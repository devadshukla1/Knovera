"""Create knowledge_graph_snapshots table (Phase 7 C7.6).

Revision ID: 20261107_007
Revises: 20261107_006
Create Date: 2026-11-07 11:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261107_007"
down_revision: Union[str, None] = "20261107_006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_graph_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="completed", nullable=False),
        sa.Column("graph_schema_version", sa.String(length=20), server_default="1.0.0", nullable=False),
        sa.Column("ontology_version", sa.String(length=20), server_default="1.0.0", nullable=False),
        sa.Column("relationship_ontology_version", sa.String(length=20), server_default="1.0.0", nullable=False),
        sa.Column("builder_version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("source_snapshot_hash", sa.String(length=64), nullable=True),
        sa.Column("node_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("concept_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("entity_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("edge_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("isolated_node_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("component_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("graph_statistics", sa.JSON(), nullable=False),
        sa.Column("artifact_uri", sa.String(length=512), nullable=True),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=True),
        sa.Column("serialization_format", sa.String(length=50), server_default="json_node_link", nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("failure_reason_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["knowledge_extraction_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_graph_snapshots_workspace_id", "knowledge_graph_snapshots", ["workspace_id"], unique=False)
    op.create_index("ix_knowledge_graph_snapshots_extraction_run_id", "knowledge_graph_snapshots", ["extraction_run_id"], unique=False)
    op.create_index("ix_kg_snapshots_workspace_created", "knowledge_graph_snapshots", ["workspace_id", "created_at"], unique=False)
    op.create_index("ix_kg_snapshots_workspace_active", "knowledge_graph_snapshots", ["workspace_id", "is_active"], unique=False)


def downgrade() -> None:
    op.drop_table("knowledge_graph_snapshots")
