"""DocumentChunk ORM model for Knovera Phase 2."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import (
    BigInteger,
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
    from backend.app.models.document import Document
    from backend.app.models.workspace import Workspace


class DocumentChunk(Base):
    """DocumentChunk entity according to docs/schema.md Section 4.3 and Phase 2 spec."""

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
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
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )  # 0-based sequential ordering within document/version
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )  # Authoritative cleaned chunk text
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )  # SHA-256
    page_start: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )  # 1-based page number for PDF
    page_end: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )  # >= page_start
    slide_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )  # 1-based slide number for PPTX
    section_title: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    source_start_offset: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    source_end_offset: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    token_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    token_count_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        default="estimate_v1",
        nullable=True,
    )
    parser_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    cleaning_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    chunking_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    source_segments: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        default=list,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            "chunking_version",
            name="uq_document_chunks_index",
        ),
        Index("ix_document_chunks_workspace_doc", "workspace_id", "document_id"),
        Index("ix_document_chunks_doc_version", "document_id", "chunking_version"),
        Index("ix_document_chunks_doc_page", "document_id", "page_start"),
    )
