"""Create conversations, messages, and citations tables.

Revision ID: 20261106_004
Revises: 20261105_003
Create Date: 2026-11-06 16:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261106_004"
down_revision: Union[str, None] = "20261105_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source_scope", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_workspace_id", "conversations", ["workspace_id"], unique=False)
    op.create_index("ix_conversations_created_by_user_id", "conversations", ["created_by_user_id"], unique=False)
    op.create_index("ix_conversations_workspace_updated", "conversations", ["workspace_id", "updated_at"], unique=False)

    # 2. Create messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="complete", nullable=False),
        sa.Column("client_request_id", sa.Uuid(), nullable=True),
        sa.Column("in_reply_to_message_id", sa.Uuid(), nullable=True),
        sa.Column("model_provider", sa.String(length=80), nullable=True),
        sa.Column("model_name", sa.String(length=160), nullable=True),
        sa.Column("retrieval_metadata", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        sa.CheckConstraint("status IN ('pending', 'complete', 'failed')", name="ck_messages_status"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["in_reply_to_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_workspace_id", "messages", ["workspace_id"], unique=False)
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], unique=False)
    op.create_index("ix_messages_client_request_id", "messages", ["client_request_id"], unique=False)
    op.create_index("ix_messages_conv_created_id", "messages", ["conversation_id", "created_at", "id"], unique=False)
    op.create_index("ix_messages_workspace_created", "messages", ["workspace_id", "created_at"], unique=False)
    op.create_index(
        "uq_messages_conversation_client_req",
        "messages",
        ["conversation_id", "client_request_id"],
        unique=True,
        postgresql_where=sa.text("client_request_id IS NOT NULL"),
        sqlite_where=sa.text("client_request_id IS NOT NULL"),
    )

    # 3. Create citations table
    op.create_table(
        "citations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("claim_index", sa.Integer(), nullable=True),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("quote_text", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_citations_workspace_id", "citations", ["workspace_id"], unique=False)
    op.create_index("ix_citations_message_id", "citations", ["message_id"], unique=False)
    op.create_index("ix_citations_chunk_id", "citations", ["chunk_id"], unique=False)
    op.create_index("ix_citations_message_display", "citations", ["message_id", "display_order"], unique=False)
    op.create_index("ix_citations_workspace_created", "citations", ["workspace_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("citations")
    op.drop_table("messages")
    op.drop_table("conversations")
