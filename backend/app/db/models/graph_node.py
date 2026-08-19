"""
Cartographer — GraphNode ORM Model.

Each node represents an AST entity extracted from the repository:
  - Module / file
  - Class
  - Function / method
  - Import statement
  - Variable (top-level)

Nodes carry rich metadata (e.g. docstring, signature, line range)
stored in JSONB for flexible schema evolution.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.graph_edge import GraphEdge
    from app.db.models.repository import Repository


class NodeType(str):
    """Types of AST nodes stored in the knowledge graph."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    IMPORT = "import"
    VARIABLE = "variable"
    DECORATOR = "decorator"


class GraphNode(Base):
    """
    An AST-derived node in the repository knowledge graph.

    The combination of (repository_id, file_path, name, node_type)
    is a natural key, but we use a UUID PK for flexibility.
    """

    __tablename__ = "graph_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # AST identity
    node_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    qualified_name: Mapped[str | None] = mapped_column(
        Text, nullable=True, index=True
    )  # e.g. "mypackage.utils.MyClass.my_method"

    # Source location
    file_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)

    # Rich metadata stored as JSONB for schema-free evolution
    # e.g. {"signature": "def foo(x: int) -> str", "docstring": "...",
    #        "decorators": ["@staticmethod"], "is_async": true}
    node_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    repository: Mapped[Repository] = relationship("Repository", back_populates="graph_nodes")
    outgoing_edges: Mapped[list[GraphEdge]] = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[list[GraphEdge]] = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.target_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_graph_nodes_repo_type", "repository_id", "node_type"),
        Index("ix_graph_nodes_repo_file", "repository_id", "file_path"),
        # GIN index on metadata for fast JSONB key lookups
        Index(
            "ix_graph_nodes_metadata_gin",
            "metadata",
            postgresql_using="gin",
        ),
    )
