"""KnowledgeNode ORM model for Knovera Knowledge Graph (Phase 7)."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.knowledge_extraction_run import KnowledgeExtractionRun
    from backend.app.models.knowledge_mention import KnowledgeMention
    from backend.app.models.knowledge_relationship import KnowledgeRelationship
    from backend.app.models.workspace import Workspace


class KnowledgeNode(Base):
    """Represents a canonical knowledge graph entity or concept node."""

    __tablename__ = "knowledge_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("knowledge_extraction_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    node_type: Mapped[str] = mapped_column(
        String(50),
        default="concept",
        nullable=False,  # "concept" or "entity"
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,  # from ontology
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    normalized_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    aliases: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    extraction_run: Mapped[Optional["KnowledgeExtractionRun"]] = relationship(
        "KnowledgeExtractionRun",
        back_populates="nodes",
    )
    mentions: Mapped[List["KnowledgeMention"]] = relationship(
        "KnowledgeMention",
        back_populates="node",
        cascade="all, delete-orphan",
    )
    source_relationships: Mapped[List["KnowledgeRelationship"]] = relationship(
        "KnowledgeRelationship",
        foreign_keys="KnowledgeRelationship.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    target_relationships: Mapped[List["KnowledgeRelationship"]] = relationship(
        "KnowledgeRelationship",
        foreign_keys="KnowledgeRelationship.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "normalized_name",
            "category",
            name="uq_knowledge_nodes_workspace_key",
        ),
        Index("ix_knowledge_nodes_workspace_type", "workspace_id", "node_type"),
    )
