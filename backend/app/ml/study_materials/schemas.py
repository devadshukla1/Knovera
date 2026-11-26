"""Pydantic schemas for Knovera Study Material Generation (Phase 8).

Covers:
- C8.1: Revision Notes
- C8.2: Multiple-Choice Questions (MCQs)
- C8.3: Fill-in-the-Blanks Exercises
- C8.4: True/False Questions
- C8.5: Flashcards
- C8.6: Interactive Quiz Attempts & Authoritative Evaluation
- Source Scopes & Resolution
- Generation Requests, Responses, and Quality Reports
- Practice Mode vs Review Mode Security DTOs
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================================
# Enums
# ============================================================================

class MaterialType(str, Enum):
    """Supported study material types."""
    REVISION_NOTES = "revision_notes"
    MCQ = "mcq"
    FILL_BLANKS = "fill_blanks"
    TRUE_FALSE = "true_false"
    FLASHCARDS = "flashcards"


class GenerationStatus(str, Enum):
    """Lifecycle status of a study material generation run."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class NoteLength(str, Enum):
    """Configurable length for revision notes."""
    CONCISE = "concise"
    STANDARD = "standard"
    DETAILED = "detailed"


class DetailLevel(str, Enum):
    """Audience depth / difficulty tier."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class NoteFocus(str, Enum):
    """Pedagogical focus style for revision notes."""
    EXAM_REVISION = "exam_revision"
    CONCEPTUAL_LEARNING = "conceptual_learning"
    TECHNICAL_REFERENCE = "technical_reference"
    RESEARCH_REVIEW = "research_review"


class QuestionDifficulty(str, Enum):
    """Difficulty rating for quiz questions."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class MCQType(str, Enum):
    """Cognitive dimension of MCQ questions."""
    CONCEPTUAL = "conceptual"
    FACTUAL = "factual"
    APPLICATION = "application"
    COMPARISON = "comparison"
    ANALYTICAL_REASONING = "analytical_reasoning"


class FlashcardType(str, Enum):
    """Pedagogical category of flashcards."""
    DEFINITION = "definition"
    CONCEPT = "concept"
    FACT = "fact"
    FORMULA = "formula"
    ALGORITHM = "algorithm"
    COMPARISON = "comparison"
    APPLICATION = "application"
    TERMINOLOGY = "terminology"


