"""KnowledgeGraphSnapshot ORM model for Knovera Knowledge Graph (Phase 7 C7.6)."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
import uuid
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.knowledge_extraction_run import KnowledgeExtractionRun
    from backend.app.models.user import User
    from backend.app.models.workspace import Workspace


class KnowledgeGraphSnapshot(Base):
    """Represents an immutable, versioned snapshot of a constructed knowledge graph."""

    __tablename__ = "knowledge_graph_snapshots"

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
    status: Mapped[str] = mapped_column(
        String(50),
        default="completed",
        nullable=False,  # "queued", "building", "persisting", "completed", "completed_with_warnings", "failed", "stale"
    )
    graph_schema_version: Mapped[str] = mapped_column(
        String(20),
        default="1.0.0",
        nullable=False,
    )
    ontology_version: Mapped[str] = mapped_column(
        String(20),
        default="1.0.0",
        nullable=False,
    )
    relationship_ontology_version: Mapped[str] = mapped_column(
        String(20),
        default="1.0.0",
        nullable=False,
    )
    builder_version: Mapped[str] = mapped_column(
        String(50),
        default="1.0.0",
        nullable=False,
    )
    source_snapshot_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    node_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    concept_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    entity_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    edge_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    isolated_node_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    component_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    graph_statistics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    artifact_uri: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    artifact_checksum: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,  # SHA-256
    )
    serialization_format: Mapped[str] = mapped_column(
        String(50),
        default="json_node_link",
        nullable=False,
    )
    configuration: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    failure_reason_code: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    extraction_run: Mapped[Optional["KnowledgeExtractionRun"]] = relationship("KnowledgeExtractionRun")
    created_by_user: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index("ix_kg_snapshots_workspace_created", "workspace_id", "created_at"),
        Index("ix_kg_snapshots_workspace_active", "workspace_id", "is_active"),
    )
