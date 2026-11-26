"""Create revision_recommendations and bkt_evaluation_runs tables (Phase 9 C9.7, C9.8, C9.9).

Revision ID: 20261108_012
Revises: 20261108_011
Create Date: 2026-11-08 19:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261108_012"
down_revision: Union[str, None] = "20261108_011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. revision_recommendations table (C9.7)
    op.create_table(
        "revision_recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_type", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence_summary", sa.JSON(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="suggested", nullable=False),
        sa.Column("linked_resources", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_version_id"], ["bkt_model_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rev_rec_workspace_user", "revision_recommendations", ["workspace_id", "user_id"])
    op.create_index("ix_rev_rec_user_status", "revision_recommendations", ["user_id", "status"])
    op.create_index("ix_rev_rec_concept", "revision_recommendations", ["concept_id"])
    op.create_index("ix_rev_rec_recommendation_type", "revision_recommendations", ["recommendation_type"])
    op.create_index("ix_rev_rec_priority", "revision_recommendations", ["priority"])

    # 2. bkt_evaluation_runs table (C9.9)
    op.create_table(
        "bkt_evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("split_method", sa.String(length=50), server_default="learner_holdout", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="running", nullable=False),
        sa.Column("readiness_status", sa.String(length=50), server_default="not_evaluated", nullable=False),
        sa.Column("num_learners", sa.Integer(), server_default="0", nullable=False),
        sa.Column("num_sequences", sa.Integer(), server_default="0", nullable=False),
        sa.Column("num_observations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("log_loss", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("brier_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("accuracy", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("auc_roc", sa.Float(), nullable=True),
        sa.Column("calibration_metrics", sa.JSON(), nullable=False),
        sa.Column("baseline_metrics", sa.JSON(), nullable=False),
        sa.Column("parameter_stability", sa.JSON(), nullable=False),
        sa.Column("readiness_notes", sa.Text(), nullable=True),
        sa.Column("evaluated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_version_id"], ["bkt_model_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bkt_eval_workspace_model", "bkt_evaluation_runs", ["workspace_id", "model_version_id"])
    op.create_index("ix_bkt_eval_readiness", "bkt_evaluation_runs", ["readiness_status"])
    op.create_index("ix_bkt_eval_status", "bkt_evaluation_runs", ["status"])


def downgrade() -> None:
    op.drop_table("bkt_evaluation_runs")
    op.drop_table("revision_recommendations")
