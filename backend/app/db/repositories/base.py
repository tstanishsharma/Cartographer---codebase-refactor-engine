"""
Cartographer — Base Repository.

Generic async CRUD repository using SQLAlchemy 2.
All concrete repositories inherit from this.

Pattern:
  - Repositories are the ONLY layer that talks to SQLAlchemy.
  - Services receive repositories via DI and call their methods.
  - No raw SQL in services or routers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from sqlalchemy import select

from app.db.base import Base

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository[ModelT: Base]:
    """
    Generic repository providing async CRUD for any SQLAlchemy model.

    Usage:
        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, entity_id: UUID) -> ModelT | None:
        """Fetch a single record by primary key."""
        return await self._session.get(self.model, entity_id)

    async def get_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
    ) -> list[ModelT]:
        """Fetch all records with optional pagination."""
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> ModelT:
        """Create and persist a new record."""
        obj = self.model(**kwargs)
        self._session.add(obj)
        await self._session.flush()  # Get the PK without committing
        await self._session.refresh(obj)
        return obj

    async def update(self, entity_id: UUID, **kwargs: Any) -> ModelT | None:
        """Update fields on an existing record."""
        obj = await self.get_by_id(entity_id)
        if obj is None:
            return None
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self._session.flush()
        await self._session.refresh(obj)
        return obj

    async def delete(self, entity_id: UUID) -> bool:
        """Delete a record by PK. Returns True if found and deleted."""
        obj = await self.get_by_id(entity_id)
        if obj is None:
            return False
        await self._session.delete(obj)
        await self._session.flush()
        return True

    async def count(self) -> int:
        """Return total row count for the model table."""
        from sqlalchemy import func  # noqa: PLC0415

        stmt = select(func.count()).select_from(self.model)
        result = await self._session.execute(stmt)
        return result.scalar_one()
