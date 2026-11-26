"""Pydantic schemas for Knovera Learner Intelligence Foundation (Phase 9).

Covers:
- C9.1: Concept-Question Mapping schemas
- C9.2: Learner Interaction Event schemas
- C9.3: Quiz Attempt Tracking & Concept Performance schemas
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================================
# C9.1: Concept-Question Mapping Enums & Schemas
# ============================================================================

class MappingMethod(str, Enum):
    """Method used to derive the question-to-concept relationship."""
    EXPLICIT_METADATA = "explicit_metadata"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    DETERMINISTIC_EXTRACTION = "deterministic_extraction"
    EMBEDDING_CANDIDATE = "embedding_candidate"
    LLM_SUGGESTED = "llm_suggested"
    HUMAN_REVIEWED = "human_reviewed"


class MappingValidationStatus(str, Enum):
    """Validation review state of the question-concept mapping."""
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class QuestionConceptMappingCreate(BaseModel):
    """Payload to create an explicit mapping between question and concept."""
    concept_id: UUID = Field(..., description="Target canonical KnowledgeNode ID")
    question_type: str = Field(default="mcq", description="mcq, true_false, or fill_blank")
    mapping_method: MappingMethod = MappingMethod.EXPLICIT_METADATA
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    validation_status: MappingValidationStatus = MappingValidationStatus.VALIDATED
    evidence_excerpt: Optional[str] = Field(default=None, max_length=2000)


class QuestionConceptMappingUpdate(BaseModel):
    """Payload to update an existing concept mapping."""
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    validation_status: Optional[MappingValidationStatus] = None
    evidence_excerpt: Optional[str] = Field(default=None, max_length=2000)


class ConceptSummary(BaseModel):
    """Minimal snapshot of a canonical concept/entity node."""
    id: UUID
    name: str
    normalized_name: str
    node_type: str
    category: str
    description: Optional[str] = None


class QuestionConceptMappingResponse(BaseModel):
    """Representation of an individual question-concept mapping."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    question_id: UUID
    question_type: str
    concept_id: UUID
    concept: Optional[ConceptSummary] = None
    mapping_method: MappingMethod
    confidence_score: float
    validation_status: MappingValidationStatus
    evidence_excerpt: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class QuestionConceptsResponse(BaseModel):
    """List of all concepts mapped to a specific question."""
    question_id: UUID
    question_type: str
    total_mappings: int
    mappings: List[QuestionConceptMappingResponse]


class QuestionSummary(BaseModel):
    """Minimal reference to an assessment question."""
    id: UUID
    question_type: str
    question_text: str
    difficulty: str


class ConceptQuestionsResponse(BaseModel):
    """List of all questions assessing a specific canonical concept."""
    concept_id: UUID
    concept_name: str
    total_questions: int
    questions: List[QuestionConceptMappingResponse]


# ============================================================================
# C9.2: Learner Interaction Event Enums & Schemas
# ============================================================================

class LearnerEventType(str, Enum):
    """Permitted educational interaction event types."""
    # Question interactions
    QUESTION_PRESENTED = "question_presented"
    QUESTION_VIEWED = "question_viewed"
    QUESTION_SKIPPED = "question_skipped"
    QUESTION_FLAGGED = "question_flagged"
    QUESTION_NAVIGATED = "question_navigated"

    # Answer interactions
    ANSWER_SELECTED = "answer_selected"
    ANSWER_SAVED = "answer_saved"
    ANSWER_REVISED = "answer_revised"
    ANSWER_SUBMITTED = "answer_submitted"

    # Learning support interactions
    HINT_OPENED = "hint_opened"
    EXPLANATION_OPENED = "explanation_opened"
    CORRECT_ANSWER_REVEALED = "correct_answer_revealed"
    SOURCE_OPENED = "source_opened"
    SOURCE_PAGE_NAVIGATED = "source_page_navigated"

    # Quiz interactions
    QUIZ_STARTED = "quiz_started"
    QUIZ_RESUMED = "quiz_resumed"
    QUIZ_PAUSED = "quiz_paused"
    QUIZ_SUBMITTED = "quiz_submitted"
    QUIZ_EVALUATED = "quiz_evaluated"


