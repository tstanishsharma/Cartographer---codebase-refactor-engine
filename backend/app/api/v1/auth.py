"""
Cartographer — Authentication Router.

Endpoints:
  POST /auth/register  — create account (JWT)
  POST /auth/login     — issue access + refresh tokens
  POST /auth/refresh   — rotate access token using refresh token
  POST /auth/logout    — client-side token invalidation (stateless)
  GET  /auth/me        — get current user profile

GitHub OAuth (plug-in later):
  GET  /auth/github/login    — redirect to GitHub (when GITHUB_OAUTH_ENABLED)
  GET  /auth/github/callback — handle OAuth callback
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import CurrentUser, DbSession, UserRepo  # noqa: TC001, TC002
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth")
settings = get_settings()


# ── Request/Response schemas ────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8)
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str | None
    avatar_url: str | None
    role: str
    is_active: bool
    created_at: str


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, repo: UserRepo, db: DbSession) -> UserResponse:
    """Register a new user account."""
    if await repo.email_exists(body.email):
        raise HTTPException(status_code=409, detail="Email already registered.")
    if await repo.username_exists(body.username):
        raise HTTPException(status_code=409, detail="Username already taken.")

    user = await repo.create(
        email=body.email,
        username=body.username,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
    )
    logger.info("auth.register", user_id=str(user.id), username=user.username)
    return _user_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, repo: UserRepo) -> TokenResponse:
    """Authenticate with email/password and receive JWT tokens."""
    user = await repo.get_by_email(body.email)
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive.")

    # Update last login
    await repo.update(user.id, last_login_at=datetime.now(UTC))
    logger.info("auth.login", user_id=str(user.id))

    return _token_response(user.id, user.role)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, repo: UserRepo) -> TokenResponse:
    """Issue a new access token using a valid refresh token."""
    import uuid  # noqa: PLC0415

    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token.") from exc

    user = await repo.get_by_id(uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found.")

    return _token_response(user.id, user.role)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return _user_response(current_user)


# ── GitHub OAuth stubs (activated when GITHUB_OAUTH_ENABLED=true) ──────────

if settings.github_oauth_enabled:

    @router.get("/github/login")
    async def github_login() -> dict:
        """Redirect to GitHub OAuth authorization page."""
        import urllib.parse  # noqa: PLC0415

        params = urllib.parse.urlencode(
            {
                "client_id": settings.github_client_id,
                "redirect_uri": settings.github_callback_url,
                "scope": "read:user user:email",
            }
        )
        return {"redirect_url": f"https://github.com/login/oauth/authorize?{params}"}

    @router.get("/github/callback")
    async def github_callback(code: str, repo: UserRepo) -> TokenResponse:
        """Handle GitHub OAuth callback and issue JWT tokens."""
        # TODO: Implement in Phase 3 (GitHub OAuth phase)
        raise HTTPException(status_code=501, detail="GitHub OAuth not yet implemented.")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _token_response(user_id: object, role: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id, role=role),  # type: ignore[arg-type]
        refresh_token=create_refresh_token(user_id),  # type: ignore[arg-type]
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


def _user_response(user: object) -> UserResponse:
    return UserResponse(
        id=str(getattr(user, "id", "")),
        email=getattr(user, "email", ""),
        username=getattr(user, "username", ""),
        full_name=getattr(user, "full_name", None),
        avatar_url=getattr(user, "avatar_url", None),
        role=getattr(user, "role", "user"),
        is_active=getattr(user, "is_active", True),
        created_at=getattr(user, "created_at", datetime.now(UTC)).isoformat(),
    )
