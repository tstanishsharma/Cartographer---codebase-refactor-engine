"""
Cartographer — Graph Retriever.

Performs structural context retrieval via multi-hop graph traversal.
Finds related code by following "calls", "imports", "inherits", and "defines"
edges in the knowledge graph — capturing relationships that semantic search
cannot find.

Pipeline:
  1. Find seed nodes matching the query (by name or qualified_name LIKE)
  2. Traverse outward up to N hops
  3. Resolve node → chunk by file_path + line range
  4. Return chunks representing the structural neighborhood
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings

if TYPE_CHECKING:
    import uuid

    from app.db.models.chunk import CodeChunk
    from app.db.models.graph_node import GraphNode
    from app.db.repositories.chunk_repo import ChunkRepository
    from app.db.repositories.graph_repo import GraphRepository

logger = structlog.get_logger(__name__)
settings = get_settings()

# Edge types to follow during traversal
TRAVERSAL_EDGE_TYPES = ["calls", "imports", "inherits", "defines", "depends_on", "uses"]


@dataclass
class GraphSearchResult:
    chunk: CodeChunk
    score: float
    retrieval_source: str = "graph"
    path: list[str] | None = None  # Qualified name path from seed to this node

    def __post_init__(self):
        if self.path is None:
            self.path = []


class GraphRetriever:
    """
    Multi-hop graph traversal retriever.

    Given an entity name from the query, finds the corresponding graph node
    and traverses its neighbors up to retrieval_graph_traversal_depth hops,
    then resolves each neighbor back to the code chunk that contains it.
    """

    def __init__(
        self,
        graph_repo: GraphRepository,
        chunk_repo: ChunkRepository,
    ) -> None:
        self._graph_repo = graph_repo
        self._chunk_repo = chunk_repo

    async def retrieve(
        self,
        entity_names: list[str],
        repository_id: uuid.UUID,
        top_k: int | None = None,
        max_hops: int | None = None,
    ) -> list[GraphSearchResult]:
        """
        Traverse the knowledge graph starting from seed entities.

        Args:
            entity_names:  List of class/function names extracted from the query.
            repository_id: Scope to a specific repository.
            top_k:         Maximum total results.
            max_hops:      Traversal depth (defaults to settings).

        Returns:
            List of GraphSearchResult ordered by graph distance (closer = higher score).
        """
        k = top_k or settings.retrieval_top_k_graph
        hops = max_hops or settings.retrieval_graph_traversal_depth

        if not entity_names:
            return []

        # Find seed nodes
        seed_nodes: list[GraphNode] = []
        for name in entity_names:
            nodes = await self._find_nodes_by_name(repository_id, name)
            seed_nodes.extend(nodes)

        if not seed_nodes:
            logger.debug("graph_retriever.no_seeds", entities=entity_names)
            return []

        # Multi-hop BFS traversal
        visited: set[uuid.UUID] = set()
        frontier: list[tuple[GraphNode, int, list[str]]] = [
            (n, 0, [n.qualified_name or n.name]) for n in seed_nodes
        ]
        collected: list[tuple[GraphNode, int, list[str]]] = []

        while frontier and len(collected) < k * 3:
            next_frontier = []
            for node, depth, path in frontier:
                if node.id in visited:
                    continue
                visited.add(node.id)
                collected.append((node, depth, path))

                if depth < hops:
                    neighbors = await self._graph_repo.get_neighbors(
                        node.id,
                        edge_types=TRAVERSAL_EDGE_TYPES,
                        direction="both",
                    )
                    for neighbor in neighbors:
                        if neighbor.id not in visited:
                            next_frontier.append(
                                (
                                    neighbor,
                                    depth + 1,
                                    path + [neighbor.qualified_name or neighbor.name],
                                )
                            )
            frontier = next_frontier

        # Resolve nodes → chunks
        results: list[GraphSearchResult] = []
        for node, depth, path in collected[:k]:
            chunk = await self._resolve_node_to_chunk(node, repository_id)
            if chunk:
                score = max(0.1, 1.0 - (depth * 0.2))
                results.append(GraphSearchResult(chunk=chunk, score=score, path=path))

        logger.debug("graph_retriever.done", results=len(results), seeds=len(seed_nodes))
        return results

    async def _find_nodes_by_name(self, repository_id: uuid.UUID, name: str) -> list[GraphNode]:
        """Find graph nodes matching a name (exact or qualified_name LIKE)."""
        nodes = await self._graph_repo.get_by_repository(repository_id)
        return [
            n for n in nodes if n.name == name or (n.qualified_name and name in n.qualified_name)
        ][:5]  # Limit seeds per entity

    async def _resolve_node_to_chunk(
        self, node: GraphNode, repository_id: uuid.UUID
    ) -> CodeChunk | None:
        """Find the code chunk that best represents a graph node."""
        chunks = await self._chunk_repo.get_by_file(repository_id, node.file_path)
        if not chunks:
            return None

        # Find the chunk whose line range overlaps with the node
        for chunk in chunks:
            if chunk.start_line <= node.start_line <= chunk.end_line:
                return chunk

        # Fallback: return the first chunk from that file
        return chunks[0] if chunks else None