class LearnerInteractionEventCreate(BaseModel):
    """Ingestion payload for an individual interaction event."""
    event_type: LearnerEventType
    attempt_id: Optional[UUID] = None
    question_id: Optional[UUID] = None
    concept_id: Optional[UUID] = None
    client_occurred_at: Optional[datetime] = None
    event_metadata: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    schema_version: str = Field(default="1.0.0", max_length=20)

    @field_validator("event_metadata")
    @classmethod
    def validate_metadata_no_scores(cls, val: Dict[str, Any]) -> Dict[str, Any]:
        """Anti-tampering: Learner cannot submit score or correctness in event metadata."""
        disallowed = {"score", "score_percentage", "is_correct", "correct_count"}
        for key in disallowed:
            if key in val:
                raise ValueError(f"Metadata field '{key}' is server-authoritative and disallowed in client events.")
        return val


class LearnerInteractionBatchCreate(BaseModel):
    """Ingestion payload for a batch of interaction events."""
    events: List[LearnerInteractionEventCreate] = Field(..., min_length=1, max_length=100)


class LearnerInteractionEventResponse(BaseModel):
    """Persisted interaction event representation."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    user_id: UUID
    attempt_id: Optional[UUID] = None
    question_id: Optional[UUID] = None
    concept_id: Optional[UUID] = None
    event_type: str
    occurred_at: datetime
    client_occurred_at: Optional[datetime] = None
    event_metadata: Dict[str, Any]
    idempotency_key: Optional[str] = None
    schema_version: str
    created_at: datetime


class LearnerInteractionListResponse(BaseModel):
    """Paginated list of interaction events."""
    items: List[LearnerInteractionEventResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# C9.3: Quiz Attempt Tracking & Concept Performance Schemas
# ============================================================================

class ConceptPerformanceMetric(BaseModel):
    """Evaluated performance for a single canonical concept in a quiz attempt."""
    concept_id: UUID
    concept_name: str
    category: str
    questions_attempted: int
    questions_answered: int
    correct_answers: int
    incorrect_answers: int
    unanswered: int
    correct_rate: float = Field(..., description="Percentage correct among answered questions (0-100)")


class QuizAttemptConceptPerformanceResponse(BaseModel):
    """Concept-level performance breakdown for an evaluated quiz attempt."""
    attempt_id: UUID
    title: str
    status: str
    evaluated_at: Optional[datetime] = None
    concepts: List[ConceptPerformanceMetric]


class QuestionTrackingMetric(BaseModel):
    """Detailed operational tracking for a single question inside a quiz attempt."""
    question_id: UUID
    question_type: str
    display_order: int
    is_answered: bool
    is_correct: Optional[bool] = None
    selected_answer: Any = None
    response_duration_ms: Optional[int] = None
    revision_count: int = 0
    hint_opened: bool = False
    explanation_opened: bool = False
    source_opened: bool = False
    mapped_concepts: List[str] = Field(default_factory=list)


class QuizAttemptTrackingResponse(BaseModel):
    """Full operational tracking and lifecycle analytics for a quiz attempt."""
    attempt_id: UUID
    workspace_id: UUID
    user_id: UUID
    title: str
    status: str
    started_at: datetime
    submitted_at: Optional[datetime] = None
    total_duration_seconds: Optional[int] = None
    total_questions: int
    answered_count: int
    unanswered_count: int
    correct_count: int
    incorrect_count: int
    score_percentage: float
    questions: List[QuestionTrackingMetric]
    concept_performance: List[ConceptPerformanceMetric]


class LearningInteractionsSummaryResponse(BaseModel):
    """Workspace-level interaction event summary statistics."""
    workspace_id: UUID
    total_events: int
    events_by_type: Dict[str, int]
    active_attempts_count: int
    total_hints_opened: int
    total_explanations_opened: int
    total_sources_opened: int