class ValidationStatus(str, Enum):
    """Verification and quality status."""
    GENERATED = "generated"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class QuizAttemptStatus(str, Enum):
    """Lifecycle status of a quiz assessment attempt."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EVALUATED = "evaluated"


class SourceScopeType(str, Enum):
    """Scope defining source chunk boundary."""
    WORKSPACE = "workspace"
    DOCUMENTS = "documents"
    DOCUMENT = "document"
    TOPIC = "topic"
    CHUNKS = "chunks"


class ViewMode(str, Enum):
    """Security view mode for question retrieval."""
    PRACTICE = "practice"
    REVIEW = "review"


# ============================================================================
# Source Scope & Provenance
# ============================================================================

class SourceScope(BaseModel):
    """Target source boundary configuration for generation."""
    scope_type: SourceScopeType = Field(
        default=SourceScopeType.WORKSPACE,
        description="Boundary type: workspace, documents, document, topic, chunks",
    )
    document_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Target document IDs when scope is documents or document",
    )
    topic_id: Optional[UUID] = Field(
        default=None,
        description="Target topic ID when scope is topic",
    )
    chunk_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Explicit chunk IDs when scope is chunks",
    )


class SourceReference(BaseModel):
    """Fine-grained provenance reference to source document chunks."""
    chunk_id: UUID = Field(..., description="UUID of source chunk")
    document_id: UUID = Field(..., description="UUID of parent document")
    document_title: str = Field(..., description="Original document title")
    page_number: Optional[int] = Field(None, description="Page number if applicable")
    slide_number: Optional[int] = Field(None, description="Slide number if presentation")
    chunk_index: Optional[int] = Field(None, description="Zero-based chunk index")
    section_heading: Optional[str] = Field(None, description="Section heading if detected")
    excerpt: Optional[str] = Field(None, description="Exact text excerpt supporting the item")
    start_char_offset: Optional[int] = Field(None, description="Start character offset in chunk")
    end_char_offset: Optional[int] = Field(None, description="End character offset in chunk")


# ============================================================================
# C8.1: Revision Notes Schemas
# ============================================================================

class NoteSection(BaseModel):
    """Structured thematic section of revision notes."""
    heading: str = Field(..., min_length=1, description="Section title or topic")
    summary: str = Field(..., min_length=1, description="Concise summary of the section")
    bullet_points: List[str] = Field(default_factory=list, description="Core takeaways")
    key_takeaways: Optional[List[str]] = Field(default=None, description="Critical exam or recall items")


class KeyConceptItem(BaseModel):
    """Key concept definition item."""
    term: str = Field(..., min_length=1, description="Concept or term name")
    definition: str = Field(..., min_length=1, description="Source-grounded definition")
    context: Optional[str] = Field(None, description="Contextual application or example")


class FormulaItem(BaseModel):
    """Formula, equation, or algorithm excerpt."""
    name: str = Field(..., min_length=1, description="Formula or algorithm name")
    expression: str = Field(..., min_length=1, description="Mathematical notation or algorithm rule")
    explanation: Optional[str] = Field(None, description="Variable explanations or significance")


class RevisionNoteCreate(BaseModel):
    """Raw generated revision note before database insertion."""
    title: str = Field(..., min_length=1, max_length=255)
    overview: str = Field(..., min_length=1)
    length: NoteLength = NoteLength.STANDARD
    detail_level: DetailLevel = DetailLevel.INTERMEDIATE
    focus: NoteFocus = NoteFocus.CONCEPTUAL_LEARNING
    sections: List[NoteSection] = Field(default_factory=list)
    key_concepts: List[KeyConceptItem] = Field(default_factory=list)
    important_points: List[str] = Field(default_factory=list)
    formulas: List[FormulaItem] = Field(default_factory=list)
    quick_summary: List[str] = Field(default_factory=list)
    source_references: List[SourceReference] = Field(default_factory=list)


class RevisionNoteResponse(BaseModel):
    """Full API response for revision notes."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    generation_id: Optional[UUID]
    title: str
    overview: str
    length: NoteLength
    detail_level: DetailLevel
    focus: NoteFocus
    sections: List[NoteSection]
    key_concepts: List[KeyConceptItem]
    important_points: List[str]
    formulas: List[FormulaItem]
    quick_summary: List[str]
    source_references: List[SourceReference]
    created_at: datetime
    updated_at: datetime


# ============================================================================
# C8.2: MCQ Schemas
# ============================================================================

class MCQOptionCreate(BaseModel):
    """Single MCQ option."""
    option_id: str = Field(..., pattern=r"^[A-D]$", description="Option letter: A, B, C, or D")
    option_text: str = Field(..., min_length=1, description="Text of option")
    is_correct: bool = Field(..., description="Whether this option is the single correct answer")


class MCQOptionPracticeResponse(BaseModel):
    """Safe MCQ option response in practice mode (omits is_correct)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    option_id: str
    option_text: str


class MCQOptionReviewResponse(BaseModel):
    """Detailed MCQ option response in review mode (includes is_correct)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    option_id: str
    option_text: str
    is_correct: bool


class MCQQuestionCreate(BaseModel):
    """Raw generated MCQ question."""
    question_text: str = Field(..., min_length=5, description="Stem of question")
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    question_type: MCQType = MCQType.CONCEPTUAL
    correct_option_id: str = Field(..., pattern=r"^[A-D]$")
    explanation: str = Field(..., min_length=1, description="Justification and distractor analysis")
    topic_tags: List[str] = Field(default_factory=list)
    options: List[MCQOptionCreate] = Field(..., min_length=4, max_length=4)
    source_references: List[SourceReference] = Field(default_factory=list)

    @field_validator("options")
    @classmethod
    def validate_four_options(cls, v: List[MCQOptionCreate]) -> List[MCQOptionCreate]:
        ids = [opt.option_id for opt in v]
        if sorted(ids) != ["A", "B", "C", "D"]:
            raise ValueError("MCQ must contain exactly four options with IDs ['A', 'B', 'C', 'D']")
        correct_count = sum(1 for opt in v if opt.is_correct)
        if correct_count != 1:
            raise ValueError(f"MCQ must have exactly 1 correct option, got {correct_count}")
        return v


