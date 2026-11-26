"""TopicAssignment ORM model for Knovera Topic Discovery (Phase 6 C6.6)."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.document import Document
    from backend.app.models.document_chunk import DocumentChunk
    from backend.app.models.topic import Topic
    from backend.app.models.topic_clustering_run import TopicClusteringRun
    from backend.app.models.workspace import Workspace


class TopicAssignment(Base):
    """Links an authoritative document chunk to an assigned topic within a clustering run."""

    __tablename__ = "topic_assignments"

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
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    distance_to_centroid: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    is_representative: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
    )
    clustering_run: Mapped["TopicClusteringRun"] = relationship(
        "TopicClusteringRun",
        back_populates="assignments",
    )
    topic: Mapped["Topic"] = relationship(
        "Topic",
        back_populates="assignments",
    )
    chunk: Mapped["DocumentChunk"] = relationship(
        "DocumentChunk",
    )
    document: Mapped["Document"] = relationship(
        "Document",
    )

    __table_args__ = (
        UniqueConstraint(
            "clustering_run_id",
            "chunk_id",
            name="uq_topic_assignments_run_chunk",
        ),
        Index("ix_topic_assignments_ws_run", "workspace_id", "clustering_run_id"),
    )
