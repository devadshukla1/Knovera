"""IngestionJob ORM model for Knovera Phase 2 (C2.6–C2.8)."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
import uuid
from sqlalchemy import (
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
    from backend.app.models.document import Document
    from backend.app.models.workspace import Workspace


class IngestionJob(Base):
    """PostgreSQL-backed durable job tracking entity per docs/schema.md Section 4.3."""

    __tablename__ = "ingestion_jobs"

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
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(
        String(40),
        default="document_ingestion",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="queued",
        nullable=False,
        index=True,
    )  # queued, running, retry_wait, completed, failed, cancelled
    stage: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    locked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    locked_by: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )
    last_error_code: Mapped[Optional[str]] = mapped_column(
        String(80),
        nullable=True,
    )
    last_error_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    processing_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    pipeline_version: Mapped[str] = mapped_column(
        String(40),
        default="v1.0",
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
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="jobs",
    )
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
    )

    __table_args__ = (
        Index("ix_ingestion_jobs_status_available", "status", "available_at"),
        Index("ix_ingestion_jobs_document_created", "document_id", "created_at"),
    )
