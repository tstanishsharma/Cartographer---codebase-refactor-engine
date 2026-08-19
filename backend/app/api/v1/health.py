"""
Cartographer — Health Check Router.

Provides /health and /health/ready endpoints for:
  - Load balancer health checks
  - Kubernetes liveness/readiness probes
  - Docker Compose depends_on condition: service_healthy
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.db.base import get_engine
from app.services.cache.redis_service import get_redis_client

router = APIRouter()
settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health() -> HealthResponse:
    """Basic liveness check — always returns 200 if the process is running."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.app_env,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness() -> ReadinessResponse:
    """
    Readiness check — verifies all downstream dependencies are reachable.
    Returns 200 only if DB and Redis are both healthy.
    """
    checks: dict[str, str] = {}
    all_ok = True

    # Check PostgreSQL
    try:
        from sqlalchemy import text  # noqa: PLC0415

        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"
        all_ok = False

    # Check Redis
    try:
        redis = get_redis_client()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        all_ok = False

    return ReadinessResponse(
        status="ready" if all_ok else "degraded",
        checks=checks,
    )