class MCQPracticeResponse(BaseModel):
    """Practice mode MCQ response (shields correct option and explanation)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    generation_id: Optional[UUID]
    question_text: str
    difficulty: QuestionDifficulty
    question_type: MCQType
    topic_tags: List[str]
    options: List[MCQOptionPracticeResponse]
    created_at: datetime


class MCQReviewResponse(BaseModel):
    """Review mode MCQ response (full answer key, explanations, and evidence)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    generation_id: Optional[UUID]
    question_text: str
    difficulty: QuestionDifficulty
    question_type: MCQType
    correct_option_id: str
    explanation: str
    topic_tags: List[str]
    options: List[MCQOptionReviewResponse]
    source_references: List[SourceReference]
    created_at: datetime


# ============================================================================
# C8.3: Fill-in-the-Blanks Schemas
# ============================================================================

class FillBlankExerciseCreate(BaseModel):
    """Raw generated fill-in-the-blank item."""
    sentence_with_blank: str = Field(
        ...,
        min_length=5,
        description="Sentence containing exact placeholder '______' (6 underscores)",
    )
    original_sentence: str = Field(..., min_length=5, description="Exact source sentence")
    canonical_answer: str = Field(..., min_length=1, description="Target term removed")
    accepted_answers: List[str] = Field(
        default_factory=list,
        description="Normalized case variants or common synonyms",
    )
    target_start_offset: int = Field(..., ge=0, description="Start char offset in original sentence")
    target_end_offset: int = Field(..., ge=1, description="End char offset in original sentence")
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    hint: Optional[str] = Field(None, description="Non-leaking contextual hint")
    explanation: Optional[str] = Field(None, description="Contextual explanation")
    chunk_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    source_reference: Optional[SourceReference] = None


class FillBlankPracticeResponse(BaseModel):
    """Practice mode Fill-in-the-blank response (hides answer and explanation)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    generation_id: Optional[UUID]
    sentence_with_blank: str
    difficulty: QuestionDifficulty
    hint: Optional[str]
    created_at: datetime


class FillBlankReviewResponse(BaseModel):
    """Review mode Fill-in-the-blank response (full answer key and evidence)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    generation_id: Optional[UUID]
    sentence_with_blank: str
    original_sentence: str
    canonical_answer: str
    accepted_answers: List[str]
    target_start_offset: int
    target_end_offset: int
    difficulty: QuestionDifficulty
    hint: Optional[str]
    explanation: Optional[str]
    source_reference: Optional[SourceReference]
    created_at: datetime


# ============================================================================
# C8.4: True/False Question Schemas
# ============================================================================

class TrueFalseQuestionCreate(BaseModel):
    """Raw generated True/False question."""
    statement: str = Field(..., min_length=5, description="Complete declarative statement")
    correct_answer: bool = Field(..., description="Boolean truth value: True or False")
    explanation: str = Field(..., min_length=5, description="Source-grounded justification and error correction")
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    topic: Optional[str] = Field(None, max_length=100)
    validation_status: ValidationStatus = ValidationStatus.VALIDATED
    chunk_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    source_references: List[SourceReference] = Field(default_factory=list)


class TrueFalsePracticeResponse(BaseModel):
    """Practice mode True/False response (shields correct answer and explanation)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    generation_id: Optional[UUID]
    statement: str
    difficulty: QuestionDifficulty
    topic: Optional[str] = None
    created_at: datetime


class TrueFalseReviewResponse(BaseModel):
    """Review mode True/False response (includes answer, explanation, and source evidence)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    generation_id: Optional[UUID]
    statement: str
    correct_answer: bool
    explanation: str
    difficulty: QuestionDifficulty
    topic: Optional[str] = None
    validation_status: ValidationStatus
    source_references: List[SourceReference]
    created_at: datetime


class TrueFalseGenerateRequest(BaseModel):
    """Request payload for generating True/False questions."""
    scope: SourceScope = Field(default_factory=SourceScope)
    count: int = Field(default=5, ge=1, le=50, description="Number of questions to generate")
    difficulty: Optional[QuestionDifficulty] = Field(None, description="Target difficulty")
    topic: Optional[str] = Field(None, max_length=100)
    target_true_ratio: Optional[float] = Field(default=0.5, ge=0.0, le=1.0, description="Target ratio of True questions")


