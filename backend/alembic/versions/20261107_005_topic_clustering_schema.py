"""Create topic clustering runs, topics, and topic assignments tables (Phase 6 C6.6).

Revision ID: 20261107_005
Revises: 20261106_004
Create Date: 2026-11-07 10:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261107_005"
down_revision: Union[str, None] = "20261106_004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create topic_clustering_runs table
    op.create_table(
        "topic_clustering_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="queued", nullable=False),
        sa.Column("algorithm", sa.String(length=50), server_default="kmeans", nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("embedding_model_id", sa.String(length=150), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("k", sa.Integer(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("evaluation_metrics", sa.JSON(), nullable=False),
        sa.Column("selection_metadata", sa.JSON(), nullable=False),
        sa.Column("model_artifact_path", sa.String(length=512), nullable=True),
        sa.Column("corpus_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_topic_clustering_runs_workspace_id", "topic_clustering_runs", ["workspace_id"], unique=False)
    op.create_index("ix_topic_clustering_runs_snapshot_id", "topic_clustering_runs", ["snapshot_id"], unique=False)
    op.create_index("ix_topic_clustering_runs_status", "topic_clustering_runs", ["status"], unique=False)
    op.create_index("ix_topic_clustering_runs_ws_created", "topic_clustering_runs", ["workspace_id", "created_at"], unique=False)
    op.create_index("ix_topic_clustering_runs_ws_active", "topic_clustering_runs", ["workspace_id", "is_active"], unique=False)

    # 2. Create topics table
    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("clustering_run_id", sa.Uuid(), nullable=False),
        sa.Column("cluster_key", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("label_source", sa.String(length=50), server_default="keyword_based", nullable=False),
        sa.Column("label_status", sa.String(length=50), server_default="suggested", nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("representative_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("cluster_statistics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["clustering_run_id"], ["topic_clustering_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clustering_run_id", "cluster_key", name="uq_topics_run_cluster_key"),
    )
    op.create_index("ix_topics_workspace_id", "topics", ["workspace_id"], unique=False)
    op.create_index("ix_topics_clustering_run_id", "topics", ["clustering_run_id"], unique=False)

    # 3. Create topic_assignments table
    op.create_table(
        "topic_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("clustering_run_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("distance_to_centroid", sa.Float(), nullable=True),
        sa.Column("is_representative", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clustering_run_id"], ["topic_clustering_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clustering_run_id", "chunk_id", name="uq_topic_assignments_run_chunk"),
    )
    op.create_index("ix_topic_assignments_ws_run", "topic_assignments", ["workspace_id", "clustering_run_id"], unique=False)
    op.create_index("ix_topic_assignments_topic_id", "topic_assignments", ["topic_id"], unique=False)
    op.create_index("ix_topic_assignments_chunk_id", "topic_assignments", ["chunk_id"], unique=False)
    op.create_index("ix_topic_assignments_document_id", "topic_assignments", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_table("topic_assignments")
    op.drop_table("topics")
    op.drop_table("topic_clustering_runs")
