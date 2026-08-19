"""
Cartographer — Ingestion Worker.

Thin async wrapper that drives IngestionOrchestrator as a background task.
Called by FastAPI BackgroundTasks and can be extended to use Celery/ARQ
for distributed execution in production.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.db.base import async_session_factory
from app.db.repositories.chunk_repo import ChunkRepository
from app.db.repositories.graph_repo import GraphRepository
from app.db.repositories.repository_repo import RepositoryRepository
from app.services.embedding.factory import get_embedding_provider
from app.services.ingestion.ingestion_orchestrator import IngestionOrchestrator

if TYPE_CHECKING:
    import uuid

logger = structlog.get_logger(__name__)


async def run_ingestion(repository_id: uuid.UUID) -> None:
    """
    Background task entry point for repository ingestion.

    Creates a fresh DB session (separate from the request session that
    created the repository record) and drives the full pipeline.

    Args:
        repository_id: UUID of the Repository record to ingest.
    """
    log = logger.bind(repository_id=str(repository_id), task="ingestion_worker")
    log.info("ingestion_worker.start")

    try:
        async with async_session_factory() as session, session.begin():
            orchestrator = IngestionOrchestrator(
                repo_repo=RepositoryRepository(session),
                chunk_repo=ChunkRepository(session),
                graph_repo=GraphRepository(session),
                embedding_provider=get_embedding_provider(),
            )
            await orchestrator.ingest(repository_id)

        log.info("ingestion_worker.done")

    except Exception as exc:
        log.error("ingestion_worker.error", error=str(exc), exc_info=True)
        raise
