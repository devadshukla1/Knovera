"""Pydantic schemas for Knovera Learning Analytics Dashboard (Phase 9 C9.8)."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class AnalyticsDateFilter(str, Enum):
    """Supported time windows for dashboard aggregation."""
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    ALL_TIME = "all"


class AnalyticsOverviewResponse(BaseModel):
    """High-level summary KPIs for the learning analytics dashboard."""
    total_quiz_attempts: int
    completed_attempts: int
    evaluated_attempts: int
    average_quiz_score: float = Field(description="Mean percentage score across completed evaluated attempts")
    overall_correct_rate: float = Field(description="Percentage of correct answers out of answered questions (unanswered excluded)")
    total_questions_answered: int
    total_correct_answers: int
    total_incorrect_answers: int
    total_unanswered: int
    concepts_assessed: int = Field(description="Number of distinct canonical concepts evaluated")
    concepts_with_sufficient_bkt: int = Field(description="Concepts with >= 3 observations under an active model")
    pending_recommendations_count: int
    date_filter: str


class QuizPerformanceResponse(BaseModel):
    """Aggregated quiz assessment performance metrics."""
    total_attempts: int
    average_score: float
    highest_score: float
    recent_score: Optional[float] = None
    recent_attempt_id: Optional[UUID] = None
    recent_attempt_date: Optional[datetime] = None
    total_answered: int
    total_correct: int
    total_incorrect: int
    total_unanswered: int
    correct_rate: float


class ScoreHistoryPoint(BaseModel):
    """A single completed quiz attempt score point for time-series charts."""
    attempt_id: UUID
    attempt_date: datetime
    score_percentage: float
    passed: bool
    total_questions: int
    correct_count: int


class ScoreHistoryResponse(BaseModel):
    """Chronological series of completed quiz scores."""
    points: List[ScoreHistoryPoint]
    total_points: int


class ConceptAnalyticsItem(BaseModel):
    """Performance breakdown for a single canonical concept."""
    concept_id: UUID
    concept_name: str
    category: Optional[str] = None
    questions_attempted: int
    questions_answered: int
    correct_answers: int
    incorrect_answers: int
    unanswered: int
    correct_rate: float = Field(description="Percentage (correct / answered * 100), or 0.0 if 0 answered")
    evidence_sufficiency: str = Field(description="sufficient (>= 3 obs), sparse (1-2 obs), or unobserved")
    bkt_mastery_probability: Optional[float] = None
    bkt_status: Optional[str] = None
    last_activity_at: Optional[datetime] = None


class ConceptAnalyticsResponse(BaseModel):
    """List of concept analytics with total count."""
    concepts: List[ConceptAnalyticsItem]
    total_count: int


class MasteryAnalyticsItem(BaseModel):
    """Latent concept mastery state under the active BKT model."""
    concept_id: UUID
    concept_name: str
    category: Optional[str] = None
    prior_mastery: float
    posterior_mastery: float
    predicted_next_mastery: float
    observation_count: int
    correct_count: int
    bkt_status: str
    model_version: Optional[str] = None
    is_model_validated: bool
    last_updated_at: datetime


class MasteryAnalyticsResponse(BaseModel):
    """Workspace-wide BKT mastery overview."""
    masteries: List[MasteryAnalyticsItem]
    total_concepts_tracked: int
    model_readiness_status: str
    active_model_version: Optional[str] = None


class ActivityTimelineItem(BaseModel):
    """A meaningful educational action for the learning timeline."""
    event_id: UUID
    event_type: str
    occurred_at: datetime
    title: str
    description: str
    concept_id: Optional[UUID] = None
    concept_name: Optional[str] = None
    attempt_id: Optional[UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActivityTimelineResponse(BaseModel):
    """Chronological timeline of educational events."""
    events: List[ActivityTimelineItem]
    total_events: int
