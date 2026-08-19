"""
Cartographer — Repository ORM Model.

Represents a code repository ingested by the platform.
Tracks ingestion status, metadata, and file statistics.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.agent_run import AgentRun
    from app.db.models.chunk import CodeChunk
    from app.db.models.graph_node import GraphNode
    from app.db.models.sandbox_job import SandboxJob
    from app.db.models.user import User


class RepositoryStatus(str):
    """Repository ingestion lifecycle states."""

    PENDING = "pending"
    CLONING = "cloning"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"
    UPDATING = "updating"


class Repository(Base):
    """A code repository ingested by Cartographer."""

    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )

    # Ownership
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)  # Git clone URL
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    head_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Ingestion state
    status: Mapped[str] = mapped_column(
        String(50),
        default=RepositoryStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Statistics (populated after ingestion)
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    total_nodes: Mapped[int] = mapped_column(Integer, default=0)
    total_edges: Mapped[int] = mapped_column(Integer, default=0)
    languages: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"python": 120, "ts": 50}

    # Local clone path (inside the container)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    owner: Mapped[User] = relationship("User", back_populates="repositories")
    chunks: Mapped[list[CodeChunk]] = relationship(
        "CodeChunk", back_populates="repository", cascade="all, delete-orphan"
    )
    graph_nodes: Mapped[list[GraphNode]] = relationship(
        "GraphNode", back_populates="repository", cascade="all, delete-orphan"
    )
    sandbox_jobs: Mapped[list[SandboxJob]] = relationship(
        "SandboxJob", back_populates="repository", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[list[AgentRun]] = relationship(
        "AgentRun", back_populates="repository", cascade="all, delete-orphan"
    )
