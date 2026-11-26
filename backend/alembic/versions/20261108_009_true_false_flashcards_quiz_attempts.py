"""Create true_false_questions, flashcards, and quiz_attempts tables (Phase 8 C8.4-C8.6).

Revision ID: 20261108_009
Revises: 20261107_008
Create Date: 2026-11-08 09:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261108_009"
down_revision: Union[str, None] = "20261107_008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. true_false_questions
    op.create_table(
        "true_false_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("correct_answer", sa.Boolean(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=50), server_default="medium", nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=True),
        sa.Column("validation_status", sa.String(length=50), server_default="validated", nullable=False),
        sa.Column("source_references", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_id"], ["study_material_generations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_true_false_questions_workspace_id", "true_false_questions", ["workspace_id"])
    op.create_index("ix_true_false_questions_generation_id", "true_false_questions", ["generation_id"])
    op.create_index("ix_true_false_questions_difficulty", "true_false_questions", ["difficulty"])

    # 2. flashcards
    op.create_table(
        "flashcards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("card_type", sa.String(length=50), server_default="concept", nullable=False),
        sa.Column("difficulty", sa.String(length=50), server_default="medium", nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=True),
        sa.Column("validation_status", sa.String(length=50), server_default="validated", nullable=False),
        sa.Column("source_references", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_id"], ["study_material_generations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flashcards_workspace_id", "flashcards", ["workspace_id"])
    op.create_index("ix_flashcards_generation_id", "flashcards", ["generation_id"])
    op.create_index("ix_flashcards_card_type", "flashcards", ["card_type"])
    op.create_index("ix_flashcards_difficulty", "flashcards", ["difficulty"])

    # 3. quiz_attempts
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), server_default="Interactive Quiz Attempt", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="in_progress", nullable=False),
        sa.Column("total_questions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("correct_answers_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("score_percentage", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("questions_order", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluation_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quiz_attempts_workspace_id", "quiz_attempts", ["workspace_id"])
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])
    op.create_index("ix_quiz_attempts_status", "quiz_attempts", ["status"])

    # 4. quiz_attempt_answers
    op.create_table(
        "quiz_attempt_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("question_type", sa.String(length=50), nullable=False),
        sa.Column("selected_answer", sa.JSON(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["quiz_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quiz_attempt_answers_attempt_id", "quiz_attempt_answers", ["attempt_id"])
    op.create_index("ix_quiz_attempt_answers_question_id", "quiz_attempt_answers", ["question_id"])


def downgrade() -> None:
    op.drop_table("quiz_attempt_answers")
    op.drop_table("quiz_attempts")
    op.drop_table("flashcards")
    op.drop_table("true_false_questions")
