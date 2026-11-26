"""ORM models for Knovera Study Materials (Phase 8).

Includes:
- StudyMaterialGeneration: Run audit log, telemetry, quality report
- RevisionNote: Structured revision notes (C8.1)
- MCQQuestion & MCQOption: Four-option multiple-choice questions (C8.2)
- FillBlankExercise: High-yield sentence recall exercises (C8.3)
- TrueFalseQuestion: Source-grounded True/False assessment questions (C8.4)
- Flashcard: Active-recall study flashcards across 8 categories (C8.5)
- QuizAttempt & QuizAttemptAnswer: Interactive assessment runner & attempt persistence (C8.6)
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.document import Document
    from backend.app.models.document_chunk import DocumentChunk
    from backend.app.models.user import User
    from backend.app.models.workspace import Workspace


class StudyMaterialGeneration(Base):
    """Lifecycle tracking and execution telemetry for study material generation runs."""

    __tablename__ = "study_material_generations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    material_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="completed",
        index=True,
    )
    requested_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    generated_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    validated_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    rejected_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    provider_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="mock",
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="mock-model",
    )
    scope_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="workspace",
    )
    scope_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    quality_report: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class RevisionNote(Base):
    """Structured, source-grounded revision notes (C8.1)."""

    __tablename__ = "revision_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("study_material_generations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    overview: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    length: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="standard",
    )
    detail_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="intermediate",
    )
    focus: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="conceptual_learning",
    )
    sections: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    key_concepts: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    important_points: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    formulas: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    quick_summary: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    source_references: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MCQQuestion(Base):
    """Multiple-Choice Question entity (C8.2)."""

    __tablename__ = "mcq_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("study_material_generations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    difficulty: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medium",
        index=True,
    )
    question_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="conceptual",
    )
    correct_option_id: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    topic_tags: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    source_references: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    options: Mapped[List["MCQOption"]] = relationship(
        "MCQOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="MCQOption.option_id",
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_mcq_questions_ws_active_diff", "workspace_id", "is_active", "difficulty"),
    )


class MCQOption(Base):
    """Option associated with an MCQ question."""

    __tablename__ = "mcq_options"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("mcq_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_id: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    option_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship back to parent question
    question: Mapped["MCQQuestion"] = relationship(
        "MCQQuestion",
        back_populates="options",
    )


class FillBlankExercise(Base):
    """Fill-in-the-blank recall exercise (C8.3)."""

    __tablename__ = "fill_blank_exercises"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("study_material_generations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sentence_with_blank: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    original_sentence: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    canonical_answer: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    accepted_answers: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    target_start_offset: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    target_end_offset: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    difficulty: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medium",
        index=True,
    )
    hint: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    explanation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    source_reference: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_fill_blank_ws_active", "workspace_id", "is_active"),
    )


class TrueFalseQuestion(Base):
    """Source-grounded True/False assessment question (Phase 8 C8.4)."""

    __tablename__ = "true_false_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("study_material_generations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    statement: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    correct_answer: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    difficulty: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medium",
        index=True,
    )
    topic: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    validation_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="validated",
    )
    source_references: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_tf_questions_ws_active", "workspace_id", "is_active"),
    )


class Flashcard(Base):
    """Source-grounded active-recall study flashcard (Phase 8 C8.5)."""

    __tablename__ = "flashcards"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("study_material_generations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    front: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    back: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    card_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="concept",
        index=True,
    )
    difficulty: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medium",
        index=True,
    )
    topic: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    validation_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="validated",
    )
    source_references: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_flashcards_ws_active_type", "workspace_id", "is_active", "card_type"),
    )


class QuizAttempt(Base):
    """User assessment attempt tracking and evaluation (Phase 8 C8.6)."""

    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Interactive Quiz Attempt",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="in_progress",
        index=True,
    )
    total_questions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    correct_answers_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    score_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    questions_order: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    evaluation_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_quiz_attempts_ws_user_status", "workspace_id", "user_id", "status"),
        Index("ix_quiz_attempts_user_submitted", "user_id", "submitted_at"),
    )

    # Relationships
    answers: Mapped[List["QuizAttemptAnswer"]] = relationship(
        "QuizAttemptAnswer",
        back_populates="attempt",
        cascade="all, delete-orphan",
        lazy="joined",
    )


class QuizAttemptAnswer(Base):
    """Single answer submitted by a user for a question in a quiz attempt."""

    __tablename__ = "quiz_attempt_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    question_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    selected_answer: Mapped[Any] = mapped_column(
        JSON,
        nullable=True,
    )
    is_correct: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_quiz_attempt_answers_attempt_q", "attempt_id", "question_id"),
    )

    attempt: Mapped["QuizAttempt"] = relationship(
        "QuizAttempt",
        back_populates="answers",
    )
