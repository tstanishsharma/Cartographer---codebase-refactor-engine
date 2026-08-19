"""
Cartographer — Vector Retriever.

Performs cosine similarity search over the embeddings table using pgvector.
Embeds the query using the configured EmbeddingProvider, then delegates
to ChunkRepository.vector_search().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings

if TYPE_CHECKING:
    import uuid

    from app.db.models.chunk import CodeChunk
    from app.db.repositories.chunk_repo import ChunkRepository
    from app.services.embedding.base import EmbeddingProvider

logger = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class VectorSearchResult:
    chunk: CodeChunk
    score: float
    retrieval_source: str = "vector"


class VectorRetriever:
    """
    Embeds a query and retrieves the top-k most similar code chunks
    from pgvector using cosine similarity.
    """

    def __init__(
        self,
        chunk_repo: ChunkRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._chunk_repo = chunk_repo
        self._embedding_provider = embedding_provider

    async def retrieve(
        self,
        query: str,
        repository_id: uuid.UUID,
        top_k: int | None = None,
        metadata_filter: dict | None = None,
    ) -> list[VectorSearchResult]:
        """
        Embed query and perform vector similarity search.

        Args:
            query:           Natural language or code query.
            repository_id:   Scope to a specific repository.
            top_k:           Number of results (defaults to settings.retrieval_top_k_vector).
            metadata_filter: Optional chunk metadata filter (language, file_path, etc.)

        Returns:
            List of VectorSearchResult ordered by descending similarity.
        """
        k = top_k or settings.retrieval_top_k_vector
        model_info = self._embedding_provider.model_info

        logger.debug(
            "vector_retriever.embed_query",
            query_len=len(query),
            model=model_info.name,
        )
        query_vector = await self._embedding_provider.embed_query(query)

        rows = await self._chunk_repo.vector_search(
            query_vector=query_vector,
            repo_id=repository_id,
            top_k=k,
            model=model_info.name,
        )

        results = [VectorSearchResult(chunk=chunk, score=score) for chunk, score in rows]
        logger.debug("vector_retriever.done", results=len(results))
        return results
