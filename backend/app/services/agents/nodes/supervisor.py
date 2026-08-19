import time

from app.services.agents.base import BaseAgent
from app.services.agents.state import AgentState


class SupervisorAgent(BaseAgent):
    name = "SupervisorAgent"
    description = "Orchestrates the multi-agent system (intent classification, task scheduling)."

    def get_system_prompt(self) -> str:
        return """You are the Supervisor Agent (Operating System of Cartographer).
Classify the user intent:
- If it's a simple query or architectural question -> Route to RetrieverAgent -> ReasoningAgent
- If it's a refactoring or code edit request -> Route to PlannerAgent -> RetrieverAgent -> BlastRadiusAgent -> CodeEditAgent
"""

    async def run(self, state: AgentState) -> AgentState:
        start_time = time.time()
        self._emit_event(state, "Classifying intent and routing...")

        import asyncio

        await asyncio.sleep(0.5)

        query = state.get("user_query", "").lower()

        if "refactor" in query or "change" in query or "add" in query or "fix" in query:
            state["next_agent"] = "PlannerAgent"
            self._emit_event(state, "Intent classified: Refactoring. Routing to Planner.")
        else:
            state["next_agent"] = "RetrieverAgent"
            self._emit_event(state, "Intent classified: Code Query. Routing to Retriever.")

        self._track_latency(state, "supervisor", start_time)
        return state
