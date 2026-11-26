"""ORM Models for Bayesian Knowledge Tracing (Phase 9 Chunks C9.4, C9.5, C9.6).

Tables:
- BKTModelVersion: Stores versioned BKT parameter sets (global or concept-specific)
- BKTEstimationRun: Tracks parameter fitting lifecycle, metrics, and convergence
- LearnerConceptMastery: Current learner-concept mastery state projection
- LearnerConceptMasteryHistory: Immutable audit log of every Bayesian update
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


class BKTModelVersion(Base):
    """Versioned BKT parameter set for online inference and model management (C9.5)."""

    __tablename__ = "bkt_model_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    model_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    model_scope: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="global",  # "global" or "concept_specific"
        index=True,
    )
    concept_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("knowledge_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    p_init: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.30,
    )
    p_transit: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.15,
    )
    p_guess: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.20,
    )
    p_slip: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.10,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="candidate",  # "candidate", "active", "archived"
        index=True,
    )
    training_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    training_sequence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    validation_metrics: Mapped[Dict[str, Any]] = mapped_column(
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

    concept: Mapped[Optional["KnowledgeNode"]] = relationship(
        "KnowledgeNode",
        foreign_keys=[concept_id],
        lazy="joined",
    )
    evaluation_runs: Mapped[List["BKTEvaluationRun"]] = relationship(
        "BKTEvaluationRun",
        back_populates="model_version",
        cascade="all, delete-orphan",
    )


class BKTEstimationRun(Base):
    """Tracks BKT parameter fitting experiments, convergence, and evaluation metrics (C9.5)."""

    __tablename__ = "bkt_estimation_runs"

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
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("bkt_model_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    concept_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("knowledge_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="running",  # "running", "completed", "failed"
        index=True,
    )
    num_learners: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    num_sequences: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    num_observations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    converged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    iterations_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    final_log_likelihood: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    initial_params: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    fitted_params: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
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


class LearnerConceptMastery(Base):
    """Current active learner-concept mastery state projection (C9.6)."""

    __tablename__ = "learner_concept_mastery"

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
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("bkt_model_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    posterior_mastery_probability: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.30,
    )
    predicted_next_mastery_probability: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.30,
    )
    observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_attempt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("quiz_attempts.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
    )
    last_observation_correct: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="insufficient_data",  # "insufficient_data", "developing", "mastered"
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", "concept_id", name="uq_learner_concept_mastery"),
        Index("ix_lcm_user_workspace", "user_id", "workspace_id"),
    )

    concept: Mapped["KnowledgeNode"] = relationship(
        "KnowledgeNode",
        foreign_keys=[concept_id],
        lazy="joined",
    )


class LearnerConceptMasteryHistory(Base):
    """Immutable audit log of each Bayesian update step across opportunities (C9.6)."""

    __tablename__ = "learner_concept_mastery_history"

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
    mastery_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("learner_concept_mastery.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    observation_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    prior_mastery: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    posterior_mastery: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    predicted_next_mastery: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    p_init: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    p_transit: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    p_guess: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    p_slip: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    sequence_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "attempt_id", "question_id", "concept_id",
            name="uq_bkt_mastery_history_event",
        ),
        Index("ix_lcmh_user_concept_occurred", "user_id", "concept_id", "occurred_at"),
    )


class BKTEvaluationRun(Base):
    """Tracks offline validation, predictive metrics, calibration, and readiness of a BKT model version (Phase 9 C9.9)."""

    __tablename__ = "bkt_evaluation_runs"

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
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("bkt_model_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    split_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="learner_holdout",  # "learner_holdout", "temporal_holdout"
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="running",  # "running", "completed", "failed"
        index=True,
    )
    readiness_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="not_evaluated",  # "not_evaluated", "insufficient_data", "evaluation_passed", "evaluation_failed", "requires_review"
        index=True,
    )
    num_learners: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    num_sequences: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    num_observations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    log_loss: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    brier_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    accuracy: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    auc_roc: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    calibration_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    baseline_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    parameter_stability: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    readiness_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    evaluated_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
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

    __table_args__ = (
        Index("ix_bkt_eval_workspace_model", "workspace_id", "model_version_id"),
        Index("ix_bkt_eval_readiness", "readiness_status"),
    )

    model_version: Mapped["BKTModelVersion"] = relationship(
        "BKTModelVersion",
        back_populates="evaluation_runs",
        lazy="joined",
    )
