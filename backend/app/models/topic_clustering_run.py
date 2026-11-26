"""TopicClusteringRun ORM model for Knovera Topic Discovery (Phase 6 C6.6)."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.topic import Topic
    from backend.app.models.topic_assignment import TopicAssignment
    from backend.app.models.workspace import Workspace


class TopicClusteringRun(Base):
    """Represents a discrete, versioned unsupervised clustering execution on a workspace."""

    __tablename__ = "topic_clustering_runs"

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
    snapshot_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="queued",
        nullable=False,
        index=True,  # queued, running, completed, failed
    )
    algorithm: Mapped[str] = mapped_column(
        String(50),
        default="kmeans",
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    embedding_model_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    embedding_dimension: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    k: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    configuration: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    evaluation_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    selection_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    model_artifact_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    corpus_snapshot_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
    )
    topics: Mapped[List["Topic"]] = relationship(
        "Topic",
        back_populates="clustering_run",
        cascade="all, delete-orphan",
        order_by="Topic.cluster_key",
    )
    assignments: Mapped[List["TopicAssignment"]] = relationship(
        "TopicAssignment",
        back_populates="clustering_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_topic_clustering_runs_ws_created", "workspace_id", "created_at"),
        Index("ix_topic_clustering_runs_ws_active", "workspace_id", "is_active"),
    )
