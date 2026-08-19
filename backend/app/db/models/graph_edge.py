"""
Cartographer — GraphEdge ORM Model.

Directed edges in the repository knowledge graph.
Supported edge types:

  IMPORTS      — module A imports from module B
  CALLS        — function A calls function B
  INHERITS     — class A inherits from class B
  DEFINES      — module/class A defines function/class B
  DEPENDS_ON   — file A has a build dependency on package B
  REFERENCES   — symbol A references symbol B
  IMPLEMENTS   — class A implements interface B
  USES         — function A uses variable B
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.graph_node import GraphNode


class EdgeType(str):
    """Semantic relationship types between graph nodes."""

    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    DEFINES = "defines"
    DEPENDS_ON = "depends_on"
    REFERENCES = "references"
    IMPLEMENTS = "implements"
    USES = "uses"


class GraphEdge(Base):
    """
    A directed edge in the repository knowledge graph.

    Weight represents the strength of the relationship
    (e.g. call frequency for CALLS edges, 1.0 for structural edges).
    """

    __tablename__ = "graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source and target nodes
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    edge_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    # Optional: extra edge attributes (e.g. import alias, call argument count)
    edge_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    source: Mapped[GraphNode] = relationship(
        "GraphNode", foreign_keys=[source_id], back_populates="outgoing_edges"
    )
    target: Mapped[GraphNode] = relationship(
        "GraphNode", foreign_keys=[target_id], back_populates="incoming_edges"
    )

    __table_args__ = (
        # Fast edge lookups by type for graph traversal
        Index("ix_graph_edges_source_type", "source_id", "edge_type"),
        Index("ix_graph_edges_target_type", "target_id", "edge_type"),
        # Prevent duplicate edges of same type between same nodes
        Index(
            "uq_graph_edges_source_target_type",
            "source_id",
            "target_id",
            "edge_type",
            unique=True,
        ),
    )
