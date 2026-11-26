"""KnowledgeRelationship ORM model for Knovera Knowledge Graph (Phase 7)."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.knowledge_extraction_run import KnowledgeExtractionRun
    from backend.app.models.knowledge_node import KnowledgeNode
    from backend.app.models.relationship_evidence import RelationshipEvidence
    from backend.app.models.workspace import Workspace


class KnowledgeRelationship(Base):
    """Represents a typed directional relationship between two knowledge nodes."""

    __tablename__ = "knowledge_relationships"

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
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,  # e.g. "uses", "is_a", "part_of"
        index=True,
    )
    inverse_relation_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    is_negated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    modality: Mapped[str] = mapped_column(
        String(50),
        default="certain",
        nullable=False,  # "certain", "hypothetical", "uncertain"
    )
    qualifiers: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    extraction_method: Mapped[str] = mapped_column(
        String(50),
        default="deterministic",
        nullable=False,
    )
    validation_status: Mapped[str] = mapped_column(
        String(50),
        default="valid",
        nullable=False,  # "valid", "unverified", "rejected"
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
        back_populates="relationships",
    )
    source_node: Mapped["KnowledgeNode"] = relationship(
        "KnowledgeNode",
        foreign_keys=[source_node_id],
        back_populates="source_relationships",
    )
    target_node: Mapped["KnowledgeNode"] = relationship(
        "KnowledgeNode",
        foreign_keys=[target_node_id],
        back_populates="target_relationships",
    )
    evidence_records: Mapped[List["RelationshipEvidence"]] = relationship(
        "RelationshipEvidence",
        back_populates="relationship",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "source_node_id",
            "target_node_id",
            "relation_type",
            "is_negated",
            name="uq_knowledge_rels_triple",
        ),
        Index("ix_knowledge_rels_pair", "workspace_id", "source_node_id", "target_node_id"),
    )
