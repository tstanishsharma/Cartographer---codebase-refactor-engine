"""
Cartographer — Async SQLAlchemy 2 Database Engine.

Provides:
  - Async engine and session factory
  - Declarative base with common mixins
  - init_db() / close_db() lifecycle hooks
  - get_session() dependency for FastAPI DI
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# SQLAlchemy naming convention (required for Alembic auto-migrations)
# ---------------------------------------------------------------------------
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Declarative base for all ORM models.

    Applies the shared naming convention so Alembic can generate
    consistent, deterministic migration names.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Allow models to define __repr__ without boilerplate
    def __repr__(self) -> str:
        cols = ", ".join(
            f"{c.key}={getattr(self, c.key)!r}"
            for c in self.__table__.columns
            if c.key in ("id", "name", "status")
        )
        return f"<{self.__class__.__name__}({cols})>"


# ---------------------------------------------------------------------------
# Engine and session factory (module-level singletons)
# ---------------------------------------------------------------------------
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """
    Initialize the async engine and session factory.

    Called once during application startup (lifespan hook).
    Verifies connectivity by running a SELECT 1 query.
    Also ensures the pgvector extension exists.
    """
    global _engine, _session_factory  # noqa: PLW0603

    _engine = create_async_engine(
        settings.database_url,  # type: ignore[arg-type]
        echo=settings.app_debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Re-validate connections before use
        pool_recycle=3600,  # Recycle connections every hour
        connect_args={
            "server_settings": {
                "application_name": "cartographer",
            }
        },
    )

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Avoid lazy-load after commit
        autocommit=False,
        autoflush=False,
    )

    # Verify connectivity
    async with _engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        # Ensure pgvector extension is present
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.commit()

    logger.info(
        "db.connected",
        url=settings.database_url.split("@")[-1] if settings.database_url else "unknown",
    )


async def close_db() -> None:
    """Dispose the engine and release all connections on shutdown."""
    global _engine  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        logger.info("db.disconnected")
        _engine = None


def get_engine() -> AsyncEngine:
    """Return the module-level engine (must call init_db first)."""
    if _engine is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory (must call init_db first)."""
    if _session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a managed async DB session.

    Usage:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_session)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def async_session_factory():
    """
    Return the session factory as a context manager.

    Used by background tasks (e.g. ingestion_worker) that need to manage
    their own session lifecycle outside of the FastAPI request context.

    Usage:
        async with async_session_factory() as session:
            async with session.begin():
                ...
    """
    return get_session_factory()()
