"""
Cartographer — Graph Repository.

Queries for GraphNode and GraphEdge models.
Provides graph traversal primitives used by the GraphRetriever service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from app.db.models.graph_edge import GraphEdge
from app.db.models.graph_node import GraphNode
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    import uuid


class GraphRepository(BaseRepository[GraphNode]):
    model = GraphNode

    async def get_by_repository(
        self, repo_id: uuid.UUID, *, node_type: str | None = None
    ) -> list[GraphNode]:
        stmt = select(GraphNode).where(GraphNode.repository_id == repo_id)
        if node_type:
            stmt = stmt.where(GraphNode.node_type == node_type)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_file(self, repo_id: uuid.UUID, file_path: str) -> list[GraphNode]:
        stmt = select(GraphNode).where(
            GraphNode.repository_id == repo_id,
            GraphNode.file_path == file_path,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_qualified_name(
        self, repo_id: uuid.UUID, qualified_name: str
    ) -> GraphNode | None:
        stmt = select(GraphNode).where(
            GraphNode.repository_id == repo_id,
            GraphNode.qualified_name == qualified_name,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_neighbors(
        self,
        node_id: uuid.UUID,
        *,
        edge_types: list[str] | None = None,
        direction: str = "outgoing",
    ) -> list[GraphNode]:
        """
        Return neighboring nodes connected by edges.

        Args:
            node_id:    The source node UUID.
            edge_types: Optional filter on edge type.
            direction:  "outgoing", "incoming", or "both".
        """
        if direction == "outgoing":
            filter_col = "source_id"
            neighbor_col = "target_id"
        elif direction == "incoming":
            filter_col = "target_id"
            neighbor_col = "source_id"
        else:
            # Both directions: union
            out = await self.get_neighbors(node_id, edge_types=edge_types, direction="outgoing")
            inc = await self.get_neighbors(node_id, edge_types=edge_types, direction="incoming")
            seen = {n.id for n in out}
            return out + [n for n in inc if n.id not in seen]

        stmt = (
            select(GraphNode)
            .join(GraphEdge, GraphEdge.__table__.c[neighbor_col] == GraphNode.id)
            .where(GraphEdge.__table__.c[filter_col] == node_id)
        )
        if edge_types:
            stmt = stmt.where(GraphEdge.edge_type.in_(edge_types))

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_subgraph(
        self,
        node_ids: list[uuid.UUID],
        *,
        edge_types: list[str] | None = None,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Return all nodes and edges within a given set of node IDs."""
        node_stmt = select(GraphNode).where(GraphNode.id.in_(node_ids))
        node_result = await self._session.execute(node_stmt)
        nodes = list(node_result.scalars().all())

        edge_stmt = select(GraphEdge).where(
            GraphEdge.source_id.in_(node_ids),
            GraphEdge.target_id.in_(node_ids),
        )
        if edge_types:
            edge_stmt = edge_stmt.where(GraphEdge.edge_type.in_(edge_types))
        edge_result = await self._session.execute(edge_stmt)
        edges = list(edge_result.scalars().all())

        return nodes, edges

    async def create_edge(
        self,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        edge_type: str,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> GraphEdge:
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            metadata=metadata or {},
        )
        self._session.add(edge)
        await self._session.flush()
        return edge

    async def count_by_repository(self, repo_id: uuid.UUID) -> int:
        """Return total node count for a repository."""
        from sqlalchemy import func  # noqa: PLC0415

        stmt = select(func.count()).select_from(GraphNode).where(GraphNode.repository_id == repo_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_edges_by_repository(self, repo_id: uuid.UUID) -> int:
        """Return total edge count for a repository."""
        from sqlalchemy import func  # noqa: PLC0415

        stmt = (
            select(func.count())
            .select_from(GraphEdge)
            .join(GraphNode, GraphNode.id == GraphEdge.source_id)
            .where(GraphNode.repository_id == repo_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete_by_repository(self, repo_id: uuid.UUID) -> None:
        """Delete all graph data for a repository."""
        await self._session.execute(
            text(
                "DELETE FROM graph_edges WHERE source_id IN "
                "(SELECT id FROM graph_nodes WHERE repository_id = :repo_id)"
            ),
            {"repo_id": repo_id},
        )
        await self._session.execute(
            text("DELETE FROM graph_nodes WHERE repository_id = :repo_id"),
            {"repo_id": repo_id},
        )
