"""ORM models for Knovera Learner Intelligence Foundation (Phase 9).

Includes:
- QuestionConceptMapping: Many-to-many relationship linking questions to canonical concepts (C9.1)
- LearnerInteractionEvent: Normalized event-level interaction logging across the learning lifecycle (C9.2)
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.knowledge_node import KnowledgeNode
    from backend.app.models.study_material import QuizAttempt
    from backend.app.models.user import User
    from backend.app.models.workspace import Workspace


class QuestionConceptMapping(Base):
    """Many-to-many mapping connecting assessment questions to canonical concepts (Phase 9 C9.1)."""

    __tablename__ = "question_concept_mappings"

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
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    question_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="mcq",  # "mcq", "true_false", "fill_blank"
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mapping_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="explicit_metadata",  # "explicit_metadata", "knowledge_graph", "deterministic_extraction", "embedding_candidate", "llm_suggested", "human_reviewed"
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    validation_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="candidate",  # "candidate", "validated", "needs_review", "rejected"
        index=True,
    )
    evidence_excerpt: Mapped[Optional[str]] = mapped_column(
        Text,
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
        UniqueConstraint("question_id", "concept_id", name="uq_question_concept"),
        Index("ix_qcm_workspace_concept", "workspace_id", "concept_id"),
        Index("ix_qcm_question_validation", "question_id", "validation_status"),
    )

    # Relationships
    concept: Mapped["KnowledgeNode"] = relationship(
        "KnowledgeNode",
        foreign_keys=[concept_id],
        lazy="joined",
    )


class RevisionRecommendation(Base):
    """Actionable, explainable revision recommendation for a learner and concept (Phase 9 C9.7)."""

    __tablename__ = "revision_recommendations"

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
    concept_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recommendation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        # "revise_concept", "practice_concept", "reinforce_concept",
        # "review_source_material", "insufficient_evidence", "no_action_needed"
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        index=True,
        # "high", "medium", "low"
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    evidence_summary: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("bkt_model_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="suggested",
        index=True,
        # "suggested", "viewed", "started", "completed", "dismissed", "expired"
    )
    linked_resources: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
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
        Index("ix_rev_rec_workspace_user", "workspace_id", "user_id"),
        Index("ix_rev_rec_user_status", "user_id", "status"),
        Index("ix_rev_rec_concept", "concept_id"),
    )

    concept: Mapped["KnowledgeNode"] = relationship(
        "KnowledgeNode",
        foreign_keys=[concept_id],
        lazy="joined",
    )


class LearnerInteractionEvent(Base):
    """Normalized interaction log recording learner actions across learning materials (Phase 9 C9.2)."""

    __tablename__ = "learner_interaction_events"

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
    attempt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        index=True,
    )
    concept_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("knowledge_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    client_occurred_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    event_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    schema_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_lie_attempt_occurred", "attempt_id", "occurred_at"),
        Index("ix_lie_user_occurred", "user_id", "occurred_at"),
        Index("ix_lie_workspace_type", "workspace_id", "event_type"),
    )
