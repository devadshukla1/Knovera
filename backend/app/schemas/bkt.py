"""Pydantic schemas for Bayesian Knowledge Tracing (Phase 9 Chunks C9.4, C9.5, C9.6)."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class BKTModelScope(str, Enum):
    GLOBAL = "global"
    CONCEPT_SPECIFIC = "concept_specific"


class BKTModelStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    ARCHIVED = "archived"


class BKTEstimationRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LearnerMasteryStatus(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    DEVELOPING = "developing"
    MASTERED = "mastered"


# -----------------------------------------------------------------------------
# Parameter Estimation Schemas (C9.5)
# -----------------------------------------------------------------------------

class BKTEstimationRunCreate(BaseModel):
    """Payload to trigger a BKT parameter estimation run."""
    model_scope: BKTModelScope = BKTModelScope.GLOBAL
    concept_id: Optional[UUID] = None
    max_iter: int = Field(default=100, ge=5, le=500)
    tol: float = Field(default=1e-5, gt=0.0, le=0.01)
    n_restarts: int = Field(default=5, ge=1, le=20)
    random_seed: int = Field(default=42)
    auto_activate: bool = Field(default=False, description="Automatically activate model version if statistically supported")


class BKTModelVersionResponse(BaseModel):
    """Representation of a persisted BKT model version."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: Optional[UUID] = None
    model_version: str
    model_scope: str
    concept_id: Optional[UUID] = None
    p_init: float
    p_transit: float
    p_guess: float
    p_slip: float
    status: str
    training_observation_count: int
    training_sequence_count: int
    validation_metrics: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class BKTEstimationRunResponse(BaseModel):
    """Representation of an estimation execution run."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    model_version_id: Optional[UUID] = None
    concept_id: Optional[UUID] = None
    status: str
    num_learners: int
    num_sequences: int
    num_observations: int
    converged: bool
    iterations_count: int
    final_log_likelihood: float
    initial_params: Dict[str, Any]
    fitted_params: Dict[str, Any]
    metrics: Dict[str, Any]
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class BKTModelActivateRequest(BaseModel):
    """Request to activate a candidate BKT model version."""
    activate: bool = True
    force: bool = Field(default=False, description="Force activation even if offline evaluation readiness has warnings")


# -----------------------------------------------------------------------------
# Learner Mastery State & History Schemas (C9.6)
# -----------------------------------------------------------------------------

class LearnerConceptMasteryResponse(BaseModel):
    """Current mastery state for a learner on a specific canonical concept."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    user_id: UUID
    concept_id: UUID
    concept_name: Optional[str] = None
    concept_category: Optional[str] = None
    model_version_id: Optional[UUID] = None
    posterior_mastery_probability: float = Field(..., description="Probability of mastery after latest observation")
    predicted_next_mastery_probability: float = Field(..., description="Predicted mastery after learning transition")
    observation_count: int
    last_attempt_id: Optional[UUID] = None
    last_question_id: Optional[UUID] = None
    last_observation_correct: Optional[bool] = None
    status: str
    last_updated_at: datetime
    created_at: datetime


class LearnerConceptMasteryHistoryResponse(BaseModel):
    """Immutable log entry of a Bayesian update opportunity."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    user_id: UUID
    concept_id: UUID
    mastery_id: UUID
    attempt_id: UUID
    question_id: UUID
    observation_correct: bool
    prior_mastery: float
    posterior_mastery: float
    predicted_next_mastery: float
    p_init: float
    p_transit: float
    p_guess: float
    p_slip: float
    model_version: str
    sequence_index: int
    occurred_at: datetime
    created_at: datetime


class LearnerMasterySummaryResponse(BaseModel):
    """Aggregated mastery snapshot across all evaluated concepts for a learner."""
    workspace_id: UUID
    user_id: UUID
    total_concepts_evaluated: int
    mastered_count: int
    developing_count: int
    insufficient_data_count: int
    average_mastery_probability: float
    items: List[LearnerConceptMasteryResponse]


# -----------------------------------------------------------------------------
# BKT Evaluation & Model Readiness Schemas (C9.9)
# -----------------------------------------------------------------------------

class BKTSplitMethod(str, Enum):
    """Dataset splitting strategy for offline model evaluation (C9.9)."""
    LEARNER_HOLDOUT = "learner_holdout"
    TEMPORAL_HOLDOUT = "temporal_holdout"


class BKTReadinessStatus(str, Enum):
    """Model-readiness qualification state (C9.9)."""
    NOT_EVALUATED = "not_evaluated"
    INSUFFICIENT_DATA = "insufficient_data"
    EVALUATION_PASSED = "evaluation_passed"
    EVALUATION_FAILED = "evaluation_failed"
    REQUIRES_REVIEW = "requires_review"


class BKTEvaluationRunCreate(BaseModel):
    """Payload to launch an offline BKT evaluation run."""
    model_version_id: UUID
    split_method: BKTSplitMethod = BKTSplitMethod.LEARNER_HOLDOUT
    test_ratio: float = Field(default=0.25, ge=0.1, le=0.5)
    random_seed: int = Field(default=42)
    max_acceptable_log_loss: float = Field(default=0.75, gt=0.0)
    max_acceptable_brier: float = Field(default=0.30, gt=0.0)


class BKTCalibrationBin(BaseModel):
    """Predicted probability bin for calibration analysis."""
    bin_index: int
    bin_range: str
    sample_count: int
    predicted_mean: float
    observed_mean: float


class BKTEvaluationRunResponse(BaseModel):
    """Structured report of an offline BKT evaluation run (C9.9)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    model_version_id: UUID
    split_method: str
    status: str
    readiness_status: str
    num_learners: int
    num_sequences: int
    num_observations: int
    log_loss: float
    brier_score: float
    accuracy: float
    auc_roc: Optional[float] = None
    calibration_metrics: Dict[str, Any]
    baseline_metrics: Dict[str, Any]
    parameter_stability: Dict[str, Any]
    readiness_notes: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class BKTModelRollbackRequest(BaseModel):
    """Payload to rollback from active model to previous active version."""
    target_version_id: Optional[UUID] = Field(
        default=None,
        description="Optional explicit previous model version to restore. If omitted, restores most recent previously active version."
    )

