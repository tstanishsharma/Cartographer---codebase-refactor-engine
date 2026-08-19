"""
Cartographer — Security Utilities (JWT + Password Hashing).

Design:
  - JWT tokens are stateless; the payload carries user_id + role.
  - Token creation and verification are pure functions (easily testable).
  - The authentication layer is structured for GitHub OAuth to be plugged in
    without touching this module — OAuth will produce a User record and then
    call create_access_token() just like the password flow.
  - Passwords are hashed with bcrypt via passlib.

Never import this module from the LLM / embedding / agent layers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

import bcrypt
import structlog
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plaintext password."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return hashed.decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches hashed."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
TokenType = Literal["access", "refresh"]


def create_access_token(
    user_id: UUID | str,
    *,
    role: str = "user",
    extra: dict[str, Any] | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        user_id: The user's UUID (stored as string in sub claim).
        role:    User role for coarse-grained authorization.
        extra:   Optional additional claims to embed.

    Returns:
        Signed JWT string.
    """
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": datetime.now(UTC),
        "exp": expire,
        **(extra or {}),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: UUID | str) -> str:
    """
    Create a signed JWT refresh token (longer TTL, fewer claims).

    Args:
        user_id: The user's UUID.

    Returns:
        Signed JWT string.
    """
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": datetime.now(UTC),
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, *, expected_type: TokenType = "access") -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token:         Raw JWT string from the Authorization header.
        expected_type: "access" or "refresh".

    Returns:
        The decoded payload dict.

    Raises:
        InvalidTokenError: If the token is invalid, expired, or wrong type.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        logger.warning("jwt.decode_failed", error=str(exc))
        raise InvalidTokenError("Token is invalid or has expired.") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError(
            f"Expected token type '{expected_type}', got '{payload.get('type')}'."
        )

    return payload


def get_user_id_from_token(token: str) -> str:
    """
    Extract the user_id (sub claim) from a valid access token.

    Args:
        token: Raw JWT string.

    Returns:
        User ID string.

    Raises:
        InvalidTokenError: On any token issue.
    """
    payload = decode_token(token, expected_type="access")
    sub = payload.get("sub")
    if not sub:
        raise InvalidTokenError("Token is missing 'sub' claim.")
    return str(sub)
