"""
Cartographer — Hybrid Retriever.

Top-level retrieval orchestrator that combines vector, keyword, and graph
retrieval with RRF score fusion, LLM reranking, parent-child expansion,
and context compression into a single pipeline call.

This is the primary retrieval interface consumed by the Retriever Agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from app.core.config import get_settings
from app.services.retrieval.context_compressor import ContextCompressor
from app.services.retrieval.graph_retriever import GraphRetriever
from app.services.retrieval.keyword_retriever import KeywordRetriever
from app.services.retrieval.parent_child_retriever import ParentChildRetriever
from app.services.retrieval.reranker import Reranker
from app.services.retrieval.vector_retriever import VectorRetriever

if TYPE_CHECKING:
    import uuid

    from app.db.repositories.chunk_repo import ChunkRepository
    from app.db.repositories.graph_repo import GraphRepository
    from app.services.embedding.base import EmbeddingProvider

logger = structlog.get_logger(__name__)
settings = get_settings()


class HybridRetriever:
    """
    Orchestrates the full hybrid retrieval pipeline:
      1. Vector search   — semantic similarity
      2. Keyword search  — exact name/symbol matching
      3. Graph search    — structural neighborhood traversal
      4. RRF fusion      — merge all three result lists
      5. LLM reranking   — optional cross-encoder reranking
      6. Parent-child    — expand child chunks to their parent context
      7. Compression     — reduce token budget for prompt assembly

    Returns: list[dict] ready for direct injection into LLM prompts.
    """

    def __init__(
        self,
        chunk_repo: ChunkRepository,
        graph_repo: GraphRepository,
        embedding_provider: EmbeddingProvider,
        llm_provider: Any | None = None,
    ) -> None:
        self._vector = VectorRetriever(chunk_repo, embedding_provider)
        self._keyword = KeywordRetriever(chunk_repo)
        self._graph = GraphRetriever(graph_repo, chunk_repo)
        self._reranker = Reranker(llm_provider)
        self._parent_child = ParentChildRetriever(chunk_repo)
        self._compressor = ContextCompressor(llm_provider)
        self._chunk_repo = chunk_repo

    async def retrieve(
        self,
        query: str,
        repository_id: uuid.UUID,
        entity_names: list[str] | None = None,
        metadata_filter: dict | None = None,
        top_k_final: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute the full hybrid retrieval pipeline.

        Args:
            query:           User query text.
            repository_id:   Repository to search within.
            entity_names:    Code entity names extracted from query for graph seeding.
            metadata_filter: Optional filter dict (language, file_path, etc.)
            top_k_final:     Final result count after reranking.

        Returns:
            List of context dicts with chunk_id, file_path, content, score, etc.
        """
        k = top_k_final or settings.retrieval_top_k_final
        log = logger.bind(repository_id=str(repository_id), query_len=len(query))
        log.info("hybrid_retriever.start")

        import asyncio  # noqa: PLC0415

        # ── Step 1-3: Run all three retrievers concurrently ─────────────────
        vector_task = asyncio.create_task(
            self._vector.retrieve(query, repository_id, metadata_filter=metadata_filter)
        )
        keyword_task = asyncio.create_task(self._keyword.retrieve(query, repository_id))
        graph_task = asyncio.create_task(self._graph.retrieve(entity_names or [], repository_id))

        vector_results, keyword_results, graph_results = await asyncio.gather(
            vector_task,
            keyword_task,
            graph_task,
            return_exceptions=False,
        )

        log.debug(
            "hybrid_retriever.retrieved",
            vector=len(vector_results),
            keyword=len(keyword_results),
            graph=len(graph_results),
        )

        # ── Step 4: RRF fusion ───────────────────────────────────────────────
        fused = self._reranker.fuse(vector_results, keyword_results, graph_results)

        # ── Step 5: LLM reranking ────────────────────────────────────────────
        reranked = await self._reranker.llm_rerank(query, fused, top_k=k * 2)

        # ── Step 6: Parent-child expansion ───────────────────────────────────
        [self._chunk_repo._session.get for r in reranked]  # Already have chunks
        # Resolve RankedResult → CodeChunk objects
        chunks = []
        for r in reranked:
            c = await self._chunk_repo.get_by_id(r.chunk_id)
            if c:
                chunks.append(c)

        expanded = await self._parent_child.expand(chunks, max_parent_hops=1)

        # ── Step 7: Context compression ──────────────────────────────────────
        # Convert expanded chunks back to RankedResult format for compressor
        ranked_expanded = []
        chunk_score_map = {r.chunk_id: r.score for r in reranked}
        for chunk in expanded:
            from app.services.retrieval.reranker import RankedResult  # noqa: PLC0415

            ranked_expanded.append(
                RankedResult(
                    chunk_id=chunk.id,
                    file_path=chunk.file_path,
                    content=chunk.content,
                    language=chunk.language,
                    score=chunk_score_map.get(chunk.id, 0.1),
                    retrieval_source="expanded",
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    symbol_name=chunk.symbol_name,
                    metadata=chunk.chunk_metadata or {},
                )
            )

        context = await self._compressor.compress(query, ranked_expanded)

        log.info(
            "hybrid_retriever.complete",
            fused=len(fused),
            reranked=len(reranked),
            final=len(context),
        )
        return context
