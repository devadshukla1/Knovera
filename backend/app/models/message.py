"""Message ORM model according to docs/schema.md Section 5.2."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import (
    CheckConstraint,
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
    from backend.app.models.citation import Citation
    from backend.app.models.conversation import Conversation
    from backend.app.models.workspace import Workspace


class Message(Base):
    """Message entity representing single chat turns in a conversation."""

    __tablename__ = "messages"

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
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="complete",
    )
    client_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        index=True,
    )
    in_reply_to_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_provider: Mapped[Optional[str]] = mapped_column(
        String(80),
        nullable=True,
    )
    model_name: Mapped[Optional[str]] = mapped_column(
        String(160),
        nullable=True,
    )
    retrieval_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    failure_code: Mapped[Optional[str]] = mapped_column(
        String(50),
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
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    citations: Mapped[List["Citation"]] = relationship(
        "Citation",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="Citation.display_order, Citation.id",
    )

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        CheckConstraint("status IN ('pending', 'complete', 'failed')", name="ck_messages_status"),
        Index("ix_messages_conv_created_id", "conversation_id", "created_at", "id"),
        Index("ix_messages_workspace_created", "workspace_id", "created_at"),
        Index(
            "uq_messages_conversation_client_req",
            "conversation_id",
            "client_request_id",
            unique=True,
            postgresql_where=(client_request_id.isnot(None)),
            sqlite_where=(client_request_id.isnot(None)),
        ),
    )
