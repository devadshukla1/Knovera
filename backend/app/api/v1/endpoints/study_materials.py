"""API endpoints for Knovera Study Material Generation (Phase 8).

Exposes:
- Revision Notes: generation, listing, detail retrieval (C8.1)
- MCQs: generation, practice mode & review mode retrieval (C8.2)
- Fill-in-the-Blanks: generation, practice mode & review mode retrieval (C8.3)
- True/False: generation, practice mode & review mode retrieval (C8.4)
- Flashcards: generation, retrieval, active recall decks (C8.5)
- Interactive Quizzes: attempt creation, answer saving, authoritative evaluation (C8.6)
- Generation run lifecycle telemetry & audit logs
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_user_workspace
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.ml.study_materials.evidence_service import AntiCheatShieldError
from backend.app.ml.study_materials.generation_service import StudyMaterialGenerationService
from backend.app.ml.study_materials.schemas import (
    FillBlankGenerateRequest,
    FillBlankPracticeResponse,
    FillBlankReviewResponse,
    FlashcardGenerateRequest,
    FlashcardResponse,
    MCQGenerateRequest,
    MCQPracticeResponse,
    MCQReviewResponse,
    QuestionExplanationResponse,
    QuestionSourcesResponse,
    QuizAttemptAnswerSaveRequest,
    QuizAttemptAnswerSubmit,
    QuizAttemptCreateRequest,
    QuizAttemptResponse,
    QuizAttemptResultResponse,
    QuizAttemptSummaryResponse,
    QuizHistoryListResponse,
    QuizHistorySummaryResponse,
    QuizHistoryTrendsResponse,
    RevisionNoteResponse,
    RevisionNotesGenerateRequest,
    StudyMaterialGenerationRunResponse,
    TrueFalseGenerateRequest,
    TrueFalsePracticeResponse,
    TrueFalseReviewResponse,
    ViewMode,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.repositories.study_material_repository import StudyMaterialRepository

logger = get_logger("knovera.api.study_materials")

router = APIRouter()


# =============================================================================
# Revision Notes Endpoints (C8.1)
# =============================================================================

@router.post(
    "/{workspace_id}/study-materials/revision-notes/generate",
    response_model=RevisionNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate structured revision notes",
)
async def generate_revision_notes(
    workspace_id: uuid.UUID,
    request: RevisionNotesGenerateRequest,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RevisionNoteResponse:
    """Generates structured revision notes from verified source documents in workspace."""
    service = StudyMaterialGenerationService(session=db)
    try:
        note_response, _ = await service.generate_revision_notes(
            workspace_id=workspace_id,
            request=request,
        )
        return note_response
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Failed to generate revision notes: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Study material generation failed: {str(exc)}",
        )


@router.get(
    "/{workspace_id}/study-materials/revision-notes",
    response_model=Dict[str, Any],
    summary="List revision notes for workspace",
)
def list_revision_notes(
    workspace_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves paginated revision notes in the authorized workspace."""
    repo = StudyMaterialRepository(db)
    notes, total = repo.list_revision_notes(workspace_id=workspace_id, limit=limit, offset=offset)
    return {
        "items": [RevisionNoteResponse.model_validate(n) for n in notes],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{workspace_id}/study-materials/revision-notes/{note_id}",
    response_model=RevisionNoteResponse,
    summary="Get single revision note",
)
def get_revision_note(
    workspace_id: uuid.UUID,
    note_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RevisionNoteResponse:
    """Retrieves single revision note with full section tree and formulas."""
    repo = StudyMaterialRepository(db)
    note = repo.get_revision_note(note_id=note_id, workspace_id=workspace_id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision note not found")
    return RevisionNoteResponse.model_validate(note)


# =============================================================================
# Multiple-Choice Questions (MCQ) Endpoints (C8.2)
# =============================================================================

@router.post(
    "/{workspace_id}/study-materials/mcqs/generate",
    response_model=List[MCQReviewResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate Multiple-Choice Questions",
)
async def generate_mcqs(
    workspace_id: uuid.UUID,
    request: MCQGenerateRequest,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[MCQReviewResponse]:
    """Generates source-grounded 4-option MCQs passing psychometric quality checks."""
    service = StudyMaterialGenerationService(session=db)
    try:
        mcqs, _ = await service.generate_mcqs(
            workspace_id=workspace_id,
            request=request,
        )
        return mcqs
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Failed to generate MCQs: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCQ generation failed: {str(exc)}",
        )


@router.get(
    "/{workspace_id}/study-materials/mcqs",
    response_model=Dict[str, Any],
    summary="List MCQs for workspace",
)
def list_mcqs(
    workspace_id: uuid.UUID,
    difficulty: Optional[str] = Query(default=None),
    question_type: Optional[str] = Query(default=None),
    mode: ViewMode = Query(default=ViewMode.PRACTICE),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Lists workspace MCQs with view mode protection (practice shields answer keys)."""
    repo = StudyMaterialRepository(db)
    service = StudyMaterialGenerationService(session=db)
    questions, total = repo.list_mcq_questions(
        workspace_id=workspace_id,
        difficulty=difficulty,
        question_type=question_type,
        limit=limit,
        offset=offset,
    )

    items = (
        [service.format_mcq_practice(q) for q in questions]
        if mode == ViewMode.PRACTICE
        else [service.format_mcq_review(q) for q in questions]
    )

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "mode": mode.value,
    }


@router.get(
    "/{workspace_id}/study-materials/mcqs/{question_id}",
    response_model=Union[MCQReviewResponse, MCQPracticeResponse],
    summary="Get single MCQ question",
)
def get_mcq(
    workspace_id: uuid.UUID,
    question_id: uuid.UUID,
    mode: ViewMode = Query(default=ViewMode.PRACTICE),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves single MCQ question."""
    repo = StudyMaterialRepository(db)
    service = StudyMaterialGenerationService(session=db)
    question = repo.get_mcq_question(question_id=question_id, workspace_id=workspace_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCQ not found")

    if mode == ViewMode.PRACTICE:
        return service.format_mcq_practice(question)
    return service.format_mcq_review(question)


# =============================================================================
# Fill-in-the-Blanks Endpoints (C8.3)
# =============================================================================

@router.post(
    "/{workspace_id}/study-materials/fill-blanks/generate",
    response_model=List[FillBlankReviewResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate Fill-in-the-Blank exercises",
)
async def generate_fill_blanks(
    workspace_id: uuid.UUID,
    request: FillBlankGenerateRequest,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[FillBlankReviewResponse]:
    """Generates unambiguous fill-in-the-blank items with precise char offsets."""
    service = StudyMaterialGenerationService(session=db)
    try:
        items, _ = await service.generate_fill_blanks(
            workspace_id=workspace_id,
            request=request,
        )
        return items
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Failed to generate Fill-in-the-Blanks: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fill-in-the-blank generation failed: {str(exc)}",
        )


@router.get(
    "/{workspace_id}/study-materials/fill-blanks",
    response_model=Dict[str, Any],
    summary="List Fill-in-the-Blank exercises for workspace",
)
def list_fill_blanks(
    workspace_id: uuid.UUID,
    difficulty: Optional[str] = Query(default=None),
    mode: ViewMode = Query(default=ViewMode.PRACTICE),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Lists fill-in-the-blanks with view mode protection."""
    repo = StudyMaterialRepository(db)
    service = StudyMaterialGenerationService(session=db)
    exercises, total = repo.list_fill_blank_exercises(
        workspace_id=workspace_id,
        difficulty=difficulty,
        limit=limit,
        offset=offset,
    )

    items = (
        [service.format_fill_blank_practice(ex) for ex in exercises]
        if mode == ViewMode.PRACTICE
        else [service.format_fill_blank_review(ex) for ex in exercises]
    )

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "mode": mode.value,
    }


@router.get(
    "/{workspace_id}/study-materials/fill-blanks/{exercise_id}",
    response_model=Union[FillBlankReviewResponse, FillBlankPracticeResponse],
    summary="Get single Fill-in-the-Blank exercise",
)
def get_fill_blank(
    workspace_id: uuid.UUID,
    exercise_id: uuid.UUID,
    mode: ViewMode = Query(default=ViewMode.PRACTICE),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves single fill-in-the-blank exercise."""
    repo = StudyMaterialRepository(db)
    service = StudyMaterialGenerationService(session=db)
    exercise = repo.get_fill_blank_exercise(exercise_id=exercise_id, workspace_id=workspace_id)
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    if mode == ViewMode.PRACTICE:
        return service.format_fill_blank_practice(exercise)
    return service.format_fill_blank_review(exercise)


# =============================================================================
# True/False Questions Endpoints (C8.4)
# =============================================================================

@router.post(
    "/{workspace_id}/study-materials/true-false/generate",
    response_model=List[TrueFalseReviewResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate True/False questions",
)
async def generate_true_false(
    workspace_id: uuid.UUID,
    request: TrueFalseGenerateRequest,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TrueFalseReviewResponse]:
    """Generates source-grounded True/False statements with misconception explanations."""
    service = StudyMaterialGenerationService(session=db)
    try:
        saved_items, _ = await service.generate_true_false(
            workspace_id=workspace_id,
            request=request,
        )
        return [service.format_true_false_review(q) for q in saved_items]
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Failed to generate True/False questions: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"True/False generation failed: {str(exc)}",
        )


@router.get(
    "/{workspace_id}/study-materials/true-false",
    response_model=Dict[str, Any],
    summary="List True/False questions for workspace",
)
def list_true_false(
    workspace_id: uuid.UUID,
    difficulty: Optional[str] = Query(default=None),
    mode: ViewMode = Query(default=ViewMode.PRACTICE),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Lists workspace True/False questions with view mode protection."""
    repo = StudyMaterialRepository(db)
    service = StudyMaterialGenerationService(session=db)
    questions, total = repo.list_true_false_questions(
        workspace_id=workspace_id,
        difficulty=difficulty,
        limit=limit,
        offset=offset,
    )

    items = (
        [service.format_true_false_practice(q) for q in questions]
        if mode == ViewMode.PRACTICE
        else [service.format_true_false_review(q) for q in questions]
    )

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "mode": mode.value,
    }


@router.get(
    "/{workspace_id}/study-materials/true-false/{question_id}",
    response_model=Union[TrueFalseReviewResponse, TrueFalsePracticeResponse],
    summary="Get single True/False question",
)
def get_true_false(
    workspace_id: uuid.UUID,
    question_id: uuid.UUID,
    mode: ViewMode = Query(default=ViewMode.PRACTICE),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Retrieves single True/False question."""
    repo = StudyMaterialRepository(db)
    service = StudyMaterialGenerationService(session=db)
    question = repo.get_true_false_question(question_id=question_id, workspace_id=workspace_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="True/False question not found")

    if mode == ViewMode.PRACTICE:
        return service.format_true_false_practice(question)
    return service.format_true_false_review(question)


# =============================================================================
# Flashcards Endpoints (C8.5)
# =============================================================================

@router.post(
    "/{workspace_id}/study-materials/flashcards/generate",
    response_model=List[FlashcardResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate Active Recall Flashcards",
)
async def generate_flashcards(
    workspace_id: uuid.UUID,
    request: FlashcardGenerateRequest,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[FlashcardResponse]:
    """Generates concise active-recall flashcards across 8 cognitive categories."""
    service = StudyMaterialGenerationService(session=db)
    try:
        saved_cards, _ = await service.generate_flashcards(
            workspace_id=workspace_id,
            request=request,
        )
        return [service.format_flashcard(c) for c in saved_cards]
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Failed to generate flashcards: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Flashcard generation failed: {str(exc)}",
        )


@router.get(
    "/{workspace_id}/study-materials/flashcards",
    response_model=Dict[str, Any],
    summary="List flashcards for workspace deck",
)
def list_flashcards(
    workspace_id: uuid.UUID,
    card_type: Optional[str] = Query(default=None),
    difficulty: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves paginated flashcards for active recall study."""
    repo = StudyMaterialRepository(db)
    service = StudyMaterialGenerationService(session=db)
    cards, total = repo.list_flashcards(
        workspace_id=workspace_id,
        card_type=card_type,
        difficulty=difficulty,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [service.format_flashcard(c) for c in cards],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{workspace_id}/study-materials/flashcards/{card_id}",
    response_model=FlashcardResponse,
    summary="Get single flashcard",
)
def get_flashcard(
    workspace_id: uuid.UUID,
    card_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FlashcardResponse:
    """Retrieves single flashcard with front/back payload."""
    repo = StudyMaterialRepository(db)
    service = StudyMaterialGenerationService(session=db)
    card = repo.get_flashcard(card_id=card_id, workspace_id=workspace_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found")
    return service.format_flashcard(card)


# =============================================================================
# Interactive Quiz Attempt Endpoints (C8.6)
# =============================================================================

@router.post(
    "/{workspace_id}/study-materials/quiz-attempts",
    response_model=QuizAttemptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create interactive quiz attempt (alias)",
)
@router.post(
    "/{workspace_id}/quiz-attempts",
    response_model=QuizAttemptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create interactive quiz attempt",
)
async def create_quiz_attempt(
    workspace_id: uuid.UUID,
    request: QuizAttemptCreateRequest,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizAttemptResponse:
    """Initializes a new interactive quiz attempt session with anti-cheat shielded questions."""
    service = StudyMaterialGenerationService(session=db)
    try:
        return await service.create_quiz_attempt(
            workspace_id=workspace_id,
            user_id=current_user.id,
            request=request,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error("Failed to create quiz attempt: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create quiz attempt: {str(exc)}",
        )


@router.get(
    "/{workspace_id}/quiz-attempts",
    response_model=Dict[str, Any],
    summary="List historical quiz attempts",
)
@router.get(
    "/{workspace_id}/quiz-history",
    response_model=Dict[str, Any],
    summary="List historical quiz attempts (history alias)",
)
def list_quiz_attempts(
    workspace_id: uuid.UUID,
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Lists historical quiz attempts in the authorized workspace with filtering, sorting and pagination."""
    repo = StudyMaterialRepository(db)
    attempts, total = repo.list_quiz_attempts(
        workspace_id=workspace_id,
        user_id=current_user.id,
        status=status,
        search=search,
        from_date=from_date,
        to_date=to_date,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [QuizAttemptSummaryResponse.model_validate(a) for a in attempts],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{workspace_id}/quiz-history/summary",
    response_model=QuizHistorySummaryResponse,
    summary="Get aggregate performance summary for quiz history",
)
def get_quiz_history_summary(
    workspace_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizHistorySummaryResponse:
    """Calculates aggregate score averages, accuracy rates, and completion counts."""
    service = StudyMaterialGenerationService(session=db)
    return service.get_quiz_history_summary(
        workspace_id=workspace_id,
        user_id=current_user.id,
    )


@router.get(
    "/{workspace_id}/quiz-history/trends",
    response_model=QuizHistoryTrendsResponse,
    summary="Get chronological score trends for evaluated quizzes",
)
def get_quiz_history_trends(
    workspace_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizHistoryTrendsResponse:
    """Extracts chronological trend points of completed assessments."""
    service = StudyMaterialGenerationService(session=db)
    return service.get_quiz_history_trends(
        workspace_id=workspace_id,
        user_id=current_user.id,
    )


@router.post(
    "/{workspace_id}/quiz-attempts/{attempt_id}/retake",
    response_model=QuizAttemptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Retake a previous quiz attempt",
)
def retake_quiz_attempt(
    workspace_id: uuid.UUID,
    attempt_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizAttemptResponse:
    """Initializes an independent new quiz attempt reproducing questions from previous session."""
    service = StudyMaterialGenerationService(session=db)
    try:
        return service.retake_quiz_attempt(
            workspace_id=workspace_id,
            attempt_id=attempt_id,
            user_id=current_user.id,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        )


@router.get(
    "/{workspace_id}/quiz-attempts/{attempt_id}",
    response_model=QuizAttemptResponse,
    summary="Get active quiz attempt state",
)
def get_quiz_attempt(
    workspace_id: uuid.UUID,
    attempt_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizAttemptResponse:
    """Retrieves active quiz runner state (sanitized questions, saved answers, timers)."""
    service = StudyMaterialGenerationService(session=db)
    try:
        return service.get_quiz_attempt(
            workspace_id=workspace_id,
            attempt_id=attempt_id,
            user_id=current_user.id,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        )


@router.put(
    "/{workspace_id}/quiz-attempts/{attempt_id}/answers",
    response_model=QuizAttemptResponse,
    summary="Save answers for active quiz attempt",
)
def save_quiz_answers(
    workspace_id: uuid.UUID,
    attempt_id: uuid.UUID,
    payload: QuizAttemptAnswerSaveRequest,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizAttemptResponse:
    """Saves learner's answers in an in-progress quiz without grading."""
    service = StudyMaterialGenerationService(session=db)
    try:
        return service.save_quiz_attempt_answers(
            workspace_id=workspace_id,
            attempt_id=attempt_id,
            answers=payload.answers,
            user_id=current_user.id,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )


@router.post(
    "/{workspace_id}/quiz-attempts/{attempt_id}/submit",
    response_model=QuizAttemptResultResponse,
    summary="Submit and evaluate quiz attempt",
)
def submit_quiz_attempt(
    workspace_id: uuid.UUID,
    attempt_id: uuid.UUID,
    payload: Optional[QuizAttemptAnswerSaveRequest] = None,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizAttemptResultResponse:
    """Submits and authoritatively evaluates quiz attempt on backend."""
    service = StudyMaterialGenerationService(session=db)
    try:
        return service.submit_quiz_attempt(
            workspace_id=workspace_id,
            attempt_id=attempt_id,
            answers=payload.answers if payload else None,
            user_id=current_user.id,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )


@router.get(
    "/{workspace_id}/quiz-attempts/{attempt_id}/results",
    response_model=QuizAttemptResultResponse,
    summary="Get verified quiz results report",
)
def get_quiz_results(
    workspace_id: uuid.UUID,
    attempt_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizAttemptResultResponse:
    """Retrieves full evaluation report, score percentage, and review answers."""
    service = StudyMaterialGenerationService(session=db)
    try:
        return service.get_quiz_attempt_results(
            workspace_id=workspace_id,
            attempt_id=attempt_id,
            user_id=current_user.id,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        )


@router.get(
    "/{workspace_id}/quiz-attempts/{attempt_id}/questions/{question_id}/explanation",
    response_model=QuestionExplanationResponse,
    summary="Get verified pedagogical explanation for a question in an evaluated quiz",
)
def get_question_explanation(
    workspace_id: uuid.UUID,
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionExplanationResponse:
    """Retrieves verified pedagogical explanation. Protected by anti-cheat shielding."""
    service = StudyMaterialGenerationService(session=db)
    try:
        return service.get_question_explanation(
            workspace_id=workspace_id,
            attempt_id=attempt_id,
            question_id=question_id,
            user_id=current_user.id,
        )
    except AntiCheatShieldError as ac_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(ac_err),
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        )


@router.get(
    "/{workspace_id}/quiz-attempts/{attempt_id}/questions/{question_id}/sources",
    response_model=QuestionSourcesResponse,
    summary="Get verified source citations for a question in an evaluated quiz",
)
def get_question_sources(
    workspace_id: uuid.UUID,
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionSourcesResponse:
    """Retrieves verified source citations and offsets. Protected by anti-cheat shielding."""
    service = StudyMaterialGenerationService(session=db)
    try:
        return service.get_question_sources(
            workspace_id=workspace_id,
            attempt_id=attempt_id,
            question_id=question_id,
            user_id=current_user.id,
        )
    except AntiCheatShieldError as ac_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(ac_err),
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        )


# =============================================================================
# Generation Runs Audit Telemetry
# =============================================================================

@router.get(
    "/{workspace_id}/study-materials/generations",
    response_model=Dict[str, Any],
    summary="List generation runs telemetry",
)
def list_generation_runs(
    workspace_id: uuid.UUID,
    material_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Lists historical study material generation runs and quality metrics."""
    repo = StudyMaterialRepository(db)
    runs, total = repo.list_generation_runs(
        workspace_id=workspace_id,
        material_type=material_type,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [StudyMaterialGenerationRunResponse.model_validate(r) for r in runs],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{workspace_id}/study-materials/generations/{generation_id}",
    response_model=StudyMaterialGenerationRunResponse,
    summary="Get generation run details",
)
def get_generation_run(
    workspace_id: uuid.UUID,
    generation_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudyMaterialGenerationRunResponse:
    """Retrieves single generation run audit record."""
    repo = StudyMaterialRepository(db)
    run = repo.get_generation_run(generation_id=generation_id, workspace_id=workspace_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation run not found")
    return StudyMaterialGenerationRunResponse.model_validate(run)
