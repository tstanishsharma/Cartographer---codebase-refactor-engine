"""
Cartographer — Chunk Repository.

Queries for CodeChunk and Embedding models.
Includes vector similarity search via pgvector operators.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.db.models.chunk import CodeChunk
from app.db.models.embedding import Embedding
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    import uuid


class ChunkRepository(BaseRepository[CodeChunk]):
    model = CodeChunk

    async def get_by_repository(
        self, repo_id: uuid.UUID, *, limit: int = 1000, offset: int = 0
    ) -> list[CodeChunk]:
        stmt = (
            select(CodeChunk)
            .where(CodeChunk.repository_id == repo_id)
            .order_by(CodeChunk.file_path, CodeChunk.chunk_index)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_file(self, repo_id: uuid.UUID, file_path: str) -> list[CodeChunk]:
        stmt = (
            select(CodeChunk)
            .where(
                CodeChunk.repository_id == repo_id,
                CodeChunk.file_path == file_path,
            )
            .order_by(CodeChunk.chunk_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_files(self, repo_id: uuid.UUID) -> list[dict]:
        """
        Return per-file summary rows for a repository.

        Each row: {path, language, chunk_count, total_lines}.
        """
        from sqlalchemy import func  # noqa: PLC0415

        stmt = (
            select(
                CodeChunk.file_path,
                CodeChunk.language,
                func.count(CodeChunk.id).label("chunk_count"),
                func.sum(CodeChunk.end_line - CodeChunk.start_line + 1).label("total_lines"),
            )
            .where(CodeChunk.repository_id == repo_id)
            .group_by(CodeChunk.file_path, CodeChunk.language)
            .order_by(CodeChunk.file_path)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "path": row.file_path,
                "language": row.language,
                "chunk_count": row.chunk_count,
                "total_lines": int(row.total_lines or 0),
            }
            for row in result.fetchall()
        ]

    async def get_with_parent(self, chunk_id: uuid.UUID) -> CodeChunk | None:
        stmt = (
            select(CodeChunk)
            .options(selectinload(CodeChunk.parent))
            .where(CodeChunk.id == chunk_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def vector_search(
        self,
        query_vector: list[float],
        repo_id: uuid.UUID,
        *,
        top_k: int = 20,
        model: str = "text-embedding-3-large",
    ) -> list[tuple[CodeChunk, float]]:
        """
        Cosine similarity search using pgvector <=> operator.

        Returns list of (chunk, distance) tuples sorted by ascending distance
        (smaller distance = more similar).
        """
        vector_str = f"[{','.join(str(v) for v in query_vector)}]"
        stmt = text("""
            SELECT c.id, 1 - (e.vector <=> :vector::vector) AS similarity
            FROM embeddings e
            JOIN code_chunks c ON e.chunk_id = c.id
            WHERE c.repository_id = :repo_id
              AND e.model = :model
            ORDER BY e.vector <=> :vector::vector
            LIMIT :top_k
        """)
        result = await self._session.execute(
            stmt,
            {"vector": vector_str, "repo_id": repo_id, "model": model, "top_k": top_k},
        )
        rows = result.fetchall()

        chunks: list[tuple[CodeChunk, float]] = []
        for row in rows:
            chunk = await self.get_by_id(row.id)
            if chunk:
                chunks.append((chunk, float(row.similarity)))
        return chunks

    async def keyword_search(
        self,
        query: str,
        repo_id: uuid.UUID,
        *,
        top_k: int = 10,
    ) -> list[CodeChunk]:
        """Full-text keyword search using PostgreSQL tsvector."""
        stmt = text("""
            SELECT id, ts_rank(to_tsvector('english', content), plainto_tsquery(:query)) AS rank
            FROM code_chunks
            WHERE repository_id = :repo_id
              AND to_tsvector('english', content) @@ plainto_tsquery(:query)
            ORDER BY rank DESC
            LIMIT :top_k
        """)
        result = await self._session.execute(
            stmt, {"query": query, "repo_id": repo_id, "top_k": top_k}
        )
        rows = result.fetchall()
        chunks = []
        for row in rows:
            chunk = await self.get_by_id(row.id)
            if chunk:
                chunks.append(chunk)
        return chunks

    async def delete_by_repository(self, repo_id: uuid.UUID) -> int:
        """Delete all chunks for a repository. Returns deleted count."""
        stmt = text("DELETE FROM code_chunks WHERE repository_id = :repo_id RETURNING id")
        result = await self._session.execute(stmt, {"repo_id": repo_id})
        return len(result.fetchall())

    async def count_by_repository(self, repo_id: uuid.UUID) -> int:
        """Return total chunk count for a repository."""
        from sqlalchemy import func  # noqa: PLC0415

        stmt = select(func.count()).select_from(CodeChunk).where(CodeChunk.repository_id == repo_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create_embedding(
        self,
        chunk_id: uuid.UUID,
        vector: list[float],
        model: str,
        provider: str,
        token_count: int | None = None,
    ) -> Embedding:
        embedding = Embedding(
            chunk_id=chunk_id,
            vector=vector,
            model=model,
            provider=provider,
            token_count=token_count,
        )
        self._session.add(embedding)
        await self._session.flush()
        return embedding
