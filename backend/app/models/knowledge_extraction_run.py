"""KnowledgeExtractionRun ORM model for Knovera Knowledge Graph (Phase 7)."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.knowledge_node import KnowledgeNode
    from backend.app.models.knowledge_relationship import KnowledgeRelationship
    from backend.app.models.workspace import Workspace


class KnowledgeExtractionRun(Base):
    """Tracks a discrete knowledge extraction execution on workspace chunks."""

    __tablename__ = "knowledge_extraction_runs"

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
    status: Mapped[str] = mapped_column(
        String(50),
        default="completed",
        nullable=False,  # "pending", "running", "completed", "failed"
    )
    ontology_version: Mapped[str] = mapped_column(
        String(20),
        default="1.0.0",
        nullable=False,
    )
    extraction_method: Mapped[str] = mapped_column(
        String(50),
        default="deterministic",
        nullable=False,  # "deterministic", "llm", "hybrid"
    )
    total_chunks_processed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_nodes_extracted: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_relationships_extracted: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    statistics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
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
    nodes: Mapped[List["KnowledgeNode"]] = relationship(
        "KnowledgeNode",
        back_populates="extraction_run",
        cascade="all, delete-orphan",
    )
    relationships: Mapped[List["KnowledgeRelationship"]] = relationship(
        "KnowledgeRelationship",
        back_populates="extraction_run",
        cascade="all, delete-orphan",
    )
