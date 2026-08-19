import time

from app.services.agents.base import BaseAgent
from app.services.agents.state import AgentState, EditOperation


class CodeEditAgent(BaseAgent):
    name = "CodeEditAgent"
    description = "Generates structured edit operations (SEARCH/REPLACE) instead of full files."

    def get_system_prompt(self) -> str:
        return """You are the Code Edit Agent.
Output JSON with a list of SEARCH/REPLACE operations that cleanly apply the refactoring."""

    async def run(self, state: AgentState) -> AgentState:
        start_time = time.time()
        self._emit_event(state, "Generating structured search/replace edits...")

        import asyncio

        await asyncio.sleep(1)

        # MOCK
        state["edit_operations"] = [
            EditOperation(
                operation_type="SEARCH_REPLACE",
                file_path="backend/app/main.py",
                search_block="app = FastAPI()",
                replace_block="app = FastAPI(title='Cartographer')",
            )
        ]

        state["next_agent"] = "TestRunnerAgent"

        self._track_latency(state, "code_edit", start_time)
        return state
