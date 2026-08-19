"""
Cartographer — OpenAI LLM Provider.

Implements LLMProvider for GPT-4.1, GPT-4o, and any OpenAI-compatible
API (e.g. Azure OpenAI, Together AI, Groq, vLLM, LM Studio).

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

_OPENAI_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4.1": 1_047_576,
    "gpt-4.1-mini": 1_047_576,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "o1": 200_000,
    "o3": 200_000,
}


class OpenAIProvider(LLMProvider):
    """
    OpenAI / OpenAI-compatible LLM provider.

    Configuration:
        OPENAI_API_KEY    — required
        OPENAI_BASE_URL   — optional override (default: api.openai.com/v1)
        OPENAI_ORG_ID     — optional
        LLM_MODEL         — model name (default: from settings)
    """

    def __init__(self) -> None:
        try:
            from openai import AsyncOpenAI  # noqa: PLC0415

            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value()  # type: ignore[union-attr]
                if settings.openai_api_key
                else None,
                base_url=settings.openai_base_url,
                organization=settings.openai_org_id,
                max_retries=0,
            )
        except ImportError as exc:
            raise ImportError("openai package not installed. Run: pip install openai") from exc

        self._model = settings.llm_model
        logger.info("llm.provider.init", provider="openai", model=self._model)

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a complete response from GPT."""
        oai_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(Exception),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            ):
                with attempt:
                    response = await self._client.chat.completions.create(
                        model=self._model,
                        messages=oai_messages,  # type: ignore[arg-type]
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stop=stop,
                        **kwargs,
                    )

            choice = response.choices[0]
            content = choice.message.content or ""
            usage_data = response.usage
            usage = LLMUsage(
                prompt_tokens=usage_data.prompt_tokens if usage_data else 0,
                completion_tokens=usage_data.completion_tokens if usage_data else 0,
                total_tokens=usage_data.total_tokens if usage_data else 0,
            )

            logger.debug(
                "llm.complete",
                provider="openai",
                model=self._model,
                total_tokens=usage.total_tokens,
            )

            return LLMResponse(
                content=content,
                model=self._model,
                usage=usage,
                finish_reason=choice.finish_reason or "stop",
                metadata={"id": response.id},
            )

        except Exception as exc:
            logger.error("llm.complete.failed", provider="openai", error=str(exc))
            raise LLMUnavailableError(
                f"OpenAI API error: {exc}", error_code="openai_error"
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
        """Stream tokens from GPT."""
        oai_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            async with await self._client.chat.completions.create(
                model=self._model,
                messages=oai_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop,
                stream=True,
                **kwargs,
            ) as stream:
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yield delta

        except Exception as exc:
            logger.error("llm.stream.failed", provider="openai", error=str(exc))
            raise LLMUnavailableError(f"OpenAI streaming error: {exc}") from exc

    async def health_check(self) -> bool:
        """Verify OpenAI API connectivity."""
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
            provider="openai",
            context_window=_OPENAI_CONTEXT_WINDOWS.get(self._model, 128_000),
            supports_streaming=True,
            supports_tool_calls=True,
        )
