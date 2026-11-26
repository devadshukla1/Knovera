"""API Endpoints for Knovera Learner Intelligence Foundation (Phase 9).

Exposes:
- Concept-Question Mapping (C9.1)
- Learner Interaction Logging (C9.2)
- Quiz Attempt Tracking & Concept Performance (C9.3)
"""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_user_workspace
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.learner_intelligence import (
    ConceptQuestionsResponse,
    ConceptSummary,
    LearnerInteractionBatchCreate,
    LearnerInteractionEventCreate,
    LearnerInteractionEventResponse,
    LearnerInteractionListResponse,
    LearningInteractionsSummaryResponse,
    MappingMethod,
    MappingValidationStatus,
    QuestionConceptMappingCreate,
    QuestionConceptMappingResponse,
    QuestionConceptMappingUpdate,
    QuestionConceptsResponse,
    QuizAttemptConceptPerformanceResponse,
    QuizAttemptTrackingResponse,
)
from backend.app.services.concept_mapping_service import ConceptQuestionMappingService
from backend.app.services.learner_interaction_service import LearnerInteractionService
from backend.app.services.quiz_tracking_service import QuizAttemptTrackingService

logger = get_logger("knovera.api.learner_intelligence")

router = APIRouter()


# =============================================================================
# C9.1: Concept-Question Mapping Endpoints
# =============================================================================

