"""
Cartographer — Base Agent.

All 10 agents inherit from BaseAgent.
Provides: prompt loading, retry logic, metrics tracking,
streaming support, error recovery, and structlog integration.

Concrete agents override:
  - AGENT_NAME: str
  - _run(): The agent's core logic
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import structlog
import yaml
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.agents.state import AgentMetrics, AgentState
from app.core.config import get_settings
from app.services.llm.base import LLMProvider, Message

logger = structlog.get_logger(__name__)
settings = get_settings()

# Path to prompt YAML files
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class BaseAgent(ABC):
    """
    Abstract base for all Cartographer agents.

    Provides:
      - Prompt loading from YAML (never hardcoded)
      - Retry logic with tenacity
      - Per-agent metrics collection
      - Structlog context binding
      - Error recovery hooks
    """

    AGENT_NAME: str = "base_agent"
    MAX_RETRIES: int = 3

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm
        self._prompts = self._load_prompts()
        self._log = structlog.get_logger(self.__class__.__name__)

    def _load_prompts(self) -> dict[str, str]:
        """Load prompt templates from YAML file for this agent."""
        prompt_file = PROMPTS_DIR / f"{self.AGENT_NAME}.yaml"
        if not prompt_file.exists():
            self._log.warning("agent.prompts.missing", file=str(prompt_file))
            return {}
        with prompt_file.open() as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}

    def get_prompt(self, key: str, **kwargs: Any) -> str:
        """
        Retrieve and format a named prompt template.

        Args:
            key:    Key in the YAML file (e.g. "system", "user_template").
            kwargs: Variables to interpolate into the template.

        Returns:
            Formatted prompt string.
        """
        template = self._prompts.get(key, "")
        if not template:
            self._log.warning("agent.prompt.not_found", key=key, agent=self.AGENT_NAME)
            return ""
        return template.format(**kwargs) if kwargs else template

    async def invoke(self, state: AgentState) -> AgentState:
        """
        Execute the agent with retry logic and metrics collection.

        Args:
            state: Current LangGraph agent state.

        Returns:
            Updated AgentState with this agent's output populated.
        """
        start_time = time.perf_counter()
        retry_count = 0

        self._log.info("agent.start", agent=self.AGENT_NAME, run_id=state.get("run_id"))

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(Exception),
                stop=stop_after_attempt(self.MAX_RETRIES),
                wait=wait_exponential(multiplier=1, min=2, max=30),
                reraise=True,
            ):
                with attempt:
                    retry_count = attempt.retry_state.attempt_number - 1
                    result = await self._run(state)

        except Exception as exc:
            end_time = time.perf_counter()
            self._log.error(
                "agent.failed",
                agent=self.AGENT_NAME,
                error=str(exc),
                retries=retry_count,
            )
            errors = list(state.get("errors", []))
            errors.append(f"{self.AGENT_NAME}: {exc}")
            result = {
                **state,
                "errors": errors,
                "status": "failed",
                "next_agent": "reflection",
            }
            await self.on_failure(state, exc)

        end_time = time.perf_counter()
        duration_ms = round((end_time - start_time) * 1000, 2)

        # Record metrics
        metrics: list[AgentMetrics] = list(result.get("metrics", []))
        metrics.append(
            AgentMetrics(
                agent_name=self.AGENT_NAME,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                tokens_used=0,  # Overridden by agents that track tokens
                retry_count=retry_count,
            )
        )
        result["metrics"] = metrics

        self._log.info(
            "agent.complete",
            agent=self.AGENT_NAME,
            duration_ms=duration_ms,
            retries=retry_count,
        )

        return result  # type: ignore[return-value]

    @abstractmethod
    async def _run(self, state: AgentState) -> AgentState:
        """
        Core agent logic. Implemented by each concrete agent.

        Args:
            state: Current pipeline state.

        Returns:
            Updated state with this agent's output.
        """
        ...

    async def on_failure(self, state: AgentState, exc: Exception) -> None:
        """
        Hook called after all retries are exhausted.

        Override to implement custom failure recovery (e.g. cleanup, alerts).
        Default implementation is a no-op.
        """

    def build_messages(
        self,
        system_key: str = "system",
        user_key: str = "user_template",
        **template_kwargs: Any,
    ) -> list[Message]:
        """
        Build a message list from named prompt templates.

        Args:
            system_key:      Key of the system prompt in YAML.
            user_key:        Key of the user prompt template in YAML.
            template_kwargs: Variables to interpolate.

        Returns:
            List of Message objects ready for LLMProvider.complete().
        """
        messages: list[Message] = []

        system_prompt = self.get_prompt(system_key)
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))

        user_prompt = self.get_prompt(user_key, **template_kwargs)
        if user_prompt:
            messages.append(Message(role="user", content=user_prompt))

        return messages
