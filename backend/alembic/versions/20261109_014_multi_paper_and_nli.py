"""Create multi-paper comparison, findings, and NLI tables (Phase 10 C10.4, C10.5, C10.6).

Revision ID: 20261109_014
Revises: 20261109_013
Create Date: 2026-11-09 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261109_014"
down_revision: Union[str, None] = "20261109_013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. research_comparisons (C10.4)
    op.create_table(
        "research_comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), server_default="Research Comparison", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("document_ids", sa.JSON(), nullable=False),
        sa.Column("document_versions", sa.JSON(), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("matrix", sa.JSON(), nullable=False),
        sa.Column("difference_summaries", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="completed", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_res_comp_ws_status", "research_comparisons", ["workspace_id", "status"])

    # 2. research_findings (C10.5)
    op.create_table(
        "research_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_version", sa.String(length=50), server_default="v1.0", nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("finding_type", sa.String(length=50), nullable=False),
        sa.Column("original_statement", sa.Text(), nullable=False),
        sa.Column("normalized_statement", sa.Text(), nullable=False),
        sa.Column("outcome_variable", sa.String(length=255), nullable=True),
        sa.Column("objective_relationship", sa.String(length=255), nullable=True),
        sa.Column("method_relationship", sa.String(length=255), nullable=True),
        sa.Column("dataset_relationship", sa.String(length=255), nullable=True),
        sa.Column("population", sa.String(length=255), nullable=True),
        sa.Column("experimental_condition", sa.Text(), nullable=True),
        sa.Column("comparator", sa.String(length=255), nullable=True),
        sa.Column("metric", sa.String(length=100), nullable=True),
        sa.Column("reported_value", sa.String(length=100), nullable=True),
        sa.Column("numeric_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("direction", sa.String(length=30), server_default="positive", nullable=True),
        sa.Column("statistical_significance", sa.String(length=100), nullable=True),
        sa.Column("confidence_interval", sa.String(length=100), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("extraction_status", sa.String(length=30), server_default="extracted", nullable=False),
        sa.Column("validation_status", sa.String(length=30), server_default="validated", nullable=False),
        sa.Column("is_manually_edited", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["research_analysis_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_res_finding_ws_doc", "research_findings", ["workspace_id", "document_id"])
    op.create_index("ix_res_finding_metric", "research_findings", ["workspace_id", "metric"])

    # 3. nli_inference_records (C10.6)
    op.create_table(
        "nli_inference_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("model_revision", sa.String(length=64), server_default="main", nullable=False),
        sa.Column("pair_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("premise_hash", sa.String(length=64), nullable=False),
        sa.Column("hypothesis_hash", sa.String(length=64), nullable=False),
        sa.Column("premise_text", sa.Text(), nullable=False),
        sa.Column("hypothesis_text", sa.Text(), nullable=False),
        sa.Column("premise_source_doc_id", sa.Uuid(), nullable=True),
        sa.Column("hypothesis_source_doc_id", sa.Uuid(), nullable=True),
        sa.Column("forward_label", sa.String(length=30), nullable=False),
        sa.Column("forward_scores", sa.JSON(), nullable=False),
        sa.Column("backward_label", sa.String(length=30), nullable=True),
        sa.Column("backward_scores", sa.JSON(), nullable=True),
        sa.Column("aggregated_label", sa.String(length=30), nullable=False),
        sa.Column("margin", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("abstained", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("confidence_level", sa.String(length=30), server_default="moderate", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nli_records_pair_fp", "nli_inference_records", ["pair_fingerprint"])
    op.create_index("ix_nli_records_ws", "nli_inference_records", ["workspace_id"])

    # 4. research_finding_comparisons (C10.5 & C10.6)
    op.create_table(
        "research_finding_comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("comparison_id", sa.Uuid(), nullable=False),
        sa.Column("finding_a_id", sa.Uuid(), nullable=False),
        sa.Column("finding_b_id", sa.Uuid(), nullable=False),
        sa.Column("outcome_variable", sa.String(length=255), nullable=True),
        sa.Column("comparability_status", sa.String(length=50), server_default="comparable", nullable=False),
        sa.Column("preliminary_relationship", sa.String(length=50), server_default="pending_nli", nullable=False),
        sa.Column("comparison_rationale", sa.Text(), nullable=True),
        sa.Column("contextual_differences", sa.JSON(), nullable=False),
        sa.Column("nli_relation", sa.String(length=50), nullable=True),
        sa.Column("nli_inference_record_id", sa.Uuid(), nullable=True),
        sa.Column("final_relation", sa.String(length=50), server_default="pending_nli", nullable=False),
        sa.Column("validation_status", sa.String(length=30), server_default="validated", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["research_comparisons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["finding_a_id"], ["research_findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["finding_b_id"], ["research_findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["nli_inference_record_id"], ["nli_inference_records.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_res_finding_comp_pair", "research_finding_comparisons", ["comparison_id", "finding_a_id", "finding_b_id"])

    # 5. nli_evaluation_runs (C10.6)
    op.create_table(
        "nli_evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("model_revision", sa.String(length=64), server_default="main", nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=False),
        sa.Column("macro_f1", sa.Float(), nullable=False),
        sa.Column("per_class_f1", sa.JSON(), nullable=False),
        sa.Column("precision_recall_by_class", sa.JSON(), nullable=False),
        sa.Column("confusion_matrix", sa.JSON(), nullable=False),
        sa.Column("abstention_rate", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("is_readiness_passed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nli_eval_model", "nli_evaluation_runs", ["model_id", "model_revision"])


def downgrade() -> None:
    op.drop_table("nli_evaluation_runs")
    op.drop_table("research_finding_comparisons")
    op.drop_table("nli_inference_records")
    op.drop_table("research_findings")
    op.drop_table("research_comparisons")
