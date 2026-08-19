"""
Cartographer Backend — Application Entry Point.

This module creates and configures the FastAPI application instance,
registers all middleware, routers, exception handlers, and startup/shutdown
lifecycle hooks.

Architecture: Clean Architecture with Dependency Injection via FastAPI Depends.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import (
    agents,
    auth,
    blast_radius,
    chat,
    graph,
    health,
    repositories,
    sandbox,
)
from app.core.config import get_settings
from app.core.exceptions import CartographerError
from app.core.logging import configure_logging
from app.core.telemetry import configure_telemetry
from app.db.base import close_db, init_db
from app.services.cache.redis_service import close_redis, init_redis

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    # ── Startup ──────────────────────────────────────────────────────────────
    configure_logging(level=settings.log_level, fmt=settings.log_format)
    configure_telemetry(settings)

    logger.info(
        "cartographer.startup",
        environment=settings.app_env,
        version=settings.app_version,
    )

    await init_db()
    await init_redis(settings)

    logger.info("cartographer.ready", host=settings.app_host, port=settings.app_port)

    yield  # ── Application running ──────────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("cartographer.shutdown")
    await close_redis()
    await close_db()


def create_app() -> FastAPI:
    """
    Application factory.

    Returns a fully configured FastAPI application.
    Keeping creation separate from module-level instantiation enables
    clean testing (each test gets its own app instance).
    """
    _settings = get_settings()

    app = FastAPI(
        title="Cartographer API",
        description=(
            "Autonomous code-understanding platform with Graph RAG, "
            "multi-agent reasoning, and sandboxed execution."
        ),
        version=_settings.app_version,
        docs_url="/api/docs" if _settings.app_debug else None,
        redoc_url="/api/redoc" if _settings.app_debug else None,
        openapi_url="/api/openapi.json" if _settings.app_debug else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins,
        allow_credentials=_settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Request ID + Timing Middleware ────────────────────────────────────────
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next: object) -> Response:
        import uuid

        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response: Response = await call_next(request)  # type: ignore[operator]

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "http.request",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        return response

    # ── Exception Handlers ───────────────────────────────────────────────────
    @app.exception_handler(CartographerError)
    async def cartographer_exception_handler(
        request: Request, exc: CartographerError
    ) -> JSONResponse:
        logger.warning("cartographer.error", error=str(exc), error_code=exc.error_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": str(exc),
                "detail": exc.detail,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled.exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred.",
            },
        )

    # ── Prometheus Metrics ────────────────────────────────────────────────────
    if _settings.prometheus_enabled:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            should_group_status_codes=False,
            excluded_handlers=["/api/v1/health"],
        ).instrument(app).expose(app, endpoint="/metrics")

    # ── Routers ───────────────────────────────────────────────────────────────
    api_prefix = "/api/v1"
    app.include_router(health.router, prefix=api_prefix, tags=["health"])
    app.include_router(auth.router, prefix=api_prefix, tags=["auth"])
    app.include_router(repositories.router, prefix=api_prefix, tags=["repositories"])
    app.include_router(chat.router, prefix=api_prefix, tags=["chat"])
    app.include_router(agents.router, prefix=api_prefix, tags=["agents"])
    app.include_router(graph.router, prefix=api_prefix, tags=["graph"])
    app.include_router(sandbox.router, prefix=api_prefix, tags=["sandbox"])
    app.include_router(blast_radius.router, prefix=api_prefix, tags=["blast-radius"])

    return app


# Module-level app instance (used by uvicorn)
app = create_app()
