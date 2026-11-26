"""Workspace ORM model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.user import User
    from backend.app.models.document import Document
    from backend.app.models.conversation import Conversation


class Workspace(Base):
    """Personal workspace entity according to docs/schema.md Section 3.3."""

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
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

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="workspaces",
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_workspaces_owner_updated", "owner_user_id", "updated_at"),
    )
