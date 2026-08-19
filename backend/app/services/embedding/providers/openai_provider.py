"""
Cartographer — OpenAI Embedding Provider.

Implements EmbeddingProvider using the OpenAI Embeddings API.
Default model: text-embedding-3-large (3072 dimensions).

Never import this directly from business logic.
Use app.services.embedding.factory.get_embedding_provider() instead.
"""

from __future__ import annotations

from typing import Any

import structlog
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.exceptions import EmbeddingUnavailableError
from app.services.embedding.base import EmbeddingModelInfo, EmbeddingProvider

logger = structlog.get_logger(__name__)
settings = get_settings()

_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
}
_MODEL_MAX_TOKENS: dict[str, int] = {
    "text-embedding-3-large": 8191,
    "text-embedding-3-small": 8191,
    "text-embedding-ada-002": 8191,
}


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI text-embedding-3-large (default) or any OpenAI embedding model.

    Supports batching up to 2048 texts per request.
    Respects the EMBEDDING_DIMENSIONS setting for dimensionality reduction.
    """

    def __init__(self) -> None:
        try:
            from openai import AsyncOpenAI  # noqa: PLC0415

            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value()  # type: ignore[union-attr]
                if settings.openai_api_key
                else None,
                base_url=settings.openai_embedding_base_url,
                max_retries=0,
            )
        except ImportError as exc:
            raise ImportError("openai package not installed") from exc

        self._model = settings.embedding_model
        self._dimensions = settings.embedding_dimensions
        logger.info("embedding.provider.init", provider="openai", model=self._model)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Batch in groups of 2048 (API limit)
        results: list[list[float]] = []
        for i in range(0, len(texts), 2048):
            batch = texts[i : i + 2048]
            results.extend(await self._embed_batch(batch))
        return results

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(Exception),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            ):
                with attempt:
                    kwargs: dict[str, Any] = {"model": self._model, "input": texts}
                    # text-embedding-3-* supports dimensions param for reduction
                    if "text-embedding-3" in self._model:
                        kwargs["dimensions"] = self._dimensions
                    response = await self._client.embeddings.create(**kwargs)

            vectors = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
            logger.debug("embedding.batch", provider="openai", count=len(texts))
            return vectors

        except Exception as exc:
            logger.error("embedding.failed", provider="openai", error=str(exc))
            raise EmbeddingUnavailableError(f"OpenAI embedding error: {exc}") from exc

    async def health_check(self) -> bool:
        try:
            await self.embed_query("health check")
            return True
        except Exception:
            return False

    @property
    def model_info(self) -> EmbeddingModelInfo:
        return EmbeddingModelInfo(
            name=self._model,
            provider="openai",
            dimension=self._dimensions,
            max_input_tokens=_MODEL_MAX_TOKENS.get(self._model, 8191),
        )
