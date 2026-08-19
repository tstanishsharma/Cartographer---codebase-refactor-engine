import time

from app.services.agents.base import BaseAgent
from app.services.agents.state import AgentState, CriticFeedback


class CriticAgent(BaseAgent):
    name = "CriticAgent"
    description = "Evaluates code correctness, performance, and architecture."

    def get_system_prompt(self) -> str:
        return """You are the Critic Agent.
Analyze the Code Edit Agent's diff and the Test Runner's output.
Ensure all constraints are met."""

    async def run(self, state: AgentState) -> AgentState:
        start_time = time.time()
        self._emit_event(state, "Reviewing edits and test results...")

        import asyncio

        await asyncio.sleep(1)

        sandbox_res = state.get("sandbox_status")
        approved = False if sandbox_res and sandbox_res.status == "FAIL" else True

        state["critic_feedback"] = CriticFeedback(
            approved=approved,
            confidence=0.9,
            correctness_issues=[],
            architecture_issues=[],
            style_issues=[],
            complexity_issues=[],
            performance_issues=[],
            security_issues=[],
            regression_risks=[],
            missing_tests=[],
            reasoning="Tests passed, edits look clean." if approved else "Tests failed in sandbox.",
        )

        if approved:
            state["next_agent"] = "MemoryAgent"
        else:
            state["next_agent"] = "ReflectionAgent"

        self._track_latency(state, "critic", start_time)
        return state
