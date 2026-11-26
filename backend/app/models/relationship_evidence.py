"""RelationshipEvidence ORM model for Knovera Knowledge Graph (Phase 7)."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from sqlalchemy.types import Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.document_chunk import DocumentChunk
    from backend.app.models.knowledge_relationship import KnowledgeRelationship
    from backend.app.models.workspace import Workspace


class RelationshipEvidence(Base):
    """Represents a specific source chunk and offset evidence span supporting a relationship."""

    __tablename__ = "relationship_evidence"

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
    relationship_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_relationships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    evidence_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    start_offset: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    end_offset: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = orm_relationship("Workspace")
    relationship: Mapped["KnowledgeRelationship"] = orm_relationship(
        "KnowledgeRelationship",
        back_populates="evidence_records",
    )
    chunk: Mapped[Optional["DocumentChunk"]] = orm_relationship("DocumentChunk")

    __table_args__ = (
        Index("ix_rel_evidence_chunk_span", "chunk_id", "start_offset", "end_offset"),
    )
