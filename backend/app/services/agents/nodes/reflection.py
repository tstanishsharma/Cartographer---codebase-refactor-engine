import time

from app.services.agents.base import BaseAgent
from app.services.agents.state import AgentState, ReflectionFeedback


class ReflectionAgent(BaseAgent):
    name = "ReflectionAgent"
    description = (
        "Analyzes failures and generates repair plans and improved prompts for the Edit Agent."
    )

    def get_system_prompt(self) -> str:
        return """You are the Reflection Agent.
Analyze the critic's rejection or the sandbox test failures.
Produce a Root Cause and Repair Plan."""

    async def run(self, state: AgentState) -> AgentState:
        start_time = time.time()
        self._emit_event(
            state, "Reflecting on failure to formulate repair plan...", level="warning"
        )

        import asyncio

        await asyncio.sleep(1)

        retry_count = state.get("retry_count", 0)

        should_retry = retry_count < self.max_retries

        state["reflection_feedback"] = ReflectionFeedback(
            failure_summary="Test failure on new parameters.",
            root_cause="Forgot to import the new dependency in the target file.",
            repair_plan="Add the import statement at the top of the file.",
            improved_prompt="Make sure to import `FastAPI` before using it.",
            should_retry=should_retry,
        )

        if should_retry:
            state["retry_count"] = retry_count + 1
            state["next_agent"] = "CodeEditAgent"
        else:
            state["next_agent"] = None  # escalate to human
            self._emit_event(state, "Max retries reached. Escalating to human.", level="error")

        self._track_latency(state, "reflection", start_time)
        return state
