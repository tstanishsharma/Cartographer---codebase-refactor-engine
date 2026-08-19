"""
Cartographer — Embedding Service.

Batches CodeChunk objects, generates vector embeddings via the configured
EmbeddingProvider, and persists them to the embeddings table.

Never calls embedding providers directly — always goes through the factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.db.repositories.chunk_repo import ChunkRepository
    from app.services.embedding.base import EmbeddingProvider

logger = structlog.get_logger(__name__)
settings = get_settings()

# Number of chunks to embed in a single API call batch
_EMBED_BATCH_SIZE = 100


class EmbeddingService:
    """
    Generates and persists vector embeddings for code chunks.

    Processes chunks in configurable batches to stay within
    embedding API rate limits and token limits.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        chunk_repo: ChunkRepository,
    ) -> None:
        self._provider = embedding_provider
        self._chunk_repo = chunk_repo

    async def embed_chunks(
        self,
        chunk_ids_and_content: list[tuple[Any, str]],  # (chunk_db_id, content)
        on_progress: Any | None = None,
    ) -> int:
        """
        Generate and store embeddings for a list of (chunk_id, content) pairs.

        Args:
            chunk_ids_and_content: List of (UUID, text) tuples from the DB.
            on_progress: Optional async callable(completed, total) for progress.

        Returns:
            Number of embeddings successfully created.
        """
        total = len(chunk_ids_and_content)
        created = 0
        model_info = self._provider.model_info

        logger.info(
            "embedding_service.start",
            total=total,
            model=model_info.name,
            provider=model_info.provider,
        )

        for i in range(0, total, _EMBED_BATCH_SIZE):
            batch = chunk_ids_and_content[i : i + _EMBED_BATCH_SIZE]
            chunk_ids = [item[0] for item in batch]
            texts = [item[1] for item in batch]

            try:
                vectors = await self._provider.embed_texts(texts)

                for chunk_id, vector in zip(chunk_ids, vectors, strict=False):
                    await self._chunk_repo.create_embedding(
                        chunk_id=chunk_id,
                        vector=vector,
                        model=model_info.name,
                        provider=model_info.provider,
                        token_count=None,  # Provider-specific token counting TBD
                    )
                    created += 1

                if on_progress:
                    await on_progress(created, total)

                logger.debug(
                    "embedding_service.batch_done",
                    batch_start=i,
                    batch_size=len(batch),
                    total_done=created,
                )

            except Exception as exc:
                logger.error(
                    "embedding_service.batch_failed",
                    batch_start=i,
                    error=str(exc),
                )
                # Continue with the next batch rather than aborting entirely
                continue

        logger.info("embedding_service.complete", created=created, total=total)
        return created
