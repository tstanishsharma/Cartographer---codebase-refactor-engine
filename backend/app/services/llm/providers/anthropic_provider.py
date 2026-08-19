"""
Cartographer — Anthropic (Claude) LLM Provider.

Implements LLMProvider using the official Anthropic Python SDK.
Supports all Claude models including claude-3-5-sonnet, claude-opus-4, etc.

Never import this directly from business logic.
Use app.services.llm.factory.get_llm_provider() instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.exceptions import LLMUnavailableError
from app.services.llm.base import LLMProvider, LLMResponse, LLMUsage, Message, ModelInfo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)
settings = get_settings()

# Map model names to context windows for ModelInfo
_ANTHROPIC_CONTEXT_WINDOWS: dict[str, int] = {
    "claude-opus-4-5": 200_000,
    "claude-sonnet-4-5": 200_000,
    "claude-haiku-3-5": 200_000,
    "claude-opus-4-0": 200_000,
    "claude-sonnet-4-0": 200_000,
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
}


class AnthropicProvider(LLMProvider):
    """
    Claude LLM provider via Anthropic SDK.

    Configuration via environment variables:
        ANTHROPIC_API_KEY    — required
        ANTHROPIC_BASE_URL   — optional (for private deployments)
        LLM_MODEL            — model name (default: claude-sonnet-4-5)
    """

    def __init__(self) -> None:
        try:
            import anthropic  # noqa: PLC0415

            self._client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key.get_secret_value()  # type: ignore[union-attr]
                if settings.anthropic_api_key
                else None,
                base_url=settings.anthropic_base_url,
                max_retries=0,  # We handle retries with tenacity
            )
        except ImportError as exc:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            ) from exc

        self._model = settings.llm_model
        logger.info("llm.provider.init", provider="anthropic", model=self._model)

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a complete response from Claude."""
        system_msg, anthropic_messages = self._convert_messages(messages)

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(Exception),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            ):
                with attempt:
                    import anthropic  # noqa: PLC0415

                    response = await self._client.messages.create(
                        model=self._model,
                        messages=anthropic_messages,
                        system=system_msg or anthropic.NOT_GIVEN,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stop_sequences=stop or anthropic.NOT_GIVEN,
                        **kwargs,
                    )

            content = response.content[0].text if response.content else ""
            usage = LLMUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            )

            logger.debug(
                "llm.complete",
                provider="anthropic",
                model=self._model,
                total_tokens=usage.total_tokens,
            )

            return LLMResponse(
                content=content,
                model=self._model,
                usage=usage,
                finish_reason=response.stop_reason or "stop",
                metadata={"id": response.id},
            )

        except Exception as exc:
            logger.error("llm.complete.failed", provider="anthropic", error=str(exc))
            raise LLMUnavailableError(
                f"Anthropic API error: {exc}", error_code="anthropic_error"
            ) from exc

    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from Claude."""
        system_msg, anthropic_messages = self._convert_messages(messages)

        try:
            import anthropic  # noqa: PLC0415

            async with self._client.messages.stream(
                model=self._model,
                messages=anthropic_messages,
                system=system_msg or anthropic.NOT_GIVEN,
                temperature=temperature,
                max_tokens=max_tokens,
                stop_sequences=stop or anthropic.NOT_GIVEN,
                **kwargs,
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        except Exception as exc:
            logger.error("llm.stream.failed", provider="anthropic", error=str(exc))
            raise LLMUnavailableError(f"Anthropic streaming error: {exc}") from exc

    async def health_check(self) -> bool:
        """Verify Anthropic API connectivity with a minimal request."""
        try:
            await self.complete(
                [Message(role="user", content="ping")],
                max_tokens=5,
                temperature=0,
            )
            return True
        except Exception:
            return False

    @property
    def model_info(self) -> ModelInfo:
        return ModelInfo(
            name=self._model,
            provider="anthropic",
            context_window=_ANTHROPIC_CONTEXT_WINDOWS.get(self._model, 200_000),
            supports_streaming=True,
            supports_tool_calls=True,
        )

    @staticmethod
    def _convert_messages(
        messages: list[Message],
    ) -> tuple[str | None, list[dict[str, str]]]:
        """
        Split system message out and convert to Anthropic format.

        Returns:
            (system_prompt_str_or_None, list_of_anthropic_message_dicts)
        """
        system_msg: str | None = None
        anthropic_msgs: list[dict[str, str]] = []

        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                anthropic_msgs.append({"role": msg.role, "content": msg.content})

        return system_msg, anthropic_msgs
