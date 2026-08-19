"""
Cartographer — CodeChunk ORM Model.

A chunk is a semantically meaningful slice of a source file,
generated during the ingestion pipeline. Chunks are the atomic
unit for embedding and retrieval.

Parent-child relationships are stored here so the retrieval layer
can expand context by fetching sibling chunks.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.embedding import Embedding
    from app.db.models.repository import Repository


class CodeChunk(Base):
    """
    A slice of source code with metadata for retrieval.

    Chunks are produced by the ChunkGenerator service and stored with:
      - Source file path and byte offsets
      - Language tag
      - Structural metadata (e.g., which function/class it belongs to)
      - Parent/sibling references for parent-child retrieval
    """

    __tablename__ = "code_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Source location
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="unknown", index=True
    )
    start_line: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    end_line: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    start_byte: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_byte: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )  # Order within file
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Structural metadata (populated by AST parser)
    # e.g. {"function": "my_func", "class": "MyClass", "module": "utils"}
    chunk_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}", nullable=False
    )

    # Symbol classification — what this chunk represents (function/class/module/text)
    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="text")
    symbol_name: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    symbol_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Parent-child for hierarchical retrieval
    # parent_id points to a larger enclosing chunk (e.g. whole function)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    repository: Mapped[Repository] = relationship("Repository", back_populates="chunks")
    embeddings: Mapped[list[Embedding]] = relationship(
        "Embedding", back_populates="chunk", cascade="all, delete-orphan"
    )
    children: Mapped[list[CodeChunk]] = relationship(
        "CodeChunk", back_populates="parent", remote_side="CodeChunk.parent_id"
    )
    parent: Mapped[CodeChunk | None] = relationship(
        "CodeChunk", back_populates="children", remote_side="CodeChunk.id"
    )

    __table_args__ = (
        # Composite index for per-file chunk ordering
        Index("ix_code_chunks_repo_file", "repository_id", "file_path"),
        Index("ix_code_chunks_language", "language"),
    )
