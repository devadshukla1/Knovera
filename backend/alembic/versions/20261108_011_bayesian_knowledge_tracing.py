"""Create BKT tables: bkt_model_versions, bkt_estimation_runs, learner_concept_mastery, learner_concept_mastery_history (Phase 9 C9.4-C9.6).

Revision ID: 20261108_011
Revises: 20261108_010
Create Date: 2026-11-08 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261108_011"
down_revision: Union[str, None] = "20261108_010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. bkt_model_versions
    op.create_table(
        "bkt_model_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("model_scope", sa.String(length=50), server_default="global", nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=True),
        sa.Column("p_init", sa.Float(), server_default="0.30", nullable=False),
        sa.Column("p_transit", sa.Float(), server_default="0.15", nullable=False),
        sa.Column("p_guess", sa.Float(), server_default="0.20", nullable=False),
        sa.Column("p_slip", sa.Float(), server_default="0.10", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="candidate", nullable=False),
        sa.Column("training_observation_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("training_sequence_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("validation_metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["knowledge_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_version", name="uq_bkt_model_version"),
    )
    op.create_index("ix_bkt_model_versions_workspace_id", "bkt_model_versions", ["workspace_id"])
    op.create_index("ix_bkt_model_versions_concept_id", "bkt_model_versions", ["concept_id"])
    op.create_index("ix_bkt_model_versions_status", "bkt_model_versions", ["status"])
    op.create_index("ix_bkt_model_versions_model_scope", "bkt_model_versions", ["model_scope"])

    # 2. bkt_estimation_runs
    op.create_table(
        "bkt_estimation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=True),
        sa.Column("concept_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="running", nullable=False),
        sa.Column("num_learners", sa.Integer(), server_default="0", nullable=False),
        sa.Column("num_sequences", sa.Integer(), server_default="0", nullable=False),
        sa.Column("num_observations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("converged", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("iterations_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("final_log_likelihood", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("initial_params", sa.JSON(), nullable=False),
        sa.Column("fitted_params", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_version_id"], ["bkt_model_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["concept_id"], ["knowledge_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bkt_estimation_runs_workspace_id", "bkt_estimation_runs", ["workspace_id"])
    op.create_index("ix_bkt_estimation_runs_concept_id", "bkt_estimation_runs", ["concept_id"])
    op.create_index("ix_bkt_estimation_runs_status", "bkt_estimation_runs", ["status"])

    # 3. learner_concept_mastery
    op.create_table(
        "learner_concept_mastery",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=True),
        sa.Column("posterior_mastery_probability", sa.Float(), server_default="0.30", nullable=False),
        sa.Column("predicted_next_mastery_probability", sa.Float(), server_default="0.30", nullable=False),
        sa.Column("observation_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("last_question_id", sa.Uuid(), nullable=True),
        sa.Column("last_observation_correct", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="insufficient_data", nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_version_id"], ["bkt_model_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["last_attempt_id"], ["quiz_attempts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", "concept_id", name="uq_learner_concept_mastery"),
    )
    op.create_index("ix_learner_concept_mastery_workspace_id", "learner_concept_mastery", ["workspace_id"])
    op.create_index("ix_learner_concept_mastery_user_id", "learner_concept_mastery", ["user_id"])
    op.create_index("ix_learner_concept_mastery_concept_id", "learner_concept_mastery", ["concept_id"])
    op.create_index("ix_lcm_user_workspace", "learner_concept_mastery", ["user_id", "workspace_id"])

    # 4. learner_concept_mastery_history
    op.create_table(
        "learner_concept_mastery_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("mastery_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("observation_correct", sa.Boolean(), nullable=False),
        sa.Column("prior_mastery", sa.Float(), nullable=False),
        sa.Column("posterior_mastery", sa.Float(), nullable=False),
        sa.Column("predicted_next_mastery", sa.Float(), nullable=False),
        sa.Column("p_init", sa.Float(), nullable=False),
        sa.Column("p_transit", sa.Float(), nullable=False),
        sa.Column("p_guess", sa.Float(), nullable=False),
        sa.Column("p_slip", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("sequence_index", sa.Integer(), server_default="1", nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mastery_id"], ["learner_concept_mastery.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["quiz_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "attempt_id", "question_id", "concept_id",
            name="uq_bkt_mastery_history_event",
        ),
    )
    op.create_index("ix_lcmh_user_concept_occurred", "learner_concept_mastery_history", ["user_id", "concept_id", "occurred_at"])
    op.create_index("ix_learner_concept_mastery_history_attempt_id", "learner_concept_mastery_history", ["attempt_id"])


def downgrade() -> None:
    op.drop_table("learner_concept_mastery_history")
    op.drop_table("learner_concept_mastery")
    op.drop_table("bkt_estimation_runs")
    op.drop_table("bkt_model_versions")
