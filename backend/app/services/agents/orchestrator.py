from collections.abc import AsyncGenerator

import structlog
from langgraph.graph import END, StateGraph

from app.services.agents.nodes.blast_radius import BlastRadiusAgent
from app.services.agents.nodes.code_edit import CodeEditAgent
from app.services.agents.nodes.critic import CriticAgent
from app.services.agents.nodes.memory import MemoryAgent
from app.services.agents.nodes.planner import PlannerAgent
from app.services.agents.nodes.reasoning import ReasoningAgent
from app.services.agents.nodes.reflection import ReflectionAgent
from app.services.agents.nodes.retriever import RetrieverAgent
from app.services.agents.nodes.supervisor import SupervisorAgent
from app.services.agents.nodes.test_runner import TestRunnerAgent
from app.services.agents.state import AgentState
from app.services.sandbox.docker_sandbox import DockerSandboxService

logger = structlog.get_logger(__name__)


class AgentOrchestrator:
    """
    Builds and executes the LangGraph StateGraph connecting all Cartographer agents.
    """

    def __init__(self, llm_provider=None):
        self.sandbox = DockerSandboxService()

        # Initialize nodes
        self.nodes = {
            "SupervisorAgent": SupervisorAgent(llm_provider),
            "PlannerAgent": PlannerAgent(llm_provider),
            "RetrieverAgent": RetrieverAgent(llm_provider),
            "ReasoningAgent": ReasoningAgent(llm_provider),
            "BlastRadiusAgent": BlastRadiusAgent(llm_provider),
            "CodeEditAgent": CodeEditAgent(llm_provider),
            "TestRunnerAgent": TestRunnerAgent(self.sandbox, llm_provider),
            "CriticAgent": CriticAgent(llm_provider),
            "ReflectionAgent": ReflectionAgent(llm_provider),
            "MemoryAgent": MemoryAgent(llm_provider),
        }

        self.graph = self._build_graph()

    def _build_graph(self):
        """Constructs the directed StateGraph with conditional edges."""
        workflow = StateGraph(AgentState)

        # Add nodes
        for name, agent in self.nodes.items():
            workflow.add_node(name, agent.run)

        # Entry point
        workflow.set_entry_point("SupervisorAgent")

        # Conditional edge from Supervisor
        workflow.add_conditional_edges(
            "SupervisorAgent",
            lambda state: state.get("next_agent"),
            {"PlannerAgent": "PlannerAgent", "RetrieverAgent": "RetrieverAgent"},
        )

        # Planner always goes to Retriever (for refactoring)
        workflow.add_edge("PlannerAgent", "RetrieverAgent")

        # Conditional edge from Retriever
        workflow.add_conditional_edges(
            "RetrieverAgent",
            lambda state: state.get("next_agent"),
            {"ReasoningAgent": "ReasoningAgent", "BlastRadiusAgent": "BlastRadiusAgent"},
        )

        # Reasoning goes to Memory -> END
        workflow.add_edge("ReasoningAgent", "MemoryAgent")

        # Blast Radius goes to Edit
        workflow.add_edge("BlastRadiusAgent", "CodeEditAgent")

        # Edit goes to Test Runner
        workflow.add_edge("CodeEditAgent", "TestRunnerAgent")

        # Test Runner goes to Critic
        workflow.add_edge("TestRunnerAgent", "CriticAgent")

        # Conditional edge from Critic (Pass -> Memory, Fail -> Reflection)
        workflow.add_conditional_edges(
            "CriticAgent",
            lambda state: state.get("next_agent"),
            {"MemoryAgent": "MemoryAgent", "ReflectionAgent": "ReflectionAgent"},
        )

        # Conditional edge from Reflection (Retry -> Code Edit, Abort -> END)
        workflow.add_conditional_edges(
            "ReflectionAgent",
            lambda state: state.get("next_agent") or END,
            {"CodeEditAgent": "CodeEditAgent", END: END},
        )

        workflow.add_edge("MemoryAgent", END)

        return workflow.compile()

    async def stream_run(self, initial_state: AgentState) -> AsyncGenerator[AgentState, None]:
        """Executes the graph and streams state updates at each node step."""
        try:
            # Init Sandbox
            await self.sandbox.initialize()

            # Use LangGraph's async stream
            async for s in self.graph.astream(initial_state):
                # s is a dict with key = node_name, value = updated_state
                # e.g., {'SupervisorAgent': {...state...}}
                for node_name, state_update in s.items():
                    yield state_update
        finally:
            await self.sandbox.cleanup()
