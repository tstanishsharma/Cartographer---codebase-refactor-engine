"""
Cartographer — SandboxJob ORM Model.

Represents an isolated Docker sandbox execution session.
Tracks: container lifecycle, test results, generated diff, and logs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.repository import Repository


class SandboxJobStatus(str):
    QUEUED = "queued"
    INITIALIZING = "initializing"
    RUNNING = "running"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    TIMEOUT = "timeout"


class SandboxJob(Base):
    """
    A single sandbox execution job.

    Lifecycle:
      QUEUED → INITIALIZING (container start + git clone)
             → RUNNING (apply edits)
             → TESTING (run test suite)
             → COMPLETED (diff generated)
           or → FAILED → ROLLED_BACK
    """

    __tablename__ = "sandbox_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(
        String(50), default=SandboxJobStatus.QUEUED, nullable=False, index=True
    )

    # Docker metadata
    container_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    worktree_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The code edits to apply (list of {file_path, content} dicts)
    code_edits: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Test command to run (e.g. "pytest tests/")
    test_command: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Results
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)  # Unified git diff
    test_passed: Mapped[bool | None] = mapped_column(nullable=True)
    test_summary: Mapped[dict] = mapped_column(JSONB, default=dict)  # pytest JSON report
    execution_logs: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Combined stdout/stderr
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metrics
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    repository: Mapped[Repository] = relationship("Repository", back_populates="sandbox_jobs")
