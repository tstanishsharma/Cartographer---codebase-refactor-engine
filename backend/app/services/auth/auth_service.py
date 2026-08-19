"""
Cartographer — Authentication Service.

Business logic layer for user registration, login, and token management.
Wraps UserRepository with domain-level validation and error handling.

Keeps all auth logic out of the router layer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.repositories.user_repo import UserRepository

logger = structlog.get_logger(__name__)


class AuthService:
    """
    Domain service for authentication operations.

    Keeps business logic out of the router layer by providing
    named, meaningful operations with proper error types.
    """

    def __init__(self, user_repo: UserRepository) -> None:
        self._repo = user_repo

    async def register(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str | None = None,
    ) -> User:
        """
        Register a new user account.

        Raises:
            ConflictError: If email or username already exists.
        """
        if await self._repo.email_exists(email):
            raise ConflictError(f"Email '{email}' is already registered.")
        if await self._repo.username_exists(username):
            raise ConflictError(f"Username '{username}' is already taken.")

        user = await self._repo.create(
            email=email,
            username=username,
            full_name=full_name,
            hashed_password=hash_password(password),
        )
        logger.info("auth_service.registered", user_id=str(user.id), username=username)
        return user

    async def authenticate(self, email: str, password: str) -> tuple[str, str]:
        """
        Authenticate a user and return (access_token, refresh_token).

        Raises:
            AuthenticationError: On invalid credentials or inactive account.
        """
        user = await self._repo.get_by_email(email)
        if not user or not user.hashed_password:
            raise AuthenticationError("Invalid email or password.")
        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password.")
        if not user.is_active:
            raise AuthenticationError("Account is inactive.")

        await self._repo.update(user.id, last_login_at=datetime.now(UTC))
        logger.info("auth_service.login", user_id=str(user.id))

        return (
            create_access_token(user.id, role=user.role),
            create_refresh_token(user.id),
        )

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        """
        Issue a new access token from a valid refresh token.

        Raises:
            AuthenticationError: On invalid or expired refresh token.
        """
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError("Invalid refresh token.") from exc

        user = await self._repo.get_by_id(uuid.UUID(payload["sub"]))
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive.")

        return (
            create_access_token(user.id, role=user.role),
            create_refresh_token(user.id),
        )

    async def get_user_by_id(self, user_id: uuid.UUID) -> User:
        """
        Fetch a user by ID.

        Raises:
            NotFoundError: If the user does not exist.
        """
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found.")
        return user
