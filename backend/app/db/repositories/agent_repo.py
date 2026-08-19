"""
Cartographer — Agent Repository.

Queries for AgentRun and ChatSession models.
Provides real-time state updates for the agent trace UI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db.models.agent_run import AgentRun
from app.db.models.chat_session import ChatSession
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    import uuid


class AgentRepository(BaseRepository[AgentRun]):
    model = AgentRun

    async def get_by_session(self, session_id: uuid.UUID, *, limit: int = 20) -> list[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(AgentRun.session_id == session_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_chat_session(self, session_id: uuid.UUID) -> ChatSession | None:
        return await self._session.get(ChatSession, session_id)

    async def get_user_sessions(self, user_id: uuid.UUID, *, limit: int = 50) -> list[ChatSession]:
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_chat_session(
        self,
        user_id: uuid.UUID,
        repository_id: uuid.UUID | None = None,
        title: str = "New conversation",
    ) -> ChatSession:
        session = ChatSession(
            user_id=user_id,
            repository_id=repository_id,
            title=title,
        )
        self._session.add(session)
        await self._session.flush()
        return session

    async def append_message(self, session_id: uuid.UUID, role: str, content: str) -> None:
        """Append a message to the session's messages JSONB array."""
        from datetime import UTC, datetime  # noqa: PLC0415

        session = await self.get_chat_session(session_id)
        if session:
            messages = list(session.messages)
            messages.append(
                {
                    "role": role,
                    "content": content,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            session.messages = messages
            await self._session.flush()

    async def update_run_state(
        self, run_id: uuid.UUID, state: dict, active_agent: str | None = None
    ) -> None:
        run = await self.get_by_id(run_id)
        if run:
            run.state = state
            if active_agent:
                run.active_agent = active_agent
            await self._session.flush()

    async def append_trace_step(self, run_id: uuid.UUID, step: dict) -> None:
        run = await self.get_by_id(run_id)
        if run:
            trace = list(run.trace)
            trace.append(step)
            run.trace = trace
            await self._session.flush()
