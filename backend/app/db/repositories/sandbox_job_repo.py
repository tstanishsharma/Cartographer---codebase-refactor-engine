"""
Cartographer — SandboxJob Repository.

Queries for the SandboxJob model (Docker sandbox execution sessions).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db.models.sandbox_job import SandboxJob
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    import uuid


class SandboxJobRepository(BaseRepository[SandboxJob]):
    model = SandboxJob

    async def get_by_repository(
        self, repo_id: uuid.UUID, *, limit: int = 20, offset: int = 0
    ) -> list[SandboxJob]:
        stmt = (
            select(SandboxJob)
            .where(SandboxJob.repository_id == repo_id)
            .order_by(SandboxJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
