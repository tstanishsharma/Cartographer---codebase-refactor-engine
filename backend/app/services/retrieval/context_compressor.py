"""
Cartographer — Context Compressor.

Reduces token usage by extracting the most relevant sentences/lines
from retrieved chunks for the final prompt assembly.

Two compression modes:
  1. LLM extraction: Asks the LLM to keep only relevant lines (best quality)
  2. Keyword filter: Keeps lines containing query keywords (fast fallback)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.services.retrieval.reranker import RankedResult

logger = structlog.get_logger(__name__)
settings = get_settings()

_MAX_COMPRESSED_CHARS = 800  # Per-chunk target after compression


class ContextCompressor:
    """
    Compresses ranked retrieval results to reduce prompt token count.

    When compression is disabled (settings.retrieval_context_compression=False),
    returns chunks unchanged (truncated to max length).
    """

    def __init__(self, llm_provider: Any | None = None) -> None:
        self._llm = llm_provider

    async def compress(
        self,
        query: str,
        results: list[RankedResult],
        max_total_chars: int = 12000,
    ) -> list[dict[str, Any]]:
        """
        Compress and format retrieved results for prompt assembly.

        Args:
            query:           Original user query (for relevance filtering).
            results:         Ranked retrieval results.
            max_total_chars: Soft limit on total context characters.

        Returns:
            List of context dicts ready for prompt injection.
        """
        if not settings.retrieval_context_compression or self._llm is None:
            return self._simple_truncate(results, max_total_chars)

        compressed: list[dict[str, Any]] = []
        total_chars = 0

        for result in results:
            if total_chars >= max_total_chars:
                break

            budget = min(_MAX_COMPRESSED_CHARS, max_total_chars - total_chars)
            compressed_content = await self._llm_extract(query, result.content, budget)

            ctx = self._to_context_dict(result, compressed_content)
            compressed.append(ctx)
            total_chars += len(compressed_content)

        logger.debug("context_compressor.done", chunks=len(compressed), chars=total_chars)
        return compressed

    async def _llm_extract(self, query: str, content: str, max_chars: int) -> str:
        """Use LLM to extract the most relevant lines from a chunk."""
        if len(content) <= max_chars:
            return content

        from app.services.llm.base import Message  # noqa: PLC0415

        messages = [
            Message(
                role="system",
                content=(
                    "Extract only the lines most relevant to the query. "
                    f"Keep the response under {max_chars} characters. "
                    "Preserve exact code. Use '...' to indicate omissions."
                ),
            ),
            Message(
                role="user",
                content=f"Query: {query}\n\nCode:\n{content[:3000]}",
            ),
        ]

        if self._llm is None:
            return content[:max_chars]
        try:
            response = await self._llm.complete(messages, max_tokens=500)
            return response.content[:max_chars]
        except Exception as exc:
            logger.warning("context_compressor.llm_failed", error=str(exc))
            return content[:max_chars]

    def _simple_truncate(
        self, results: list[RankedResult], max_total_chars: int
    ) -> list[dict[str, Any]]:
        """Truncate each chunk to max_chars without LLM compression."""
        output: list[dict[str, Any]] = []
        total = 0
        per_chunk = min(_MAX_COMPRESSED_CHARS, max_total_chars // max(len(results), 1))

        for result in results:
            if total >= max_total_chars:
                break
            content = result.content[:per_chunk]
            output.append(self._to_context_dict(result, content))
            total += len(content)

        return output

    def _to_context_dict(self, result: RankedResult, content: str) -> dict[str, Any]:
        return {
            "chunk_id": str(result.chunk_id),
            "file_path": result.file_path,
            "language": result.language,
            "content": content,
            "score": round(result.score, 4),
            "retrieval_source": result.retrieval_source,
            "start_line": result.start_line,
            "end_line": result.end_line,
            "symbol_name": result.symbol_name,
        }
