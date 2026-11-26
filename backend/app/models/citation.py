"""Citation ORM model according to docs/schema.md Section 5.3."""

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
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.document_chunk import DocumentChunk
    from backend.app.models.message import Message
    from backend.app.models.workspace import Workspace


class Citation(Base):
    """Citation entity mapping assistant message claims to authoritative document chunks."""

    __tablename__ = "citations"

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
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    quote_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    relevance_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="citations")
    chunk: Mapped["DocumentChunk"] = relationship("DocumentChunk")
    workspace: Mapped["Workspace"] = relationship("Workspace")

    __table_args__ = (
        Index("ix_citations_message_display", "message_id", "display_order"),
        Index("ix_citations_workspace_created", "workspace_id", "created_at"),
    )