@router.post(
    "/{workspace_id}/questions/{question_id}/concept-mappings",
    response_model=QuestionConceptMappingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an explicit question-to-concept mapping",
)
def create_question_concept_mapping(
    workspace_id: uuid.UUID,
    question_id: uuid.UUID,
    data: QuestionConceptMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> QuestionConceptMappingResponse:
    """Explicitly map an assessment question to a canonical KnowledgeNode."""
    service = ConceptQuestionMappingService(db)
    mapping = service.create_mapping(workspace.id, question_id, data)

    concept_summary = None
    if mapping.concept:
        concept_summary = ConceptSummary(
            id=mapping.concept.id,
            name=mapping.concept.name,
            normalized_name=mapping.concept.normalized_name,
            node_type=mapping.concept.node_type,
            category=mapping.concept.category,
            description=mapping.concept.description,
        )

    return QuestionConceptMappingResponse(
        id=mapping.id,
        workspace_id=mapping.workspace_id,
        question_id=mapping.question_id,
        question_type=mapping.question_type,
        concept_id=mapping.concept_id,
        concept=concept_summary,
        mapping_method=MappingMethod(mapping.mapping_method),
        confidence_score=mapping.confidence_score,
        validation_status=MappingValidationStatus(mapping.validation_status),
        evidence_excerpt=mapping.evidence_excerpt,
        created_at=mapping.created_at,
        updated_at=mapping.updated_at,
    )


@router.get(
    "/{workspace_id}/questions/{question_id}/concepts",
    response_model=QuestionConceptsResponse,
    summary="Get all concepts mapped to a question",
)
def get_question_concepts(
    workspace_id: uuid.UUID,
    question_id: uuid.UUID,
    status: Optional[str] = Query(None, description="Filter by validation status: candidate, validated, needs_review, rejected"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> QuestionConceptsResponse:
    """Retrieve all canonical concepts assessed by a specific question."""
    service = ConceptQuestionMappingService(db)
    return service.get_question_concepts(workspace.id, question_id, status_filter=status)


@router.get(
    "/{workspace_id}/concepts/{concept_id}/questions",
    response_model=ConceptQuestionsResponse,
    summary="Get all questions assessing a concept",
)
def get_concept_questions(
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
    status: Optional[str] = Query(None, description="Filter by validation status: candidate, validated, needs_review, rejected"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> ConceptQuestionsResponse:
    """Retrieve all assessment questions that evaluate a canonical concept."""
    service = ConceptQuestionMappingService(db)
    return service.get_concept_questions(workspace.id, concept_id, status_filter=status)


@router.post(
    "/{workspace_id}/questions/{question_id}/concept-mappings/generate",
    response_model=List[QuestionConceptMappingResponse],
    summary="Discover candidate concept mappings for a question",
)
def generate_candidate_concept_mappings(
    workspace_id: uuid.UUID,
    question_id: uuid.UUID,
    auto_validate: bool = Query(False, description="Whether to automatically mark generated candidates as validated"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[QuestionConceptMappingResponse]:
    """Inspects question content against workspace KnowledgeNodes to generate candidate mappings."""
    service = ConceptQuestionMappingService(db)
    mappings = service.generate_mappings_for_question(workspace.id, question_id, auto_validate=auto_validate)

    results = []
    for m in mappings:
        concept_summary = None
        if m.concept:
            concept_summary = ConceptSummary(
                id=m.concept.id,
                name=m.concept.name,
                normalized_name=m.concept.normalized_name,
                node_type=m.concept.node_type,
                category=m.concept.category,
                description=m.concept.description,
            )
        results.append(
            QuestionConceptMappingResponse(
                id=m.id,
                workspace_id=m.workspace_id,
                question_id=m.question_id,
                question_type=m.question_type,
                concept_id=m.concept_id,
                concept=concept_summary,
                mapping_method=MappingMethod(m.mapping_method),
                confidence_score=m.confidence_score,
                validation_status=MappingValidationStatus(m.validation_status),
                evidence_excerpt=m.evidence_excerpt,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
        )
    return results


@router.patch(
    "/{workspace_id}/concept-mappings/{mapping_id}",
    response_model=QuestionConceptMappingResponse,
    summary="Update validation status or confidence of a mapping",
)
def update_question_concept_mapping(
    workspace_id: uuid.UUID,
    mapping_id: uuid.UUID,
    data: QuestionConceptMappingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> QuestionConceptMappingResponse:
    """Update validation state (validated, needs_review, rejected) or confidence score."""
    service = ConceptQuestionMappingService(db)
    mapping = service.update_mapping(workspace.id, mapping_id, data)

    concept_summary = None
    if mapping.concept:
        concept_summary = ConceptSummary(
            id=mapping.concept.id,
            name=mapping.concept.name,
            normalized_name=mapping.concept.normalized_name,
            node_type=mapping.concept.node_type,
            category=mapping.concept.category,
            description=mapping.concept.description,
        )

    return QuestionConceptMappingResponse(
        id=mapping.id,
        workspace_id=mapping.workspace_id,
        question_id=mapping.question_id,
        question_type=mapping.question_type,
        concept_id=mapping.concept_id,
        concept=concept_summary,
        mapping_method=MappingMethod(mapping.mapping_method),
        confidence_score=mapping.confidence_score,
        validation_status=MappingValidationStatus(mapping.validation_status),
        evidence_excerpt=mapping.evidence_excerpt,
        created_at=mapping.created_at,
        updated_at=mapping.updated_at,
    )


@router.delete(
    "/{workspace_id}/concept-mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a question-concept mapping",
)
def delete_question_concept_mapping(
    workspace_id: uuid.UUID,
    mapping_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    """Delete an erroneous or unneeded question-concept mapping."""
    service = ConceptQuestionMappingService(db)
    service.delete_mapping(workspace.id, mapping_id)
    return None


# =============================================================================
# C9.2: Learner Interaction Event Logging Endpoints
# =============================================================================

@router.post(
    "/{workspace_id}/learning-interactions/events",
    response_model=LearnerInteractionEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an individual learner interaction event",
)
def record_learner_interaction_event(
    workspace_id: uuid.UUID,
    event_data: LearnerInteractionEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> LearnerInteractionEventResponse:
    """Record a single interaction event (question navigation, answer choice, hint/source open, etc.)."""
    service = LearnerInteractionService(db)
    event = service.record_event(workspace.id, current_user.id, event_data)
    return LearnerInteractionEventResponse.model_validate(event)


@router.post(
    "/{workspace_id}/learning-interactions/events/batch",
    response_model=List[LearnerInteractionEventResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a batch of learner interaction events",
)
def record_learner_interaction_batch(
    workspace_id: uuid.UUID,
    batch_data: LearnerInteractionBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[LearnerInteractionEventResponse]:
    """Atomically record multiple interaction events."""
    service = LearnerInteractionService(db)
    events = service.record_batch_events(workspace.id, current_user.id, batch_data)
    return [LearnerInteractionEventResponse.model_validate(e) for e in events]


@router.get(
    "/{workspace_id}/learning-interactions/events",
    response_model=LearnerInteractionListResponse,
    summary="List paginated interaction events",
)
def list_learner_interaction_events(
    workspace_id: uuid.UUID,
    attempt_id: Optional[uuid.UUID] = Query(None, description="Filter by quiz attempt ID"),
    question_id: Optional[uuid.UUID] = Query(None, description="Filter by question ID"),
    concept_id: Optional[uuid.UUID] = Query(None, description="Filter by concept ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> LearnerInteractionListResponse:
    """Query workspace-scoped interaction events with filtering and pagination."""
    service = LearnerInteractionService(db)
    return service.list_events(
        workspace_id=workspace.id,
        user_id=current_user.id,
        attempt_id=attempt_id,
        question_id=question_id,
        concept_id=concept_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{workspace_id}/quiz-attempts/{attempt_id}/interactions",
    response_model=List[LearnerInteractionEventResponse],
    summary="Get chronological interactions for a quiz attempt",
)
def get_quiz_attempt_interactions(
    workspace_id: uuid.UUID,
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[LearnerInteractionEventResponse]:
    """Retrieve chronological interaction timeline for an attempt."""
    service = LearnerInteractionService(db)
    return service.get_attempt_interactions(workspace.id, attempt_id, current_user.id)


# =============================================================================
# C9.3: Quiz Attempt Tracking & Concept Performance Endpoints
# =============================================================================

@router.get(
    "/{workspace_id}/quiz-attempts/{attempt_id}/tracking",
    response_model=QuizAttemptTrackingResponse,
    summary="Get comprehensive operational tracking for a quiz attempt",
)
def get_quiz_attempt_tracking(
    workspace_id: uuid.UUID,
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> QuizAttemptTrackingResponse:
    """Retrieve operational tracking, question-level timing/revisions, and mapped concepts."""
    service = QuizAttemptTrackingService(db)
    return service.get_attempt_tracking(workspace.id, attempt_id, current_user.id)


@router.get(
    "/{workspace_id}/quiz-attempts/{attempt_id}/concept-performance",
    response_model=QuizAttemptConceptPerformanceResponse,
    summary="Get concept-level performance breakdown for an evaluated quiz attempt",
)
def get_quiz_attempt_concept_performance(
    workspace_id: uuid.UUID,
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> QuizAttemptConceptPerformanceResponse:
    """Calculates accuracy rate and question counts attributed to canonical concepts."""
    service = QuizAttemptTrackingService(db)
    return service.get_attempt_concept_performance(workspace.id, attempt_id, current_user.id)


@router.get(
    "/{workspace_id}/learning-interactions/summary",
    response_model=LearningInteractionsSummaryResponse,
    summary="Get aggregate interaction statistics for the workspace",
)
def get_learning_interactions_summary(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> LearningInteractionsSummaryResponse:
    """Summary metrics of learner engagement, hints opened, explanations, and active attempts."""
    service = QuizAttemptTrackingService(db)
    return service.get_interactions_summary(workspace.id)
