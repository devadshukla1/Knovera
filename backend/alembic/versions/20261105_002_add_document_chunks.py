"""Add document_chunks table and indexes for semantic chunking.

Revision ID: 20261105_002
Revises: 20261105_001
Create Date: 2026-11-05 21:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261105_002"
down_revision: Union[str, None] = "20261105_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("slide_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.Text(), nullable=True),
        sa.Column("source_start_offset", sa.BigInteger(), nullable=True),
        sa.Column("source_end_offset", sa.BigInteger(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("token_count_method", sa.String(length=50), server_default="estimate_v1", nullable=True),
        sa.Column("parser_version", sa.String(length=100), nullable=False),
        sa.Column("cleaning_version", sa.String(length=100), nullable=False),
        sa.Column("chunking_version", sa.String(length=100), nullable=False),
        sa.Column("source_segments", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", "chunking_version", name="uq_document_chunks_index"),
    )
    op.create_index("ix_document_chunks_workspace_doc", "document_chunks", ["workspace_id", "document_id"], unique=False)
    op.create_index("ix_document_chunks_doc_version", "document_chunks", ["document_id", "chunking_version"], unique=False)
    op.create_index("ix_document_chunks_doc_page", "document_chunks", ["document_id", "page_start"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_chunks_doc_page", table_name="document_chunks")
    op.drop_index("ix_document_chunks_doc_version", table_name="document_chunks")
    op.drop_index("ix_document_chunks_workspace_doc", table_name="document_chunks")
    op.drop_table("document_chunks")
