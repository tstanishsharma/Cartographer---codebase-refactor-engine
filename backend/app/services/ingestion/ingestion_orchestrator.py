"""
Cartographer — Ingestion Orchestrator.

Top-level service that sequences the full repository ingestion pipeline:
  1. Clone / pull the repository
  2. Scan files
  3. AST-chunk each file
  4. Persist chunks to DB
  5. Generate + persist embeddings
  6. Build knowledge graph (AST parsing → nodes + edges)
  7. Update repository status and statistics

Status transitions:
  pending → cloning → parsing → embedding → ready (or failed)

This service is driven by IngestionWorker (the background task).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from app.core.config import get_settings
from app.services.graph.ast_parser import ASTParser
from app.services.graph.graph_builder import GraphBuilder
from app.services.ingestion.chunk_service import ChunkService
from app.services.ingestion.clone_service import CloneService
from app.services.ingestion.embedding_service import EmbeddingService
from app.services.ingestion.file_scanner import FileScanner

if TYPE_CHECKING:
    import uuid
    from pathlib import Path

    from app.db.repositories.chunk_repo import ChunkRepository
    from app.db.repositories.graph_repo import GraphRepository
    from app.db.repositories.repository_repo import RepositoryRepository
    from app.services.embedding.base import EmbeddingProvider

logger = structlog.get_logger(__name__)
settings = get_settings()


class IngestionOrchestrator:
    """
    Drives the end-to-end repository ingestion pipeline.

    Each method maps to a pipeline stage and updates the repository
    status in the DB so clients can poll progress.
    """

    def __init__(
        self,
        repo_repo: RepositoryRepository,
        chunk_repo: ChunkRepository,
        graph_repo: GraphRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._repo_repo = repo_repo
        self._chunk_repo = chunk_repo
        self._graph_repo = graph_repo
        self._clone_service = CloneService(
            settings.sandbox_workspace_base.replace("sandbox", "repos")
        )
        self._file_scanner = FileScanner()
        self._chunk_service = ChunkService()
        self._embedding_service = EmbeddingService(embedding_provider, chunk_repo)
        self._ast_parser = ASTParser()
        self._graph_builder = GraphBuilder()

    async def ingest(self, repository_id: uuid.UUID) -> None:
        """
        Execute the full ingestion pipeline for a repository.

        Handles all status transitions and error recovery.
        """
        log = logger.bind(repository_id=str(repository_id))
        repo = await self._repo_repo.get_by_id(repository_id)
        if not repo:
            log.error("ingestion.not_found")
            return

        try:
            # ── Stage 1: Clone ────────────────────────────────────────────────
            await self._repo_repo.update(repository_id, status="cloning")
            log.info("ingestion.cloning", url=repo.url)

            local_path = await self._clone_service.clone(
                url=repo.url,
                repo_id=str(repository_id),
                branch=repo.default_branch,
            )
            head_sha = await self._clone_service.get_head_sha(str(repository_id))
            await self._repo_repo.update(
                repository_id,
                local_path=str(local_path),
                head_commit_sha=head_sha,
            )

            # ── Stage 2: Scan + Chunk + Persist ───────────────────────────────
            await self._repo_repo.update(repository_id, status="parsing")
            log.info("ingestion.scanning")

            scan_result = self._file_scanner.scan(local_path)
            db_chunk_ids: list[tuple[uuid.UUID, str]] = []

            for file_info in scan_result.files:
                chunks = self._chunk_service.chunk_file(file_info)

                # Build a lookup from chunk local ID → DB UUID for parent links
                local_id_map: dict[uuid.UUID, uuid.UUID] = {}

                for chunk in chunks:
                    parent_db_id = local_id_map.get(chunk.parent_id) if chunk.parent_id else None
                    db_chunk = await self._chunk_repo.create(
                        repository_id=repository_id,
                        parent_id=parent_db_id,
                        file_path=chunk.file_path,
                        language=chunk.language,
                        chunk_type=chunk.chunk_type,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        content_hash=chunk.content_hash,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        start_byte=chunk.start_byte,
                        end_byte=chunk.end_byte,
                        symbol_name=chunk.symbol_name,
                        symbol_type=chunk.symbol_type,
                        metadata=chunk.metadata,
                    )
                    local_id_map[chunk.id] = db_chunk.id
                    db_chunk_ids.append((db_chunk.id, chunk.content))

            log.info("ingestion.chunks_persisted", count=len(db_chunk_ids))

            # ── Stage 3: Embeddings ───────────────────────────────────────────
            await self._repo_repo.update(repository_id, status="embedding")
            log.info("ingestion.embedding")

            created_embeddings = await self._embedding_service.embed_chunks(db_chunk_ids)
            log.info("ingestion.embeddings_done", count=created_embeddings)

            # ── Stage 4: Graph construction ───────────────────────────────────
            log.info("ingestion.building_graph")
            await self._build_graph(repository_id, local_path)

            # ── Stage 5: Finalise ─────────────────────────────────────────────
            chunk_count = await self._chunk_repo.count_by_repository(repository_id)
            node_count = await self._graph_repo.count_by_repository(repository_id)
            edge_count = await self._graph_repo.count_edges_by_repository(repository_id)

            await self._repo_repo.update(
                repository_id,
                status="ready",
                total_files=scan_result.total_files,
                total_chunks=chunk_count,
                total_nodes=node_count,
                total_edges=edge_count,
                languages=scan_result.language_counts,
                ingested_at=datetime.now(UTC),
                error_message=None,
            )
            log.info("ingestion.complete", files=scan_result.total_files, chunks=chunk_count)

        except Exception as exc:
            log.error("ingestion.failed", error=str(exc), exc_info=True)
            await self._repo_repo.update(
                repository_id,
                status="failed",
                error_message=str(exc)[:2000],
            )
            raise

    async def _build_graph(self, repository_id: uuid.UUID, local_path: Path) -> None:
        """Parse AST and persist graph nodes + edges."""
        scan_result = self._file_scanner.scan(local_path)

        all_nodes: list[Any] = []
        all_edges: list[Any] = []

        for file_info in scan_result.files:
            if file_info.language not in ("python", "typescript", "javascript"):
                continue
            try:
                nodes, edges = self._ast_parser.parse_file(
                    content=file_info.content,
                    file_path=file_info.relative_path,
                    language=file_info.language,
                )
                all_nodes.extend(nodes)
                all_edges.extend(edges)
            except Exception as exc:
                logger.warning(
                    "ingestion.graph_parse_error",
                    file=file_info.relative_path,
                    error=str(exc),
                )

        await self._graph_builder.persist(
            repository_id=repository_id,
            nodes=all_nodes,
            edges=all_edges,
            graph_repo=self._graph_repo,
        )
