"""
Cartographer — Repository (Code Repo) Repository.

Domain-specific queries for the Repository model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db.models.repository import Repository
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    import uuid


class RepositoryRepository(BaseRepository[Repository]):
    model = Repository

    async def get_by_owner(
        self, owner_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Repository]:
        stmt = (
            select(Repository)
            .where(Repository.owner_id == owner_id)
            .order_by(Repository.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_url(self, url: str, owner_id: uuid.UUID) -> Repository | None:
        stmt = select(Repository).where(Repository.url == url, Repository.owner_id == owner_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(self, status: str) -> list[Repository]:
        stmt = select(Repository).where(Repository.status == status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_owner(self, owner_id: uuid.UUID) -> int:
        from sqlalchemy import func  # noqa: PLC0415

        stmt = select(func.count()).select_from(Repository).where(Repository.owner_id == owner_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()
