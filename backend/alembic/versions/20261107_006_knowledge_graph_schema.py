"""Create knowledge graph extraction runs, nodes, mentions, relationships, and evidence tables (Phase 7).

Revision ID: 20261107_006
Revises: 20261107_005
Create Date: 2026-11-07 11:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261107_006"
down_revision: Union[str, None] = "20261107_005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create knowledge_extraction_runs table
    op.create_table(
        "knowledge_extraction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="completed", nullable=False),
        sa.Column("ontology_version", sa.String(length=20), server_default="1.0.0", nullable=False),
        sa.Column("extraction_method", sa.String(length=50), server_default="deterministic", nullable=False),
        sa.Column("total_chunks_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_nodes_extracted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_relationships_extracted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("statistics", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_extraction_runs_workspace_id", "knowledge_extraction_runs", ["workspace_id"], unique=False)

    # 2. Create knowledge_nodes table
    op.create_table(
        "knowledge_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=True),
        sa.Column("node_type", sa.String(length=50), server_default="concept", nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["knowledge_extraction_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "normalized_name", "category", name="uq_knowledge_nodes_workspace_key"),
    )
    op.create_index("ix_knowledge_nodes_workspace_id", "knowledge_nodes", ["workspace_id"], unique=False)
    op.create_index("ix_knowledge_nodes_normalized_name", "knowledge_nodes", ["normalized_name"], unique=False)
    op.create_index("ix_knowledge_nodes_workspace_type", "knowledge_nodes", ["workspace_id", "node_type"], unique=False)

    # 3. Create knowledge_mentions table
    op.create_table(
        "knowledge_mentions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("surface_form", sa.String(length=255), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("extraction_method", sa.String(length=50), server_default="deterministic", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_mentions_workspace_id", "knowledge_mentions", ["workspace_id"], unique=False)
    op.create_index("ix_knowledge_mentions_node_id", "knowledge_mentions", ["node_id"], unique=False)
    op.create_index("ix_knowledge_mentions_chunk_id", "knowledge_mentions", ["chunk_id"], unique=False)
    op.create_index("ix_knowledge_mentions_chunk_span", "knowledge_mentions", ["chunk_id", "start_offset", "end_offset"], unique=False)

    # 4. Create knowledge_relationships table
    op.create_table(
        "knowledge_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=True),
        sa.Column("source_node_id", sa.Uuid(), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=100), nullable=False),
        sa.Column("inverse_relation_type", sa.String(length=100), nullable=True),
        sa.Column("is_negated", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("modality", sa.String(length=50), server_default="certain", nullable=False),
        sa.Column("qualifiers", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("extraction_method", sa.String(length=50), server_default="deterministic", nullable=False),
        sa.Column("validation_status", sa.String(length=50), server_default="valid", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["knowledge_extraction_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "source_node_id", "target_node_id", "relation_type", "is_negated", name="uq_knowledge_rels_triple"),
    )
    op.create_index("ix_knowledge_relationships_workspace_id", "knowledge_relationships", ["workspace_id"], unique=False)
    op.create_index("ix_knowledge_relationships_source_node_id", "knowledge_relationships", ["source_node_id"], unique=False)
    op.create_index("ix_knowledge_relationships_target_node_id", "knowledge_relationships", ["target_node_id"], unique=False)
    op.create_index("ix_knowledge_relationships_relation_type", "knowledge_relationships", ["relation_type"], unique=False)
    op.create_index("ix_knowledge_rels_pair", "knowledge_relationships", ["workspace_id", "source_node_id", "target_node_id"], unique=False)

    # 5. Create relationship_evidence table
    op.create_table(
        "relationship_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relationship_id"], ["knowledge_relationships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_relationship_evidence_workspace_id", "relationship_evidence", ["workspace_id"], unique=False)
    op.create_index("ix_relationship_evidence_relationship_id", "relationship_evidence", ["relationship_id"], unique=False)
    op.create_index("ix_relationship_evidence_chunk_id", "relationship_evidence", ["chunk_id"], unique=False)
    op.create_index("ix_rel_evidence_chunk_span", "relationship_evidence", ["chunk_id", "start_offset", "end_offset"], unique=False)


def downgrade() -> None:
    op.drop_table("relationship_evidence")
    op.drop_table("knowledge_relationships")
    op.drop_table("knowledge_mentions")
    op.drop_table("knowledge_nodes")
    op.drop_table("knowledge_extraction_runs")
