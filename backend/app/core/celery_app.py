"""
Cartographer — Celery Application.

Optional distributed task queue for long-running work (repository ingestion).

The FastAPI backend currently drives ingestion via ``BackgroundTasks`` for a
zero-dependency local flow; this module makes the ``worker`` service in
``docker-compose.yml`` (``celery -A app.core.celery_app worker``) functional
so the same job can be offloaded to Celery when scaled out.
"""

from __future__ import annotations

import asyncio

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

# Redis doubles as the Celery broker and result backend.
_redis_url = settings.redis_url or "redis://localhost:6379/0"

celery_app = Celery(
    "cartographer",
    broker=_redis_url,
    backend=_redis_url,
    include=["app.core.celery_app"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)


def _run_async(coro):
    """Run a coroutine inside the Celery worker's event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        # We are already inside an async context — spin the coroutine to
        # completion by scheduling it as a task on the running loop.
        return asyncio.run_coroutine_threadsafe(coro, loop).result()
    return asyncio.run(coro)


@celery_app.task(name="app.core.celery_app.ingest_repository", bind=True)
def ingest_repository(self, repository_id: str) -> dict:
    """
    Celery task that ingests a repository.

    Delegates to the same async ingestion path used by FastAPI's
    ``BackgroundTasks``. ``repository_id`` is passed as a string because
    Celery serializes UUIDs through JSON.
    """
    import structlog

    from app.db.base import async_session_factory
    from app.db.repositories.chunk_repo import ChunkRepository
    from app.db.repositories.graph_repo import GraphRepository
    from app.db.repositories.repository_repo import RepositoryRepository
    from app.services.embedding.factory import get_embedding_provider
    from app.services.ingestion.ingestion_orchestrator import IngestionOrchestrator

    logger = structlog.get_logger(__name__)
    logger.info("celery.ingest.start", repository_id=repository_id)

    async def _run() -> None:
        async with async_session_factory() as session, session.begin():
            orchestrator = IngestionOrchestrator(
                repo_repo=RepositoryRepository(session),
                chunk_repo=ChunkRepository(session),
                graph_repo=GraphRepository(session),
                embedding_provider=get_embedding_provider(),
            )
            await orchestrator.ingest(repository_id)

    try:
        _run_async(_run())
        logger.info("celery.ingest.done", repository_id=repository_id)
        return {"repository_id": repository_id, "status": "completed"}
    except Exception as exc:  # noqa: BLE001
        logger.error("celery.ingest.error", repository_id=repository_id, error=str(exc))
        raise self.retry(exc=exc, countdown=10, max_retries=3) from exc
