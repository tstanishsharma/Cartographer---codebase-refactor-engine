import time

from app.services.agents.base import BaseAgent
from app.services.agents.state import AgentState


class ReasoningAgent(BaseAgent):
    name = "ReasoningAgent"
    description = "Synthesizes retrieved context to answer architectural or code queries."

    def get_system_prompt(self) -> str:
        return """You are the Reasoning Agent for Cartographer.
Use the retrieved context to answer the user's question accurately.
Include inline citations to the files you used."""

    async def run(self, state: AgentState) -> AgentState:
        start_time = time.time()
        self._emit_event(state, "Reasoning over codebase context...")

        import asyncio

        await asyncio.sleep(1)

        # MOCK
        state["proposed_diff"] = None  # Not an edit
        state["next_agent"] = "MemoryAgent"

        self._track_latency(state, "reasoning", start_time)
        return state
