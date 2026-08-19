"""
Cartographer — Nomic Embed Local Embedding Provider.

Implements EmbeddingProvider using nomic-embed-text-v1.5 via
sentence-transformers. Supports both local and Nomic cloud API.

nomic-embed-text-v1.5 uses a task type prefix:
    "search_document: <text>"   for documents
    "search_query: <query>"     for queries

Never import directly — use embedding factory.
"""

from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.core.exceptions import ProviderConfigurationError
from app.services.embedding.base import EmbeddingModelInfo, EmbeddingProvider

logger = structlog.get_logger(__name__)
settings = get_settings()

_NOMIC_DIMENSIONS: dict[str, int] = {
    "nomic-embed-text-v1.5": 768,
    "nomic-embed-text-v1": 768,
    "nomic-embed-code": 768,
}


class NomicEmbeddingProvider(EmbeddingProvider):
    """
    Nomic Embed local provider via sentence-transformers.

    Uses task prefixes ("search_document:", "search_query:") to
    differentiate document and query embeddings.

    Configuration:
        NOMIC_ENABLED     — must be true
        NOMIC_MODEL_NAME  — HuggingFace model identifier
        NOMIC_DEVICE      — cpu | cuda | mps
        NOMIC_API_KEY     — only needed for Nomic cloud API
    """

    def __init__(self) -> None:
        if not settings.nomic_enabled:
            raise ProviderConfigurationError(
                "Nomic provider requires NOMIC_ENABLED=true",
                error_code="nomic_disabled",
            )
        self._model_name = settings.nomic_model_name
        self._device = settings.nomic_device
        self._model = self._load_model()
        logger.info("embedding.provider.init", provider="nomic", model=self._model_name)

    def _load_model(self) -> object:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            return SentenceTransformer(
                self._model_name,
                device=self._device,
                trust_remote_code=True,  # Required for Nomic models
            )
        except ImportError as exc:
            raise ImportError("sentence-transformers not installed") from exc

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        prefixed = [f"search_document: {t}" for t in texts]
        loop = asyncio.get_event_loop()
        vectors = await loop.run_in_executor(
            None,
            lambda: self._model.encode(  # type: ignore[union-attr,attr-defined]
                prefixed,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=32,
            ).tolist(),
        )
        logger.debug("embedding.batch", provider="nomic", count=len(texts))
        return vectors  # type: ignore[return-value]

    async def embed_query(self, text: str) -> list[float]:
        """Use search_query prefix for query embeddings."""
        prefixed = f"search_query: {text}"
        loop = asyncio.get_event_loop()
        vectors = await loop.run_in_executor(
            None,
            lambda: self._model.encode(  # type: ignore[union-attr,attr-defined]
                [prefixed],
                normalize_embeddings=True,
                show_progress_bar=False,
            ).tolist(),
        )
        return vectors[0]  # type: ignore[return-value]

    async def health_check(self) -> bool:
        try:
            await self.embed_query("health check")
            return True
        except Exception:
            return False

    @property
    def model_info(self) -> EmbeddingModelInfo:
        dim = _NOMIC_DIMENSIONS.get(self._model_name, 768)
        return EmbeddingModelInfo(
            name=self._model_name,
            provider="nomic",
            dimension=dim,
            max_input_tokens=8192,
        )
