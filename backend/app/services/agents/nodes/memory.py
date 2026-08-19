import time

from app.services.agents.base import BaseAgent
from app.services.agents.state import AgentState


class MemoryAgent(BaseAgent):
    name = "MemoryAgent"
    description = "Manages long-term repository facts and working session memory."

    def get_system_prompt(self) -> str:
        return """You are the Memory Agent for Cartographer.
Extract new facts from the recent interaction and persist them.
Condense the conversation history to save token space."""

    async def run(self, state: AgentState) -> AgentState:
        start_time = time.time()
        self._emit_event(state, "Updating long-term memory...")

        import asyncio

        await asyncio.sleep(0.5)

        state["memory_summary"] = "The user is exploring the auth module."
        state["next_agent"] = None  # Terminal node usually

        self._track_latency(state, "memory_update", start_time)
        return state
