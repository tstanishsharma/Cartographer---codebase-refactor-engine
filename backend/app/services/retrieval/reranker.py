"""
Cartographer — Reranker.

Cross-encoder reranking of retrieved chunks for precision improvement.

Reranking strategy:
  1. Primary: LLM-based relevance scoring via the configured LLMProvider
  2. Fallback: Score fusion from individual retriever scores (RRF)

Reciprocal Rank Fusion (RRF) is always computed to merge scores from
the three retrieval sources (vector, keyword, graph) before optional
LLM reranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from app.core.config import get_settings
from app.services.retrieval.graph_retriever import GraphSearchResult
from app.services.retrieval.keyword_retriever import KeywordSearchResult
from app.services.retrieval.vector_retriever import VectorSearchResult

if TYPE_CHECKING:
    import uuid

logger = structlog.get_logger(__name__)
settings = get_settings()

AnyResult = VectorSearchResult | KeywordSearchResult | GraphSearchResult

# RRF constant (60 is standard, higher = less rank sensitivity)
_RRF_K = 60


@dataclass
class RankedResult:
    """A reranked retrieval result with merged metadata."""

    chunk_id: uuid.UUID
    file_path: str
    content: str
    language: str
    score: float
    retrieval_source: str
    start_line: int
    end_line: int
    symbol_name: str | None
    metadata: dict[str, Any]


class Reranker:
    """
    Merges results from multiple retrievers and optionally reranks with an LLM.

    Always applies Reciprocal Rank Fusion (RRF) for score merging.
    LLM reranking is applied when retrieval_reranker_enabled=True and
    reduces final candidates to retrieval_top_k_final.
    """

    def __init__(self, llm_provider: Any | None = None) -> None:
        self._llm = llm_provider

    def fuse(
        self,
        vector_results: list[VectorSearchResult],
        keyword_results: list[KeywordSearchResult],
        graph_results: list[GraphSearchResult],
    ) -> list[RankedResult]:
        """
        Apply Reciprocal Rank Fusion to merge three result lists.

        Returns deduplicated, merged results sorted by RRF score descending.
        """
        rrf_scores: dict[uuid.UUID, float] = {}
        chunk_map: dict[uuid.UUID, AnyResult] = {}

        # Process each result list
        for rank, v_result in enumerate(vector_results):
            cid = v_result.chunk.id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
            chunk_map[cid] = v_result

        for rank, k_result in enumerate(keyword_results):
            cid = k_result.chunk.id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
            if cid not in chunk_map:
                chunk_map[cid] = k_result

        for rank, g_result in enumerate(graph_results):
            cid = g_result.chunk.id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
            if cid not in chunk_map:
                chunk_map[cid] = g_result

        # Build ranked results
        ranked: list[RankedResult] = []
        for chunk_id, rrf_score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
            result = chunk_map[chunk_id]
            chunk = result.chunk
            ranked.append(
                RankedResult(
                    chunk_id=chunk.id,
                    file_path=chunk.file_path,
                    content=chunk.content,
                    language=chunk.language,
                    score=rrf_score,
                    retrieval_source=result.retrieval_source,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    symbol_name=chunk.symbol_name,
                    metadata=chunk.chunk_metadata or {},
                )
            )

        logger.debug("reranker.fused", total=len(ranked))
        return ranked

    async def llm_rerank(
        self,
        query: str,
        candidates: list[RankedResult],
        top_k: int | None = None,
    ) -> list[RankedResult]:
        """
        Use LLM to score and rerank candidates for the given query.

        If LLM reranking is disabled or the LLM fails, returns the
        RRF-ranked list truncated to top_k.
        """
        k = top_k or settings.retrieval_top_k_final

        if not settings.retrieval_reranker_enabled or self._llm is None or not candidates:
            return candidates[:k]

        # Build a scoring prompt
        candidate_texts = "\n\n".join(
            f"[{i + 1}] {c.file_path}:{c.start_line}\n{c.content[:300]}"
            for i, c in enumerate(candidates[:20])  # Cap at 20 for token budget
        )

        from app.services.llm.base import Message  # noqa: PLC0415

        messages = [
            Message(
                role="system",
                content=(
                    "You are a code relevance ranker. Given a user query and a list of code snippets, "
                    "return a JSON array of snippet indices (1-based) ordered from most to least relevant. "
                    "Return ONLY the JSON array, e.g.: [3, 1, 7, 2]"
                ),
            ),
            Message(
                role="user",
                content=f"Query: {query}\n\nCode snippets:\n{candidate_texts}",
            ),
        ]

        try:
            import json  # noqa: PLC0415

            response = await self._llm.complete(messages, max_tokens=200)
            indices = json.loads(response.content.strip())
            reranked = []
            for idx in indices:
                if 1 <= idx <= len(candidates):
                    reranked.append(candidates[idx - 1])
            # Append any candidates not mentioned by the LLM
            mentioned = set(indices)
            for i, c in enumerate(candidates, 1):
                if i not in mentioned:
                    reranked.append(c)
            logger.debug("reranker.llm_done", top_k=k)
            return reranked[:k]
        except Exception as exc:
            logger.warning("reranker.llm_failed", error=str(exc))
            return candidates[:k]
