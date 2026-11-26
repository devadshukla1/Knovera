"""Create study materials tables (Phase 8 C8.1-C8.3).

Revision ID: 20261107_008
Revises: 20261107_007
Create Date: 2026-11-07 17:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261107_008"
down_revision: Union[str, None] = "20261107_007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. study_material_generations
    op.create_table(
        "study_material_generations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("material_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="completed", nullable=False),
        sa.Column("requested_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("generated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("validated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rejected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_name", sa.String(length=100), server_default="mock", nullable=False),
        sa.Column("model_name", sa.String(length=100), server_default="mock-model", nullable=False),
        sa.Column("scope_type", sa.String(length=50), server_default="workspace", nullable=False),
        sa.Column("scope_config", sa.JSON(), nullable=True),
        sa.Column("quality_report", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_material_generations_workspace_id", "study_material_generations", ["workspace_id"])
    op.create_index("ix_study_material_generations_material_type", "study_material_generations", ["material_type"])
    op.create_index("ix_study_material_generations_status", "study_material_generations", ["status"])

    # 2. revision_notes
    op.create_table(
        "revision_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("overview", sa.Text(), nullable=False),
        sa.Column("length", sa.String(length=50), server_default="standard", nullable=False),
        sa.Column("detail_level", sa.String(length=50), server_default="intermediate", nullable=False),
        sa.Column("focus", sa.String(length=50), server_default="conceptual_learning", nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("key_concepts", sa.JSON(), nullable=False),
        sa.Column("important_points", sa.JSON(), nullable=False),
        sa.Column("formulas", sa.JSON(), nullable=False),
        sa.Column("quick_summary", sa.JSON(), nullable=False),
        sa.Column("source_references", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_id"], ["study_material_generations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_revision_notes_workspace_id", "revision_notes", ["workspace_id"])
    op.create_index("ix_revision_notes_generation_id", "revision_notes", ["generation_id"])

    # 3. mcq_questions
    op.create_table(
        "mcq_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=50), server_default="medium", nullable=False),
        sa.Column("question_type", sa.String(length=50), server_default="conceptual", nullable=False),
        sa.Column("correct_option_id", sa.String(length=10), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("topic_tags", sa.JSON(), nullable=False),
        sa.Column("source_references", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_id"], ["study_material_generations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcq_questions_workspace_id", "mcq_questions", ["workspace_id"])
    op.create_index("ix_mcq_questions_generation_id", "mcq_questions", ["generation_id"])
    op.create_index("ix_mcq_questions_difficulty", "mcq_questions", ["difficulty"])

    # 4. mcq_options
    op.create_table(
        "mcq_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("option_id", sa.String(length=10), nullable=False),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["mcq_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcq_options_question_id", "mcq_options", ["question_id"])

    # 5. fill_blank_exercises
    op.create_table(
        "fill_blank_exercises",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("sentence_with_blank", sa.Text(), nullable=False),
        sa.Column("original_sentence", sa.Text(), nullable=False),
        sa.Column("canonical_answer", sa.String(length=255), nullable=False),
        sa.Column("accepted_answers", sa.JSON(), nullable=False),
        sa.Column("target_start_offset", sa.Integer(), server_default="0", nullable=False),
        sa.Column("target_end_offset", sa.Integer(), server_default="0", nullable=False),
        sa.Column("difficulty", sa.String(length=50), server_default="medium", nullable=False),
        sa.Column("hint", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("source_reference", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_id"], ["study_material_generations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fill_blank_exercises_workspace_id", "fill_blank_exercises", ["workspace_id"])
    op.create_index("ix_fill_blank_exercises_generation_id", "fill_blank_exercises", ["generation_id"])
    op.create_index("ix_fill_blank_exercises_difficulty", "fill_blank_exercises", ["difficulty"])


def downgrade() -> None:
    op.drop_table("fill_blank_exercises")
    op.drop_table("mcq_options")
    op.drop_table("mcq_questions")
    op.drop_table("revision_notes")
    op.drop_table("study_material_generations")