# ============================================================================
# C8.5: Flashcard Schemas
# ============================================================================

class FlashcardCreate(BaseModel):
    """Raw generated flashcard before persistence."""
    front: str = Field(..., min_length=3, max_length=200, description="Concise prompt or question")
    back: str = Field(..., min_length=1, max_length=500, description="Concise target answer or definition")
    card_type: FlashcardType = FlashcardType.CONCEPT
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    topic: Optional[str] = Field(None, max_length=100)
    validation_status: ValidationStatus = ValidationStatus.VALIDATED
    chunk_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    source_references: List[SourceReference] = Field(default_factory=list)


class FlashcardResponse(BaseModel):
    """Full API response for a single flashcard."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    generation_id: Optional[UUID]
    front: str
    back: str
    card_type: FlashcardType
    difficulty: QuestionDifficulty
    topic: Optional[str] = None
    validation_status: ValidationStatus
    source_references: List[SourceReference]
    created_at: datetime
    updated_at: datetime


class FlashcardGenerateRequest(BaseModel):
    """Request payload for generating flashcards."""
    scope: SourceScope = Field(default_factory=SourceScope)
    count: int = Field(default=10, ge=1, le=50, description="Number of cards to generate")
    difficulty: Optional[QuestionDifficulty] = Field(None, description="Target difficulty")
    card_type: Optional[FlashcardType] = Field(None, description="Specific card category")
    topic: Optional[str] = Field(None, max_length=100)


# ============================================================================
# C8.6: Interactive Quiz Attempt & Authoritative Evaluation Schemas
# ============================================================================

class QuizAttemptCreateRequest(BaseModel):
    """Request to create a new interactive quiz attempt."""
    title: Optional[str] = Field(None, max_length=255, description="Optional custom quiz title")
    question_ids: Optional[List[UUID]] = Field(None, description="Explicit question IDs to include")
    generation_ids: Optional[List[UUID]] = Field(None, description="Optional generation runs to draw from")
    question_types: Optional[List[str]] = Field(
        default=None,
        description="Filter question types: mcq, true_false, fill_blank, or null for all",
    )
    count: int = Field(default=10, ge=1, le=50, description="Target total questions in quiz")
    difficulty: Optional[QuestionDifficulty] = Field(None, description="Difficulty filter")


class QuizAttemptAnswerSubmit(BaseModel):
    """Learner's answer to a single question during a quiz attempt."""
    question_id: UUID
    question_type: str = Field(..., description="mcq, true_false, or fill_blank")
    selected_answer: Any = Field(..., description="Letter (e.g. 'A'), boolean, or text string")


class QuizAttemptAnswerSaveRequest(BaseModel):
    """Batch or single answer save payload during quiz navigation."""
    answers: List[QuizAttemptAnswerSubmit]


class QuizQuestionPracticeItem(BaseModel):
    """Unified sanitized question presentation for active quiz runner."""
    id: UUID
    question_type: str = Field(..., description="mcq, true_false, or fill_blank")
    question_text: str
    difficulty: QuestionDifficulty
    options: Optional[List[MCQOptionPracticeResponse]] = None
    hint: Optional[str] = None
    document_title: Optional[str] = None
    page_number: Optional[int] = None


class QuizAttemptResponse(BaseModel):
    """Active quiz attempt state returned to the frontend runner."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    user_id: UUID
    title: str
    status: QuizAttemptStatus
    total_questions: int
    answered_count: int
    started_at: datetime
    submitted_at: Optional[datetime] = None
    questions: List[QuizQuestionPracticeItem]
    saved_answers: Dict[str, Any] = Field(default_factory=dict)


class QuizAttemptSummaryResponse(BaseModel):
    """Summary item for listing quiz attempts."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    title: str
    status: QuizAttemptStatus
    total_questions: int
    correct_answers_count: Optional[int] = 0
    score_percentage: Optional[float] = 0.0
    started_at: datetime
    submitted_at: Optional[datetime] = None


class QuizAttemptResultDetail(BaseModel):
    """Question review item showing learner answer, verified answer, and explanation."""
    question_id: UUID
    question_type: str
    question_text: str
    difficulty: QuestionDifficulty
    learner_answer: Any
    correct_answer: Any
    is_correct: bool
    explanation: str
    source_references: List[SourceReference] = Field(default_factory=list)


