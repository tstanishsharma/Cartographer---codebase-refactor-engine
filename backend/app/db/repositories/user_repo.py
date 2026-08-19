"""
Cartographer — User Repository.

Provides typed async CRUD for the User model with domain-specific
query methods (get_by_email, get_by_github_id, etc.).
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.models.user import User
from app.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_github_id(self, github_id: int) -> User | None:
        """Used by the GitHub OAuth flow (Phase 3+)."""
        stmt = select(User).where(User.github_id == github_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        return await self.get_by_email(email) is not None

    async def username_exists(self, username: str) -> bool:
        return await self.get_by_username(username) is not None
