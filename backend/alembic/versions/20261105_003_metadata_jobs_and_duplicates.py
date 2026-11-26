"""Add metadata columns, ingestion_jobs table, and duplicate constraint.

Revision ID: 20261105_003
Revises: 20261105_002
Create Date: 2026-11-05 21:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261105_003"
down_revision: Union[str, None] = "20261105_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add metadata columns to documents table
    op.add_column("documents", sa.Column("slide_count", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("extracted_block_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("documents", sa.Column("total_characters", sa.Integer(), server_default="0", nullable=False))
    op.add_column("documents", sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("documents", sa.Column("pipeline_version", sa.String(length=40), server_default="v1.0", nullable=False))

    # 2. Add unique partial index for workspace-scoped duplicate detection
    op.create_index(
        "uq_documents_workspace_sha256_active",
        "documents",
        ["workspace_id", "sha256"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    # 3. Create ingestion_jobs table
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=40), server_default="document_ingestion", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("processing_metrics", sa.JSON(), nullable=True),
        sa.Column("pipeline_version", sa.String(length=40), server_default="v1.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_jobs_status_available", "ingestion_jobs", ["status", "available_at"], unique=False)
    op.create_index("ix_ingestion_jobs_document_created", "ingestion_jobs", ["document_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_document_created", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_status_available", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index("uq_documents_workspace_sha256_active", table_name="documents")
    op.drop_column("documents", "pipeline_version")
    op.drop_column("documents", "chunk_count")
    op.drop_column("documents", "total_characters")
    op.drop_column("documents", "extracted_block_count")
    op.drop_column("documents", "slide_count")
