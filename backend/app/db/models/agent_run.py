"""
Cartographer — AgentRun ORM Model.

Records every execution of the multi-agent LangGraph pipeline.
Stores the complete state snapshot at each step for:
  - Agent trace visualization in the frontend
  - Debugging and observability
  - Reflection / retry analysis
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
    from app.db.models.chat_session import ChatSession
    from app.db.models.repository import Repository


class AgentRunStatus(str):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRun(Base):
    """
    A single end-to-end execution of the Cartographer agent pipeline.

    Each user query spawns one AgentRun. The state JSONB column captures
    the full LangGraph AgentState at the final step (or at failure).
    """

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Which agent was active (for step-level traces)
    active_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default=AgentRunStatus.QUEUED, nullable=False, index=True
    )

    # The user's original query
    user_query: Mapped[str] = mapped_column(Text, nullable=False)

    # Full LangGraph AgentState snapshot (JSONB)
    state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Step-by-step agent trace for the UI
    # [{"step": 1, "agent": "planner", "input": {...}, "output": {...}, "duration_ms": 123}]
    trace: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Final output
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Metrics
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="agent_runs")
    repository: Mapped[Repository | None] = relationship("Repository", back_populates="agent_runs")
