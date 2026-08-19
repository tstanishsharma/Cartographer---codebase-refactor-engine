import time

from app.services.agents.base import BaseAgent
from app.services.agents.state import AgentState


class TestRunnerAgent(BaseAgent):
    name = "TestRunnerAgent"
    description = "Runs tests via the SandboxService."

    def __init__(self, sandbox_service, llm_provider=None):
        super().__init__(llm_provider)
        self.sandbox = sandbox_service

    def get_system_prompt(self) -> str:
        return "Not an LLM agent. Execution agent that interfaces with Docker."

    async def run(self, state: AgentState) -> AgentState:
        start_time = time.time()
        self._emit_event(state, "Running tests in isolated sandbox...")

        # We apply edits first
        await self.sandbox.apply_edits(state.get("edit_operations", []))

        # Auto-detect ecosystem (mock logic)
        # Normally would check for pytest.ini, package.json etc in sandbox
        command = "pytest"

        res = await self.sandbox.execute(command)
        diff = await self.sandbox.get_diff()
        res.git_diff = diff

        state["sandbox_status"] = res

        state["next_agent"] = "CriticAgent"

        self._track_latency(state, "test_runner", start_time)
        if res.status == "PASS":
            self._emit_event(state, "Tests passed successfully.", level="success")
        else:
            self._emit_event(state, f"Tests failed: {res.stderr[:100]}", level="error")

        return state
