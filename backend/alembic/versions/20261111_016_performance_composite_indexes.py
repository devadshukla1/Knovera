"""Add performance composite indexes for high-throughput queries (Phase 11 C11.7).

Revision ID: 20261111_016
Revises: 20261109_015
Create Date: 2026-11-11 11:15:00.000000

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261111_016"
down_revision: Union[str, None] = "20261109_015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Study Materials: High-frequency question listing & quiz generation indexes
    op.create_index(
        "ix_mcq_questions_ws_active_diff",
        "mcq_questions",
        ["workspace_id", "is_active", "difficulty"],
        unique=False,
    )
    op.create_index(
        "ix_fill_blank_ws_active",
        "fill_blank_exercises",
        ["workspace_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_tf_questions_ws_active",
        "true_false_questions",
        ["workspace_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_flashcards_ws_active_type",
        "flashcards",
        ["workspace_id", "is_active", "card_type"],
        unique=False,
    )

    # 2. Interactive Assessment & Quiz Attempt Tracking
    op.create_index(
        "ix_quiz_attempts_ws_user_status",
        "quiz_attempts",
        ["workspace_id", "user_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_quiz_attempts_user_submitted",
        "quiz_attempts",
        ["user_id", "submitted_at"],
        unique=False,
    )
    op.create_index(
        "ix_quiz_attempt_answers_attempt_q",
        "quiz_attempt_answers",
        ["attempt_id", "question_id"],
        unique=False,
    )

    # 3. Research Intelligence: Workspace comparisons
    op.create_index(
        "ix_research_comparisons_ws_status",
        "research_comparisons",
        ["workspace_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_research_comparisons_ws_status", table_name="research_comparisons")
    op.drop_index("ix_quiz_attempt_answers_attempt_q", table_name="quiz_attempt_answers")
    op.drop_index("ix_quiz_attempts_user_submitted", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_ws_user_status", table_name="quiz_attempts")
    op.drop_index("ix_flashcards_ws_active_type", table_name="flashcards")
    op.drop_index("ix_tf_questions_ws_active", table_name="true_false_questions")
    op.drop_index("ix_fill_blank_ws_active", table_name="fill_blank_exercises")
    op.drop_index("ix_mcq_questions_ws_active_diff", table_name="mcq_questions")
