"""Document and DocumentPage ORM models for Knovera Ingestion."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.document_chunk import DocumentChunk
    from backend.app.models.ingestion_job import IngestionJob
    from backend.app.models.user import User
    from backend.app.models.workspace import Workspace


class Document(Base):
    """Document entity according to docs/schema.md Section 4.1."""

    __tablename__ = "documents"

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
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(
        String(1024),
        unique=True,
        nullable=False,
    )
    media_type: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    file_extension: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    processing_status: Mapped[str] = mapped_column(
        String(20),
        default="queued",
        nullable=False,
        index=True,
    )
    processing_stage: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
    )
    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    slide_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    extracted_block_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_characters: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    pipeline_version: Mapped[str] = mapped_column(
        String(40),
        default="v1.0",
        nullable=False,
    )
    extraction_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(80),
        nullable=True,
    )
    error_summary: Mapped[Optional[str]] = mapped_column(
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
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="documents",
    )
    uploader: Mapped["User"] = relationship(
        "User",
        back_populates="documents",
    )
    pages: Mapped[List["DocumentPage"]] = relationship(
        "DocumentPage",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentPage.page_number",
    )
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )
    jobs: Mapped[List["IngestionJob"]] = relationship(
        "IngestionJob",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="IngestionJob.created_at.desc()",
    )

    __table_args__ = (
        Index("ix_documents_workspace_created", "workspace_id", "created_at"),
        Index("ix_documents_workspace_status", "workspace_id", "processing_status"),
        Index("ix_documents_workspace_sha256", "workspace_id", "sha256"),
    )


class DocumentPage(Base):
    """Page-level extracted text and provenance entity according to Phase 2 spec."""

    __tablename__ = "document_pages"

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
    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )  # 1-based indexing
    extracted_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    is_empty: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    warnings: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="pages",
    )

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_doc_page"),
        Index("ix_document_pages_lookup", "workspace_id", "document_id", "page_number"),
    )
