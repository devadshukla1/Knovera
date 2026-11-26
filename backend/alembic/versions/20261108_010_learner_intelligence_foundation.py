"""Create question_concept_mappings and learner_interaction_events tables (Phase 9 C9.1-C9.3).

Revision ID: 20261108_010
Revises: 20261108_009
Create Date: 2026-11-08 10:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261108_010"
down_revision: Union[str, None] = "20261108_009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. question_concept_mappings
    op.create_table(
        "question_concept_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("question_type", sa.String(length=50), server_default="mcq", nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_method", sa.String(length=50), server_default="explicit_metadata", nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("validation_status", sa.String(length=50), server_default="candidate", nullable=False),
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", "concept_id", name="uq_question_concept"),
    )
    op.create_index("ix_question_concept_mappings_workspace_id", "question_concept_mappings", ["workspace_id"])
    op.create_index("ix_question_concept_mappings_question_id", "question_concept_mappings", ["question_id"])
    op.create_index("ix_question_concept_mappings_concept_id", "question_concept_mappings", ["concept_id"])
    op.create_index("ix_question_concept_mappings_validation_status", "question_concept_mappings", ["validation_status"])
    op.create_index("ix_qcm_workspace_concept", "question_concept_mappings", ["workspace_id", "concept_id"])
    op.create_index("ix_qcm_question_validation", "question_concept_mappings", ["question_id", "validation_status"])

    # 2. learner_interaction_events
    op.create_table(
        "learner_interaction_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("question_id", sa.Uuid(), nullable=True),
        sa.Column("concept_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("client_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("schema_version", sa.String(length=20), server_default="1.0.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["quiz_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["knowledge_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learner_interaction_events_workspace_id", "learner_interaction_events", ["workspace_id"])
    op.create_index("ix_learner_interaction_events_user_id", "learner_interaction_events", ["user_id"])
    op.create_index("ix_learner_interaction_events_attempt_id", "learner_interaction_events", ["attempt_id"])
    op.create_index("ix_learner_interaction_events_question_id", "learner_interaction_events", ["question_id"])
    op.create_index("ix_learner_interaction_events_concept_id", "learner_interaction_events", ["concept_id"])
    op.create_index("ix_learner_interaction_events_event_type", "learner_interaction_events", ["event_type"])
    op.create_index("ix_learner_interaction_events_occurred_at", "learner_interaction_events", ["occurred_at"])
    op.create_index("ix_learner_interaction_events_idempotency_key", "learner_interaction_events", ["idempotency_key"])
    op.create_index("ix_lie_attempt_occurred", "learner_interaction_events", ["attempt_id", "occurred_at"])
    op.create_index("ix_lie_user_occurred", "learner_interaction_events", ["user_id", "occurred_at"])
    op.create_index("ix_lie_workspace_type", "learner_interaction_events", ["workspace_id", "event_type"])


def downgrade() -> None:
    op.drop_table("learner_interaction_events")
    op.drop_table("question_concept_mappings")
