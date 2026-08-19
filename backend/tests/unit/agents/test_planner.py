import pytest

from app.services.agents.nodes.planner import PlannerAgent


@pytest.fixture
def empty_state():
    return {
        "user_query": "Refactor auth",
        "planner_output": None,
        "stream_events": [],
        "latency_metrics": {},
        "token_usage": {},
    }


@pytest.mark.asyncio
async def test_planner_agent_generates_task_graph(empty_state, mock_llm):
    agent = PlannerAgent(llm_provider=mock_llm)
    state = await agent.run(empty_state)

    assert state["planner_output"] is not None
    assert len(state["planner_output"].tasks) > 0
    assert state["next_agent"] == "RetrieverAgent"

    # Check if stream events were emitted
    events = state["stream_events"]
    assert len(events) >= 2

    # Check if tokens were tracked
    assert "PlannerAgent_prompt" in state["token_usage"]
    assert "PlannerAgent_completion" in state["token_usage"]
