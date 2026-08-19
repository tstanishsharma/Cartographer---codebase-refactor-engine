"""
Cartographer — Graph Router.

Exposes the repository knowledge graph for visualization in React Flow.
"""

from __future__ import annotations

import uuid  # noqa: TC003

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import CurrentUser, GraphRepo, RepositoryRepo  # noqa: TC001, TC002

router = APIRouter(prefix="/graph")


class NodeResponse(BaseModel):
    id: str
    node_type: str
    name: str
    qualified_name: str | None
    file_path: str
    start_line: int
    end_line: int
    metadata: dict


class EdgeResponse(BaseModel):
    id: str
    source_id: str
    target_id: str
    edge_type: str
    weight: float


class GraphResponse(BaseModel):
    nodes: list[NodeResponse]
    edges: list[EdgeResponse]
    total_nodes: int
    total_edges: int


@router.get("/repositories/{repo_id}", response_model=GraphResponse)
async def get_repository_graph(
    repo_id: uuid.UUID,
    current_user: CurrentUser,
    repo: RepositoryRepo,
    graph_repo: GraphRepo,
    node_type: str | None = Query(None, description="Filter by node type"),
    file_path: str | None = Query(None, description="Filter by file path"),
) -> GraphResponse:
    """
    Return the full knowledge graph for a repository.

    Suitable for React Flow visualization — returns nodes and edges
    in a format ready for direct use with React Flow.
    """
    repository = await repo.get_by_id(repo_id)
    if not repository or repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Repository not found.")

    if file_path:
        nodes = await graph_repo.get_by_file(repo_id, file_path)
    else:
        nodes = await graph_repo.get_by_repository(repo_id, node_type=node_type)

    node_ids = [n.id for n in nodes]
    _, edges = await graph_repo.get_subgraph(node_ids)

    return GraphResponse(
        nodes=[
            NodeResponse(
                id=str(n.id),
                node_type=n.node_type,
                name=n.name,
                qualified_name=n.qualified_name,
                file_path=n.file_path,
                start_line=n.start_line,
                end_line=n.end_line,
                metadata=n.node_metadata,
            )
            for n in nodes
        ],
        edges=[
            EdgeResponse(
                id=str(e.id),
                source_id=str(e.source_id),
                target_id=str(e.target_id),
                edge_type=e.edge_type,
                weight=e.weight,
            )
            for e in edges
        ],
        total_nodes=len(nodes),
        total_edges=len(edges),
    )


@router.get("/repositories/{repo_id}/nodes/{node_id}/neighbors", response_model=list[NodeResponse])
async def get_node_neighbors(
    repo_id: uuid.UUID,
    node_id: uuid.UUID,
    current_user: CurrentUser,
    graph_repo: GraphRepo,
    edge_types: list[str] = Query(default=[]),
    direction: str = Query(default="outgoing"),
) -> list[NodeResponse]:
    """Return neighboring nodes for graph expansion in React Flow."""
    neighbors = await graph_repo.get_neighbors(
        node_id, edge_types=edge_types or None, direction=direction
    )
    return [
        NodeResponse(
            id=str(n.id),
            node_type=n.node_type,
            name=n.name,
            qualified_name=n.qualified_name,
            file_path=n.file_path,
            start_line=n.start_line,
            end_line=n.end_line,
            metadata=n.node_metadata,
        )
        for n in neighbors
    ]
