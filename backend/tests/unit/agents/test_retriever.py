import pytest

from app.services.agents.nodes.retriever import RetrieverAgent


@pytest.fixture
def empty_state():
    return {
        "user_query": "Test query",
        "retrieval_context": [],
        "stream_events": [],
        "latency_metrics": {},
        "token_usage": {},
    }


@pytest.mark.asyncio
async def test_retriever_agent_basic(empty_state, mock_llm):
    agent = RetrieverAgent(llm_provider=mock_llm)
    state = await agent.run(empty_state)

    assert "retrieval_context" in state
    assert len(state["retrieval_context"]) > 0
    assert state["next_agent"] in ["ReasoningAgent", "CodeEditAgent", "BlastRadiusAgent"]

    # Check if stream events were emitted
    events = state["stream_events"]
    assert len(events) >= 2
    assert "Retrieving" in events[0]["message"]
