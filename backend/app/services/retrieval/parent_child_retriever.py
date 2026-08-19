"""
Cartographer — Parent-Child Retriever.

Given a child chunk (e.g. a specific function body), fetches its parent
chunk (e.g. the full class or module) to provide broader context.

Used in the hybrid retrieval pipeline to expand narrow matches into
their surrounding context window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import uuid

    from app.db.models.chunk import CodeChunk
    from app.db.repositories.chunk_repo import ChunkRepository

logger = structlog.get_logger(__name__)


class ParentChildRetriever:
    """
    Expands child chunks by including their parent context.

    Follows the parent_id foreign key chain to retrieve progressively
    broader context — from a specific function up to its containing class
    or module-level chunk.
    """

    def __init__(self, chunk_repo: ChunkRepository) -> None:
        self._chunk_repo = chunk_repo

    async def expand(
        self,
        chunks: list[CodeChunk],
        max_parent_hops: int = 1,
    ) -> list[CodeChunk]:
        """
        For each chunk, optionally retrieve its parent for broader context.

        Args:
            chunks:          Input chunks from hybrid retrieval.
            max_parent_hops: How many levels up to traverse (default: 1).

        Returns:
            Expanded list with parent chunks inserted before their children.
            Deduplicates — each chunk_id appears at most once.
        """
        seen_ids: set[uuid.UUID] = set()
        result: list[CodeChunk] = []

        for chunk in chunks:
            if chunk.id in seen_ids:
                continue

            # Walk up the parent chain
            parent_chain: list[CodeChunk] = []
            current = chunk
            for _ in range(max_parent_hops):
                if current.parent_id is None:
                    break
                parent = await self._chunk_repo.get_by_id(current.parent_id)
                if parent is None or parent.id in seen_ids:
                    break
                parent_chain.append(parent)
                seen_ids.add(parent.id)
                current = parent

            # Insert parents before the child (outermost first)
            for parent in reversed(parent_chain):
                result.append(parent)

            seen_ids.add(chunk.id)
            result.append(chunk)

        logger.debug("parent_child_retriever.expanded", original=len(chunks), expanded=len(result))
        return result
