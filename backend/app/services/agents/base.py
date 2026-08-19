import abc
import time
from typing import Any

import structlog

from app.services.agents.state import AgentState

logger = structlog.get_logger(__name__)


class BaseAgent(abc.ABC):
    """
    Base class for all Cartographer LangGraph agents.
    Enforces standardized interfaces for prompts, inputs, outputs,
    retry policies, structured logging, and observability.
    """

    name: str = "BaseAgent"
    description: str = "Base agent interface."
    max_retries: int = 3

    def __init__(self, llm_provider: Any = None):
        self.llm = llm_provider
        self.log = logger.bind(agent=self.name)

    @abc.abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    @abc.abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """Execute the agent's core logic on the state."""
        pass

    def _emit_event(self, state: AgentState, message: str, level: str = "info") -> AgentState:
        """Append a streaming event to the state for real-time frontend trace."""
        event = {"agent": self.name, "message": message, "level": level, "timestamp": time.time()}
        state["stream_events"].append(event)
        self.log.info(message)
        return state

    def _track_latency(self, state: AgentState, operation: str, start_time: float) -> AgentState:
        """Record execution latency."""
        duration = time.time() - start_time
        metric_key = f"{self.name}_{operation}"
        state["latency_metrics"][metric_key] = duration
        self.log.debug(f"{operation} completed", duration_sec=duration)
        return state

    def _track_tokens(
        self, state: AgentState, prompt_tokens: int, completion_tokens: int
    ) -> AgentState:
        """Record token usage."""
        state["token_usage"][f"{self.name}_prompt"] = (
            state["token_usage"].get(f"{self.name}_prompt", 0) + prompt_tokens
        )
        state["token_usage"][f"{self.name}_completion"] = (
            state["token_usage"].get(f"{self.name}_completion", 0) + completion_tokens
        )
        return state

    async def invoke_with_retry(self, func, *args, **kwargs) -> Any:
        """Standardized retry loop with exponential backoff for LLM calls."""
        import asyncio

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                self.log.warning(
                    f"Invocation failed attempt {attempt + 1}/{self.max_retries}", error=str(e)
                )
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)
