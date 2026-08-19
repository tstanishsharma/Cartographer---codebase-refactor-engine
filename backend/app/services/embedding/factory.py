"""
Cartographer — Embedding Provider Factory.

Single entry point for resolving the configured embedding provider.
Business logic calls get_embedding_provider() and receives an
EmbeddingProvider without knowing which concrete class backs it.

Provider selection is driven entirely by EMBEDDING_PROVIDER env var.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings
from app.core.exceptions import ProviderConfigurationError

if TYPE_CHECKING:
    from app.services.embedding.base import EmbeddingProvider

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    """
    Resolve and return the configured embedding provider singleton.

    Provider determined by EMBEDDING_PROVIDER env var:
      - "openai" → OpenAIEmbeddingProvider (text-embedding-3-large)
      - "bge"    → BGEEmbeddingProvider (BAAI/bge-large-en-v1.5, local)
      - "nomic"  → NomicEmbeddingProvider (nomic-embed-text-v1.5, local)

    Returns:
        Concrete EmbeddingProvider implementation.

    Raises:
        ProviderConfigurationError: Unknown or misconfigured provider.
    """
    settings = get_settings()
    provider_name = settings.embedding_provider

    logger.info(
        "embedding.factory.resolving", provider=provider_name, model=settings.embedding_model
    )

    match provider_name:
        case "openai":
            if not settings.openai_api_key:
                raise ProviderConfigurationError(
                    "OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai"
                )
            from app.services.embedding.providers.openai_provider import (
                OpenAIEmbeddingProvider,  # noqa: PLC0415
            )

            return OpenAIEmbeddingProvider()

        case "bge":
            if not settings.bge_enabled:
                raise ProviderConfigurationError(
                    "Set BGE_ENABLED=true to use the BGE embedding provider"
                )
            from app.services.embedding.providers.bge_provider import (
                BGEEmbeddingProvider,  # noqa: PLC0415
            )

            return BGEEmbeddingProvider()

        case "nomic":
            if not settings.nomic_enabled:
                raise ProviderConfigurationError(
                    "Set NOMIC_ENABLED=true to use the Nomic embedding provider"
                )
            from app.services.embedding.providers.nomic_provider import (
                NomicEmbeddingProvider,  # noqa: PLC0415
            )

            return NomicEmbeddingProvider()

        case _:
            raise ProviderConfigurationError(
                f"Unknown embedding provider: '{provider_name}'. Valid values: openai, bge, nomic"
            )
