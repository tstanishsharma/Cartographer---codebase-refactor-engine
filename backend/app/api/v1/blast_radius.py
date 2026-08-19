"""
Cartographer — Blast Radius Router.

Estimates the impact of a proposed code change by traversing the
repository knowledge graph. The estimator walks *incoming* edges
(things that depend on the target symbol) up to a configurable depth,
collecting every affected file, node, and the dependency chain that
leads back to the change site.

The result drives the risk score used by the Blast Radius Agent in
the multi-agent refactoring pipeline.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from collections import deque

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, GraphRepo, RepositoryRepo  # noqa: TC001, TC002

router = APIRouter(prefix="/blast-radius")

# Maximum number of hops to traverse in the dependency graph.
_MAX_HOPS = 4


class BlastRadiusRequest(BaseModel):
    repository_id: uuid.UUID
    symbol_name: str
    file_path: str
    proposed_change: str


class AffectedNode(BaseModel):
    id: str
    node_type: str
    name: str
    qualified_name: str | None
    file_path: str
    start_line: int
    end_line: int


class BlastRadiusResponse(BaseModel):
    affected_files: list[str]
    affected_nodes: list[AffectedNode]
    risk_level: str
    risk_score: float
    reasoning: str
    dependency_chain: list[str]


@router.post("/estimate", response_model=BlastRadiusResponse)
async def estimate_blast_radius(
    body: BlastRadiusRequest,
    current_user: CurrentUser,
    repo: RepositoryRepo,
    graph_repo: GraphRepo,
) -> BlastRadiusResponse:
    """
    Estimate the blast radius of a proposed code change.

    Starting from the node matching ``symbol_name`` (scoped to
    ``file_path`` when provided), walks the dependency graph backward
    (incoming edges) and reports every reachable file and node.
    """
    repository = await repo.get_by_id(body.repository_id)
    if not repository or repository.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Repository not found.")

    seed = await _find_symbol(graph_repo, body.repository_id, body.symbol_name, body.file_path)
    if seed is None:
        return BlastRadiusResponse(
            affected_files=[],
            affected_nodes=[],
            risk_level="LOW",
            risk_score=0.05,
            reasoning=(
                f"Symbol '{body.symbol_name}' in '{body.file_path}' was not found in the "
                "knowledge graph. Verify the file has been ingested and the symbol name "
                "matches a parsed node."
            ),
            dependency_chain=[],
        )

    # BFS over incoming edges (dependents of the target symbol).
    visited: set[uuid.UUID] = {seed.id}
    queue: deque[tuple[object, int]] = deque([(seed, 0)])

    affected_nodes: list[AffectedNode] = []
    affected_files: set[str] = set()
    dependency_chain: list[str] = []
    max_depth = 0
    total_nodes = 1

    while queue:
        current, depth = queue.popleft()
        if depth > 0:
            affected_nodes.append(_node_response(current))
            affected_files.add(current.file_path)
            dependency_chain.append(f"{current.file_path}::{current.name}")
            max_depth = max(max_depth, depth)
            total_nodes += 1

        if depth >= _MAX_HOPS:
            continue

        for dependent in await graph_repo.get_neighbors(current.id, direction="incoming"):
            if dependent.id not in visited:
                visited.add(dependent.id)
                queue.append((dependent, depth + 1))

    num_files = len(affected_files)
    risk_score = min(
        1.0,
        (total_nodes * 0.15) + (num_files * 0.2) + (max_depth * 0.1),
    )
    risk_level = "LOW" if risk_score < 0.3 else "MEDIUM" if risk_score < 0.6 else "HIGH"

    if num_files == 0:
        reasoning = (
            f"'{body.symbol_name}' has no dependent nodes in the graph — the change is isolated."
        )
    else:
        reasoning = (
            f"'{body.symbol_name}' is referenced by {total_nodes - 1} node(s) across "
            f"{num_files} file(s), up to {max_depth} hop(s) away. "
            f"Change reaches {len(dependency_chain)} dependency path(s)."
        )

    return BlastRadiusResponse(
        affected_files=sorted(affected_files),
        affected_nodes=affected_nodes,
        risk_level=risk_level,
        risk_score=round(risk_score, 3),
        reasoning=reasoning,
        dependency_chain=dependency_chain,
    )


async def _find_symbol(graph_repo: GraphRepo, repo_id: uuid.UUID, name: str, file_path: str):
    """Locate a graph node by symbol name, preferring exact qualified matches."""
    # 1. Exact qualified-name match.
    for candidate in (name, file_path.split("/")[-1] + "::" + name):
        node = await graph_repo.get_by_qualified_name(repo_id, candidate)
        if node:
            return node

    # 2. Match against nodes scoped to the same file.
    for node in await graph_repo.get_by_file(repo_id, file_path):
        if node.name == name:
            return node
        if node.qualified_name and node.qualified_name.endswith(name):
            return node

    # 3. Fallback: unique name match across the whole repository.
    matches = [node for node in await graph_repo.get_by_repository(repo_id) if node.name == name]
    return matches[0] if len(matches) == 1 else None


def _node_response(node: object) -> AffectedNode:
    return AffectedNode(
        id=str(getattr(node, "id", "")),
        node_type=getattr(node, "node_type", ""),
        name=getattr(node, "name", ""),
        qualified_name=getattr(node, "qualified_name", None),
        file_path=getattr(node, "file_path", ""),
        start_line=getattr(node, "start_line", 0),
        end_line=getattr(node, "end_line", 0),
    )
