"""KnowledgeMention ORM model for Knovera Knowledge Graph (Phase 7)."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.document_chunk import DocumentChunk
    from backend.app.models.knowledge_node import KnowledgeNode
    from backend.app.models.workspace import Workspace


class KnowledgeMention(Base):
    """Represents a verified surface text mention of a node in a document chunk."""

    __tablename__ = "knowledge_mentions"

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
    node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    surface_form: Mapped[str] = mapped_column(
        String(255),
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
    extraction_method: Mapped[str] = mapped_column(
        String(50),
        default="deterministic",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    node: Mapped["KnowledgeNode"] = relationship(
        "KnowledgeNode",
        back_populates="mentions",
    )
    chunk: Mapped[Optional["DocumentChunk"]] = relationship("DocumentChunk")

    __table_args__ = (
        Index("ix_knowledge_mentions_chunk_span", "chunk_id", "start_offset", "end_offset"),
    )
