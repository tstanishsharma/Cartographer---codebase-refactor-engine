import uuid

import pytest

from app.services.agents.orchestrator import AgentOrchestrator


@pytest.fixture
def orchestrator(mock_llm, mock_sandbox):
    # Dependency inject mocks
    orch = AgentOrchestrator(llm_provider=mock_llm)
    orch.sandbox = mock_sandbox
    # Overwrite test runner's sandbox reference as well
    orch.nodes["TestRunnerAgent"].sandbox = mock_sandbox
    return orch


@pytest.fixture
def empty_state():
    return {
        "session_id": uuid.uuid4(),
        "repository_id": uuid.uuid4(),
        "user_query": "",
        "conversation_history": [],
        "retrieval_context": [],
        "graph_context": [],
        "selected_files": [],
        "selected_symbols": [],
        "planner_output": None,
        "blast_radius": None,
        "proposed_diff": None,
        "edit_operations": [],
        "sandbox_status": None,
        "test_results": None,
        "critic_feedback": None,
        "reflection_feedback": None,
        "execution_logs": [],
        "current_agent": "SupervisorAgent",
        "next_agent": None,
        "retry_count": 0,
        "confidence_score": 1.0,
        "latency_metrics": {},
        "token_usage": {},
        "memory_summary": "",
        "citations": [],
        "stream_events": [],
        "errors": [],
    }


@pytest.mark.asyncio
async def test_supervisor_routing_query(orchestrator, empty_state):
    """Test that a basic query routes to Retriever."""
    state = empty_state.copy()
    state["user_query"] = "What does the auth service do?"

    # Run just the supervisor node
    result = await orchestrator.nodes["SupervisorAgent"].run(state)
    assert result["next_agent"] == "RetrieverAgent"


@pytest.mark.asyncio
async def test_supervisor_routing_refactor(orchestrator, empty_state):
    """Test that a refactor query routes to Planner."""
    state = empty_state.copy()
    state["user_query"] = "Refactor the auth service to use JWT"

    result = await orchestrator.nodes["SupervisorAgent"].run(state)
    assert result["next_agent"] == "PlannerAgent"


@pytest.mark.asyncio
async def test_full_query_workflow(orchestrator, empty_state):
    """Test Supervisor -> Retriever -> Reasoning -> Memory"""
    state = empty_state.copy()
    state["user_query"] = "Explain the architecture."

    nodes_visited = []
    async for s in orchestrator.stream_run(state):
        if s.get("stream_events"):
            nodes_visited.append(s["stream_events"][-1]["agent"])

    assert "SupervisorAgent" in nodes_visited
    assert "RetrieverAgent" in nodes_visited
    assert "ReasoningAgent" in nodes_visited
    assert "MemoryAgent" in nodes_visited
    assert "CodeEditAgent" not in nodes_visited


@pytest.mark.asyncio
async def test_full_refactor_workflow(orchestrator, empty_state):
    """Test the long execution loop ending in a Pass"""
    state = empty_state.copy()
    state["user_query"] = "Fix the authentication bug."

    nodes_visited = []
    async for s in orchestrator.stream_run(state):
        if s.get("stream_events"):
            nodes_visited.append(s["stream_events"][-1]["agent"])

    assert "SupervisorAgent" in nodes_visited
    assert "PlannerAgent" in nodes_visited
    assert "BlastRadiusAgent" in nodes_visited
    assert "CodeEditAgent" in nodes_visited
    assert "TestRunnerAgent" in nodes_visited
    assert "CriticAgent" in nodes_visited
    # The mock sandbox always returns PASS, so critic passes -> Memory -> END
    assert "MemoryAgent" in nodes_visited
    assert "ReflectionAgent" not in nodes_visited


@pytest.fixture
def failing_orchestrator(mock_llm):
    # Create an orchestrator with a sandbox that always fails
    class FailingSandbox:
        async def initialize(self, *args, **kwargs):
            return True

        async def execute(self, cmd, **kwargs):
            from app.services.agents.state import SandboxResult

            return SandboxResult(
                status="FAIL", stdout="", stderr="Build failed", exit_code=1, execution_time_sec=0.1
            )

        async def apply_edits(self, edits):
            return True

        async def get_diff(self):
            return ""

        async def cleanup(self):
            pass

    orch = AgentOrchestrator(llm_provider=mock_llm)
    failing_sb = FailingSandbox()
    orch.sandbox = failing_sb
    orch.nodes["TestRunnerAgent"].sandbox = failing_sb
    return orch


@pytest.mark.asyncio
async def test_reflection_escalation(failing_orchestrator, empty_state):
    """Test the reflection loop aborts after max retries."""
    state = empty_state.copy()
    state["user_query"] = "Fix the bug."

    # We will just run the graph starting from CodeEditAgent to simulate entering the execution loop
    # Or start from Supervisor and wait for it to abort.
    # Since failing sandbox always fails, it will loop exactly max_retries (3) times.

    nodes_visited = []
    async for s in failing_orchestrator.stream_run(state):
        if s.get("stream_events"):
            nodes_visited.append(s["stream_events"][-1]["agent"])

    # Count occurrences of ReflectionAgent
    reflection_count = nodes_visited.count("ReflectionAgent")
    assert reflection_count == 4
    # It should not reach MemoryAgent on a terminal failure
    assert "MemoryAgent" not in nodes_visited
