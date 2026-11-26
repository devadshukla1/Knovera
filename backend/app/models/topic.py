"""Topic ORM model for Knovera Topic Discovery (Phase 6 C6.6)."""

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
    from backend.app.models.topic_assignment import TopicAssignment
    from backend.app.models.topic_clustering_run import TopicClusteringRun
    from backend.app.models.workspace import Workspace


class Topic(Base):
    """Represents an individual discovered semantic topic/cluster within a clustering run."""

    __tablename__ = "topics"

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
    clustering_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("topic_clustering_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cluster_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,  # e.g. "cluster_0", "cluster_1"
    )
    label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    label_source: Mapped[str] = mapped_column(
        String(50),
        default="keyword_based",
        nullable=False,  # "keyword_based", "llm_assisted", "human_reviewed"
    )
    label_status: Mapped[str] = mapped_column(
        String(50),
        default="suggested",
        nullable=False,  # "suggested", "reviewed", "approved", "needs_review"
    )
    keywords: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,  # list of {"term": str, "score": float}
    )
    representative_chunk_ids: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,  # ordered list of top representative chunk UUID strings
    )
    cluster_statistics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,  # size, proportion, min/mean/max distance
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
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
    )
    clustering_run: Mapped["TopicClusteringRun"] = relationship(
        "TopicClusteringRun",
        back_populates="topics",
    )
    assignments: Mapped[List["TopicAssignment"]] = relationship(
        "TopicAssignment",
        back_populates="topic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "clustering_run_id",
            "cluster_key",
            name="uq_topics_run_cluster_key",
        ),
    )
