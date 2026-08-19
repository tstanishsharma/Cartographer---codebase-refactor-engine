"""
Cartographer — Embedding Provider Abstraction Layer.

ALL embedding calls MUST go through this interface.
Business logic never imports sentence_transformers or openai directly.

Design:
  EmbeddingProvider (ABC)
  ├── OpenAIEmbeddingProvider   — text-embedding-3-large (default)
  ├── BGEEmbeddingProvider      — BAAI/bge-large-en-v1.5 (local)
  └── NomicEmbeddingProvider    — nomic-embed-text-v1.5 (local)

Switching providers requires only a config change (EMBEDDING_PROVIDER env var).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingModelInfo:
    """Static information about an embedding model."""

    name: str
    provider: str
    dimension: int
    max_input_tokens: int
    supports_batch: bool = True


class EmbeddingProvider(ABC):
    """
    Abstract base for all embedding provider implementations.

    Contract:
      - embed_texts()  → batch embed a list of strings
      - embed_query()  → embed a single query string
      - model_info     → static model metadata
      - health_check() → reachability check

    Implementations must be thread-safe and support concurrent calls.
    All vectors are normalized to unit length for cosine similarity.
    """

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a batch of texts.

        Args:
            texts: List of strings to embed. May be truncated to max_input_tokens.

        Returns:
            List of embedding vectors (one per input text).
            Each vector has length == model_info.dimension.

        Raises:
            EmbeddingUnavailableError: If the provider API is unreachable.
            EmbeddingError:            On unexpected provider errors.
        """
        ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """
        Embed a single query string.

        Some providers (e.g. BGE) use a different instruction prefix
        for queries vs. documents. This method handles that automatically.

        Args:
            text: The query string to embed.

        Returns:
            Embedding vector of length model_info.dimension.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the embedding provider is reachable."""
        ...

    @property
    @abstractmethod
    def model_info(self) -> EmbeddingModelInfo:
        """Return static metadata about the embedding model."""
        ...

    @property
    def dimension(self) -> int:
        """Convenience shortcut for model_info.dimension."""
        return self.model_info.dimension
