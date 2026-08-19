"""
Cartographer — Graph Builder.

Persists ParsedNode and ParsedEdge objects (from ASTParser) to the
graph_nodes and graph_edges tables via GraphRepository.

Handles:
  - Deduplication: won't create duplicate nodes for the same qualified_name
  - Cross-file edge resolution: looks up target nodes by qualified_name
  - Batch persistence for efficiency
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import uuid

    from app.db.repositories.graph_repo import GraphRepository
    from app.services.graph.ast_parser import ParsedEdge, ParsedNode

logger = structlog.get_logger(__name__)


class GraphBuilder:
    """
    Persists AST-parsed graph data to the database.

    Maintains an in-memory qualified_name → db_id lookup within a single
    ingestion run to efficiently resolve cross-file edges without extra queries.
    """

    async def persist(
        self,
        repository_id: uuid.UUID,
        nodes: list[ParsedNode],
        edges: list[ParsedEdge],
        graph_repo: GraphRepository,
    ) -> tuple[int, int]:
        """
        Persist all nodes and edges for a repository ingestion.

        Args:
            repository_id: Target repository UUID.
            nodes:         Parsed nodes from ASTParser.
            edges:         Parsed edges from ASTParser.
            graph_repo:    GraphRepository bound to the current session.

        Returns:
            (nodes_created, edges_created) tuple.
        """
        # Map: qualified_name → db UUID (for edge resolution)
        qname_to_id: dict[str, uuid.UUID] = {}
        # All qualified names, used for suffix-matching import/inherits targets.
        all_qnames: set[str] = set()
        nodes_created = 0

        # ── Persist nodes ──────────────────────────────────────────────────────
        for pn in nodes:
            # Skip duplicates within this run
            if pn.qualified_name in qname_to_id:
                continue

            # Check if already exists in DB (re-ingestion case)
            existing = await graph_repo.get_by_qualified_name(repository_id, pn.qualified_name)
            if existing:
                qname_to_id[pn.qualified_name] = existing.id
                all_qnames.add(pn.qualified_name)
                continue

            db_node = await graph_repo.create(
                repository_id=repository_id,
                node_type=pn.node_type,
                name=pn.name,
                qualified_name=pn.qualified_name,
                file_path=pn.file_path,
                start_line=pn.start_line,
                end_line=pn.end_line,
                metadata=pn.metadata,
            )
            qname_to_id[pn.qualified_name] = db_node.id
            all_qnames.add(pn.qualified_name)
            nodes_created += 1

        logger.info("graph_builder.nodes_persisted", count=nodes_created)

        def resolve_target(target: str) -> uuid.UUID | None:
            """Exact match first, then a unique suffix match.

            Handles bare references produced by the parsers, e.g.
            ``inherits`` "Command" → "src.click.core.Command" or an
            absolute import "click.core" → "src.click.core".
            """
            if target in qname_to_id:
                return qname_to_id[target]
            matches = [q for q in all_qnames if q.endswith("." + target)]
            if len(matches) == 1:
                return qname_to_id[matches[0]]
            return None

        # ── Persist edges ──────────────────────────────────────────────────────
        edges_created = 0
        for pe in edges:
            source_id = qname_to_id.get(pe.source_qualified_name)
            target_id = resolve_target(pe.target_qualified_name)

            # For external imports (e.g. "os", "react"), target won't exist in the graph.
            # Skip those edges — we only track intra-repository relationships.
            if source_id is None or target_id is None:
                continue

            await graph_repo.create_edge(
                source_id=source_id,
                target_id=target_id,
                edge_type=pe.edge_type,
                weight=pe.weight,
                metadata=pe.metadata,
            )
            edges_created += 1

        logger.info("graph_builder.edges_persisted", count=edges_created)
        return nodes_created, edges_created
