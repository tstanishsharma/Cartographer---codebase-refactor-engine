"""
Cartographer — Embedding ORM Model.

Stores vector embeddings for code chunks.
Uses pgvector's VECTOR column type.

One chunk may have multiple embeddings from different models,
enabling model comparison and fallback.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chunk import CodeChunk


class Embedding(Base):
    """
    Vector embedding for a CodeChunk.

    The vector column dimension is set from settings.embedding_dimensions.
    Default: 3072 (text-embedding-3-large).

    For HNSW index creation see the Alembic migration — pgvector requires
    the extension and a CREATE INDEX USING hnsw statement.
    """

    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which model produced this vector
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # openai | bge | nomic

    # The embedding vector (3072-dim for text-embedding-3-large)
    # pgvector handles cosine / L2 / dot-product distance queries
    vector: Mapped[list[float]] = mapped_column(Vector(3072), nullable=False)

    # Token count for cost tracking
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    chunk: Mapped[CodeChunk] = relationship("CodeChunk", back_populates="embeddings")

    __table_args__ = (
        # Composite uniqueness — one embedding per chunk per model
        Index("ix_embeddings_chunk_model", "chunk_id", "model", unique=True),
        # NOTE: HNSW index is added in the Alembic migration using raw SQL:
        #   CREATE INDEX USING hnsw (vector vector_cosine_ops)
    )
