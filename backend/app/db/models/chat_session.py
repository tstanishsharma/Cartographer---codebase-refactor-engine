"""
Cartographer — ChatSession ORM Model.

A chat session groups all messages and agent runs for a single
conversation context between a user and a repository.

Messages are stored as a JSONB array for simplicity and fast retrieval.
Each message follows the OpenAI-compatible format:
    {"role": "user"|"assistant"|"system", "content": "...", "timestamp": "..."}
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.agent_run import AgentRun
    from app.db.models.repository import Repository
    from app.db.models.user import User


class ChatSession(Base):
    """A conversation between a user and a repository's knowledge graph."""

    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Human-readable title (auto-generated from first message)
    title: Mapped[str] = mapped_column(String(500), default="New conversation")

    # Full message history as JSONB array
    # [{"role": "user", "content": "...", "timestamp": "2024-01-01T00:00:00Z"}]
    messages: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Session-scoped memory managed by the Memory Agent
    memory: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="chat_sessions")
    repository: Mapped[Repository | None] = relationship("Repository")
    agent_runs: Mapped[list[AgentRun]] = relationship(
        "AgentRun", back_populates="session", cascade="all, delete-orphan"
    )
