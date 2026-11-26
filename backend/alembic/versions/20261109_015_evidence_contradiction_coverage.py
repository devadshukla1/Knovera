"""Create evidence validation, contradiction detection, and document coverage tables (Phase 10 C10.7, C10.8, C10.9).

Revision ID: 20261109_015
Revises: 20261109_014
Create Date: 2026-11-09 11:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261109_015"
down_revision: Union[str, None] = "20261109_014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. research_evidence_validations (C10.7)
    op.create_table(
        "research_evidence_validations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("claim_type", sa.String(length=50), server_default="finding", nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=True),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("target_chunk_id", sa.Uuid(), nullable=True),
        sa.Column("target_page_number", sa.Integer(), nullable=True),
        sa.Column("target_section", sa.String(length=255), nullable=True),
        sa.Column("validation_status", sa.String(length=50), server_default="unvalidated", nullable=False),
        sa.Column("validation_tier", sa.String(length=40), server_default="tier_1_exact_span", nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("exact_match", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("normalized_overlap", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("numeric_match", sa.Boolean(), nullable=True),
        sa.Column("qualifier_match", sa.Boolean(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("supporting_text_excerpt", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("validation_metadata", sa.JSON(), nullable=False),
        sa.Column("is_stale", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rev_workspace_status", "research_evidence_validations", ["workspace_id", "validation_status"])
    op.create_index("ix_rev_doc_claim", "research_evidence_validations", ["document_id", "claim_id"])

    # 2. research_contradictions (C10.8)
    op.create_table(
        "research_contradictions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("comparison_id", sa.Uuid(), nullable=True),
        sa.Column("finding_a_id", sa.Uuid(), nullable=False),
        sa.Column("finding_b_id", sa.Uuid(), nullable=False),
        sa.Column("document_a_id", sa.Uuid(), nullable=False),
        sa.Column("document_b_id", sa.Uuid(), nullable=False),
        sa.Column("contradiction_category", sa.String(length=50), server_default="direct_contradiction_candidate", nullable=False),
        sa.Column("evidence_validity_a", sa.String(length=40), server_default="unvalidated", nullable=False),
        sa.Column("evidence_validity_b", sa.String(length=40), server_default="unvalidated", nullable=False),
        sa.Column("comparability_status", sa.String(length=40), server_default="comparable", nullable=False),
        sa.Column("contextual_differences", sa.JSON(), nullable=False),
        sa.Column("stage_breakdown", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("nli_relation", sa.String(length=30), nullable=True),
        sa.Column("review_status", sa.String(length=40), server_default="candidate", nullable=False),
        sa.Column("human_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["research_comparisons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_a_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_b_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["finding_a_id"], ["research_findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["finding_b_id"], ["research_findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rc_ws_review", "research_contradictions", ["workspace_id", "review_status"])
    op.create_index("ix_rc_findings_pair", "research_contradictions", ["finding_a_id", "finding_b_id"])

    # 3. research_contradiction_reviews (C10.8)
    op.create_table(
        "research_contradiction_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contradiction_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("previous_status", sa.String(length=40), nullable=False),
        sa.Column("new_status", sa.String(length=40), nullable=False),
        sa.Column("review_action", sa.String(length=40), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["contradiction_id"], ["research_contradictions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rcr_contradiction", "research_contradiction_reviews", ["contradiction_id"])

    # 4. document_coverage_runs (C10.9)
    op.create_table(
        "document_coverage_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_ids", sa.JSON(), nullable=False),
        sa.Column("total_documents", sa.Integer(), nullable=False),
        sa.Column("analysis_snapshot", sa.JSON(), nullable=False),
        sa.Column("coverage_matrix", sa.JSON(), nullable=False),
        sa.Column("gap_summary", sa.JSON(), nullable=False),
        sa.Column("corpus_only_scope", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dcr_workspace", "document_coverage_runs", ["workspace_id"])

    # 5. document_coverage_gaps (C10.9)
    op.create_table(
        "document_coverage_gaps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("gap_type", sa.String(length=50), server_default="corpus_coverage_gap", nullable=False),
        sa.Column("dimension", sa.String(length=50), server_default="topic", nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("affected_documents", sa.JSON(), nullable=False),
        sa.Column("candidate_research_direction", sa.Text(), nullable=True),
        sa.Column("suggested_inquiries", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["document_coverage_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dcg_run_dimension", "document_coverage_gaps", ["run_id", "dimension"])


def downgrade() -> None:
    op.drop_table("document_coverage_gaps")
    op.drop_table("document_coverage_runs")
    op.drop_table("research_contradiction_reviews")
    op.drop_table("research_contradictions")
    op.drop_table("research_evidence_validations")
