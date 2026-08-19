"""
Cartographer — LLM Provider Abstraction Layer.

ALL LLM calls in the application MUST go through this interface.
Business logic never imports anthropic, openai, or ollama directly.

Design:
  LLMProvider (ABC)
  ├── AnthropicProvider   — Claude models
  ├── OpenAIProvider      — GPT-4.1 / OpenAI-compatible APIs
  └── OllamaProvider      — Local inference (feature-flagged)

Switching providers requires only a config change (LLM_PROVIDER env var).
The factory function resolves and returns the correct implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@dataclass(frozen=True)
class Message:
    """
    A single message in a conversation.

    Compatible with the OpenAI chat format.
    role must be one of: "system", "user", "assistant", "tool".
    """

    role: str
    content: str
    name: str | None = None  # Optional name for multi-agent scenarios
    tool_call_id: str | None = None  # For tool response messages


@dataclass
class LLMUsage:
    """Token usage statistics from a single LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """
    The result of a non-streaming LLM completion.

    Attributes:
        content:   The generated text content.
        model:     The actual model name used.
        usage:     Token usage counters.
        finish_reason: Why the model stopped (stop, length, tool_calls).
        metadata:  Provider-specific extra data.
    """

    content: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelInfo:
    """Static information about an LLM model."""

    name: str
    provider: str
    context_window: int
    supports_streaming: bool = True
    supports_tool_calls: bool = True
    supports_vision: bool = False


class LLMProvider(ABC):
    """
    Abstract base for all LLM provider implementations.

    Contract:
      - complete()     → full response (blocking-style, awaited)
      - stream()       → async generator of token strings
      - health_check() → True if the provider API is reachable
      - model_info     → static model metadata property

    Implementations must be stateless with respect to conversation history.
    Callers are responsible for building the full messages list.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a complete (non-streaming) response.

        Args:
            messages:    Ordered list of conversation messages.
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens:  Maximum tokens to generate.
            stop:        Optional stop sequences.
            **kwargs:    Provider-specific parameters.

        Returns:
            LLMResponse with content, usage, and metadata.

        Raises:
            LLMUnavailableError: If the provider is unreachable.
            EmbeddingError:      On unexpected provider errors.
        """
        ...

    @abstractmethod
    def stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Stream generated tokens as an async generator.

        Yields individual token strings as they are produced.
        The caller should aggregate them to reconstruct the full response.

        Args:
            messages:    Ordered list of conversation messages.
            temperature: Sampling temperature.
            max_tokens:  Maximum tokens to generate.
            stop:        Optional stop sequences.
            **kwargs:    Provider-specific parameters.

        Yields:
            Token strings (may be partial words depending on provider).
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify the provider API is reachable and configured correctly.

        Returns:
            True if the provider is healthy, False otherwise.
        """
        ...

    @property
    @abstractmethod
    def model_info(self) -> ModelInfo:
        """Return static metadata about the configured model."""
        ...

    def __repr__(self) -> str:
        info = self.model_info
        return f"<{self.__class__.__name__}(model={info.name}, provider={info.provider})>"
