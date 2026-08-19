import time

from app.services.agents.base import BaseAgent
from app.services.agents.state import AgentState, PlannerOutput, TaskDependency


class PlannerAgent(BaseAgent):
    name = "PlannerAgent"
    description = "Decomposes complex requests into a graph of dependent tasks."

    def get_system_prompt(self) -> str:
        return """You are the Planner Agent for Cartographer.
Your job is to analyze the user's request and decompose it into a logical graph of tasks.
Each task must have an ID, description, expected output, context required, risk level, and a list of dependent task IDs.
Return a JSON object matching this schema exactly:
{
  "tasks": [
    {
      "task_id": "step_1",
      "depends_on": [],
      "description": "...",
      "expected_output": "...",
      "required_context": ["file_a.py"],
      "risk_level": "LOW"
    }
  ],
  "overall_risk": "MEDIUM",
  "reasoning": "..."
}"""

    async def run(self, state: AgentState) -> AgentState:
        start_time = time.time()
        self._emit_event(state, "Planning task breakdown...")

        # In a real implementation with LangChain/Pydantic AI, we'd invoke the LLM with structured output.
        # Here we mock the structured output for phase completion

        prompt = self.get_system_prompt() + f"\n\nUser Query: {state['user_query']}"

        # Mocking LLM invocation
        import asyncio

        await asyncio.sleep(1)  # simulate latency

        # Simulated LLM output
        mock_output = PlannerOutput(
            tasks=[
                TaskDependency(
                    task_id="analyze_impact",
                    depends_on=[],
                    description="Find all references to the targeted code",
                    expected_output="List of affected files",
                    required_context=["dependencies"],
                    risk_level="LOW",
                ),
                TaskDependency(
                    task_id="generate_edits",
                    depends_on=["analyze_impact"],
                    description="Generate refactoring edits",
                    expected_output="Proposed code changes",
                    required_context=["target files"],
                    risk_level="MEDIUM",
                ),
            ],
            overall_risk="MEDIUM",
            reasoning="Standard refactoring flow requires analyzing impact before editing.",
        )

        state["planner_output"] = mock_output
        state["next_agent"] = "RetrieverAgent"

        self._track_latency(state, "planning", start_time)
        self._track_tokens(state, len(prompt.split()), 150)
        self._emit_event(state, "Planning complete.")
        return state
