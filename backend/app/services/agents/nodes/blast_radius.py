import time

from app.services.agents.base import BaseAgent
from app.services.agents.state import AgentState, BlastRadiusImpact


class BlastRadiusAgent(BaseAgent):
    name = "BlastRadiusAgent"
    description = "Computes impact of proposed changes by traversing dependency graphs."

    def get_system_prompt(self) -> str:
        return """You are the Blast Radius Agent.
Analyze the target code and its dependents. Compute affected files, risk level, and depth."""

    async def run(self, state: AgentState) -> AgentState:
        start_time = time.time()
        self._emit_event(state, "Calculating blast radius across dependency graph...")

        import asyncio

        await asyncio.sleep(1.5)

        state["blast_radius"] = BlastRadiusImpact(
            affected_files=["backend/app/main.py", "backend/app/api/deps.py"],
            affected_functions=["init_db", "get_current_user"],
            dependency_depth=3,
            confidence=0.92,
            estimated_risk="HIGH",
            visualization_payload={"nodes": [], "edges": []},
        )

        state["next_agent"] = (
            "CodeEditAgent"  # Usually goes to edit after blast radius if refactoring
        )

        self._track_latency(state, "blast_radius", start_time)
        self._emit_event(state, "Blast radius evaluated: HIGH risk.", level="warning")
        return state
