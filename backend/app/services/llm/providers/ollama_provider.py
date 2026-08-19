"""
Cartographer — Ollama Local LLM Provider.

Implements LLMProvider for locally-served models via Ollama's REST API.
Feature-flagged via OLLAMA_ENABLED=true.

Never import this directly from business logic.
Use app.services.llm.factory.get_llm_provider() instead.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from app.core.config import get_settings
from app.core.exceptions import LLMUnavailableError, ProviderConfigurationError
from app.services.llm.base import LLMProvider, LLMResponse, LLMUsage, Message, ModelInfo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)
settings = get_settings()


class OllamaProvider(LLMProvider):
    """Local Ollama inference via /api/chat. Feature-flagged via OLLAMA_ENABLED."""

    def __init__(self) -> None:
        if not settings.ollama_enabled:
            raise ProviderConfigurationError(
                "Ollama provider requires OLLAMA_ENABLED=true",
                error_code="ollama_disabled",
            )
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        logger.info("llm.provider.init", provider="ollama", model=self._model)

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if stop:
            payload["options"]["stop"] = stop  # type: ignore[index]
        try:
            resp = await self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            pt = data.get("prompt_eval_count", 0)
            ct = data.get("eval_count", 0)
            return LLMResponse(
                content=content,
                model=self._model,
                usage=LLMUsage(prompt_tokens=pt, completion_tokens=ct, total_tokens=pt + ct),
                finish_reason=data.get("done_reason", "stop"),
            )
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Ollama error: {exc}") from exc

    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with self._client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    @property
    def model_info(self) -> ModelInfo:
        return ModelInfo(
            name=self._model,
            provider="ollama",
            context_window=8192,
            supports_streaming=True,
            supports_tool_calls=False,
        )