class QuizAttemptResultResponse(BaseModel):
    """Complete evaluation report returned upon submission and for review."""
    model_config = ConfigDict(from_attributes=True)

    attempt_id: UUID
    title: str
    status: QuizAttemptStatus
    total_questions: int
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    score_percentage: float
    started_at: datetime
    submitted_at: Optional[datetime]
    results: List[QuizAttemptResultDetail]


# ============================================================================
# Shared Generation & Quality Schemas
# ============================================================================

class RevisionNotesGenerateRequest(BaseModel):
    """Request payload for generating revision notes."""
    scope: SourceScope = Field(default_factory=SourceScope)
    length: NoteLength = NoteLength.STANDARD
    detail_level: DetailLevel = DetailLevel.INTERMEDIATE
    focus: NoteFocus = NoteFocus.CONCEPTUAL_LEARNING
    custom_title: Optional[str] = Field(None, max_length=255)


class MCQGenerateRequest(BaseModel):
    """Request payload for generating MCQs."""
    scope: SourceScope = Field(default_factory=SourceScope)
    count: int = Field(default=5, ge=1, le=50, description="Number of questions to generate")
    difficulty: Optional[QuestionDifficulty] = Field(None, description="Filter or target difficulty")
    question_type: Optional[MCQType] = Field(None, description="Target question cognitive type")


class FillBlankGenerateRequest(BaseModel):
    """Request payload for generating fill-in-the-blanks."""
    scope: SourceScope = Field(default_factory=SourceScope)
    count: int = Field(default=5, ge=1, le=50, description="Number of exercises to generate")
    difficulty: Optional[QuestionDifficulty] = Field(None, description="Filter or target difficulty")


class QualityMetric(BaseModel):
    """Single quality verification check result."""
    check_name: str
    passed: bool
    details: Optional[str] = None


class StudyMaterialQualityReport(BaseModel):
    """Comprehensive validation metrics report for a generation run."""
    total_requested: int
    total_raw_generated: int
    total_validated: int
    total_rejected: int
    validation_checks: List[QualityMetric] = Field(default_factory=list)
    rejection_reasons: List[str] = Field(default_factory=list)


class StudyMaterialGenerationRunResponse(BaseModel):
    """Telemetry report of generation run lifecycle."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    material_type: MaterialType
    status: GenerationStatus
    requested_count: int
    generated_count: int
    validated_count: int
    rejected_count: int
    duration_ms: int
    provider_name: str
    model_name: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# ============================================================================
# C8.8 & C8.9: Explanations, Source Citations & History Schemas
# ============================================================================

class QuestionExplanationResponse(BaseModel):
    """Pedagogical explanation for a specific question in an evaluated quiz attempt."""
    attempt_id: UUID
    question_id: UUID
    question_type: str
    question_text: str
    explanation: str
    correct_answer: Any
    learner_answer: Optional[Any] = None
    is_correct: Optional[bool] = None


class QuestionSourcesResponse(BaseModel):
    """Verified source citations and document references for an evaluated question."""
    attempt_id: UUID
    question_id: UUID
    question_type: str
    source_references: List[SourceReference] = Field(default_factory=list)


class QuizHistorySummaryResponse(BaseModel):
    """Aggregate statistics for historical quiz attempts in a workspace."""
    total_attempts: int
    completed_attempts: int
    in_progress_attempts: int
    average_score: float
    overall_correct_rate: float
    total_questions_answered: int
    total_correct_answers: int


class QuizHistoryTrendPoint(BaseModel):
    """Single chronological quiz evaluation point for score trends."""
    attempt_id: UUID
    title: str
    score_percentage: float
    total_questions: int
    correct_count: int
    completed_at: datetime


class QuizHistoryTrendsResponse(BaseModel):
    """Timeline data of past evaluated quiz attempts."""
    trends: List[QuizHistoryTrendPoint] = Field(default_factory=list)


class QuizHistoryListResponse(BaseModel):
    """Paginated list of historical quiz attempts with metadata."""
    items: List[QuizAttemptSummaryResponse]
    total: int
    limit: int
    offset: int

