"""
Cartographer — BAAI/BGE Local Embedding Provider.

Implements EmbeddingProvider using BAAI/bge-large-en-v1.5 via
sentence-transformers (HuggingFace). Runs entirely locally.

BGE models use an instruction prefix for queries:
    "Represent this sentence for searching relevant passages: <query>"

This is handled automatically in embed_query().

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

# BGE query instruction prefix (improves retrieval quality)
_BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

_BGE_DIMENSIONS: dict[str, int] = {
    "BAAI/bge-large-en-v1.5": 1024,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-m3": 1024,
}


class BGEEmbeddingProvider(EmbeddingProvider):
    """
    Local BGE embedding provider via sentence-transformers.

    Configuration:
        BGE_ENABLED     — must be true
        BGE_MODEL_NAME  — HuggingFace model identifier
        BGE_DEVICE      — cpu | cuda | mps
    """

    def __init__(self) -> None:
        if not settings.bge_enabled:
            raise ProviderConfigurationError(
                "BGE provider requires BGE_ENABLED=true",
                error_code="bge_disabled",
            )
        self._model_name = settings.bge_model_name
        self._device = settings.bge_device
        self._model = self._load_model()
        logger.info("embedding.provider.init", provider="bge", model=self._model_name)

    def _load_model(self) -> object:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            return SentenceTransformer(self._model_name, device=self._device)
        except ImportError as exc:
            raise ImportError("sentence-transformers not installed") from exc

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        loop = asyncio.get_event_loop()
        vectors = await loop.run_in_executor(
            None,
            lambda: self._model.encode(  # type: ignore[union-attr,attr-defined]
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=32,
            ).tolist(),
        )
        logger.debug("embedding.batch", provider="bge", count=len(texts))
        return vectors  # type: ignore[return-value]

    async def embed_query(self, text: str) -> list[float]:
        """Prepend BGE query instruction prefix for better retrieval."""
        prefixed = f"{_BGE_QUERY_INSTRUCTION}{text}"
        vectors = await self.embed_texts([prefixed])
        return vectors[0]

    async def health_check(self) -> bool:
        try:
            await self.embed_query("health check")
            return True
        except Exception:
            return False

    @property
    def model_info(self) -> EmbeddingModelInfo:
        dim = _BGE_DIMENSIONS.get(self._model_name, 1024)
        return EmbeddingModelInfo(
            name=self._model_name,
            provider="bge",
            dimension=dim,
            max_input_tokens=512,
        )
