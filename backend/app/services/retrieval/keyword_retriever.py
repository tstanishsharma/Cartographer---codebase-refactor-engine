"""
Cartographer — Keyword Retriever.

Performs PostgreSQL full-text BM25-style retrieval using tsvector/tsquery.
Complements vector search by catching exact symbol/API name matches that
semantic search might miss.
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

logger = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class KeywordSearchResult:
    chunk: CodeChunk
    score: float
    retrieval_source: str = "keyword"


class KeywordRetriever:
    """
    Full-text keyword search over code chunks using PostgreSQL tsvector.

    Particularly effective for:
      - Exact function / class name lookups
      - API endpoint names
      - Variable names and string literals
    """

    def __init__(self, chunk_repo: ChunkRepository) -> None:
        self._chunk_repo = chunk_repo

    async def retrieve(
        self,
        query: str,
        repository_id: uuid.UUID,
        top_k: int | None = None,
    ) -> list[KeywordSearchResult]:
        """
        Perform full-text keyword search.

        Args:
            query:         Natural language or keyword query.
            repository_id: Scope to a specific repository.
            top_k:         Number of results.

        Returns:
            List of KeywordSearchResult ordered by relevance rank.
        """
        k = top_k or settings.retrieval_top_k_keyword

        chunks = await self._chunk_repo.keyword_search(
            query=query,
            repo_id=repository_id,
            top_k=k,
        )

        # Assign decreasing scores (1.0, 0.9, ... ) since keyword_search orders by rank
        results = [
            KeywordSearchResult(chunk=chunk, score=1.0 - (i * 0.05))
            for i, chunk in enumerate(chunks)
        ]
        logger.debug("keyword_retriever.done", results=len(results))
        return results
