"""
Cartographer — User ORM Model.

Stores authenticated users. Designed to support both password-based JWT
auth (Phase 2) and GitHub OAuth (later phase) without schema changes.

The github_id and github_username columns are nullable so the same table
serves both auth strategies.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat_session import ChatSession
    from app.db.models.repository import Repository


class User(Base):
    """Application user — supports JWT and GitHub OAuth auth."""

    __tablename__ = "users"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Identity
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Password auth (nullable — not used for OAuth-only accounts)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # GitHub OAuth (nullable — populated when GITHUB_OAUTH_ENABLED=true)
    github_id: Mapped[int | None] = mapped_column(nullable=True, unique=True, index=True)
    github_username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    github_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Role / permissions
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    repositories: Mapped[list[Repository]] = relationship(
        "Repository", back_populates="owner", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list[ChatSession]] = relationship(
        "ChatSession", back_populates="user", cascade="all, delete-orphan"
    )
