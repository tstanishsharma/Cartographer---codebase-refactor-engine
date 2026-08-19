import time

from app.services.agents.base import BaseAgent
from app.services.agents.state import AgentState


class RetrieverAgent(BaseAgent):
    name = "RetrieverAgent"
    description = "Performs multi-stage retrieval (Rewrite -> Hybrid -> Rerank -> Compress)."

    def get_system_prompt(self) -> str:
        return """You are the Retriever Agent for Cartographer.
Your job is to rewrite the user's query for optimal retrieval, 
then orchestrate the hybrid retrieval pipeline to find all necessary context."""

    async def run(self, state: AgentState) -> AgentState:
        start_time = time.time()
        self._emit_event(state, "Retrieving repository context...")

        import asyncio

        await asyncio.sleep(1)  # simulate hybrid retrieval latency

        # In full implementation, we'd call the existing HybridRetriever
        # For now, we populate mock context
        state["retrieval_context"] = [
            {"file_path": "backend/app/main.py", "content": "app = FastAPI()"},
            {"file_path": "backend/app/api/v1/auth.py", "content": "def login(): pass"},
        ]

        if state.get("planner_output"):
            state["next_agent"] = "BlastRadiusAgent"
        else:
            state["next_agent"] = "ReasoningAgent"

        self._track_latency(state, "retrieval", start_time)
        self._emit_event(state, "Context retrieval complete.", level="success")
        return state
