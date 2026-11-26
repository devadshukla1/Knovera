"""API endpoints for Knovera Learning Analytics Dashboard (Phase 9 C9.8).

Exposes:
- Overview KPIs
- Detailed Quiz Performance Metrics
- Chronological Quiz Score Trends
- Concept-Level Performance Attribution
- Latent BKT Mastery Projections
- Meaningful Educational Activity Timeline
- Revision Recommendations Panel
"""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_user_workspace
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.analytics import (
    ActivityTimelineResponse,
    AnalyticsOverviewResponse,
    ConceptAnalyticsResponse,
    MasteryAnalyticsResponse,
    QuizPerformanceResponse,
    ScoreHistoryResponse,
)
from backend.app.schemas.recommendation import RevisionRecommendationResponse
from backend.app.services.analytics_service import LearningAnalyticsService
from backend.app.services.recommendation_service import RevisionRecommendationService

logger = get_logger("knovera.api.learning_analytics")

router = APIRouter()


@router.get(
    "/{workspace_id}/learning-analytics/overview",
    response_model=AnalyticsOverviewResponse,
    summary="Get learning analytics overview KPIs",
)
def get_analytics_overview(
    workspace_id: uuid.UUID,
    date_filter: str = Query("all", description="7d, 30d, 90d, or all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> AnalyticsOverviewResponse:
    """Computes high-level educational KPIs for the learner in the workspace."""
    service = LearningAnalyticsService(db)
    return service.get_overview(workspace.id, current_user.id, date_filter=date_filter)


@router.get(
    "/{workspace_id}/learning-analytics/quiz-performance",
    response_model=QuizPerformanceResponse,
    summary="Get detailed quiz assessment performance",
)
def get_quiz_performance(
    workspace_id: uuid.UUID,
    date_filter: str = Query("all", description="7d, 30d, 90d, or all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> QuizPerformanceResponse:
    """Returns aggregated score metrics, question distribution, and overall accuracy."""
    service = LearningAnalyticsService(db)
    return service.get_quiz_performance(workspace.id, current_user.id, date_filter=date_filter)


@router.get(
    "/{workspace_id}/learning-analytics/score-history",
    response_model=ScoreHistoryResponse,
    summary="Get chronological quiz score history",
)
def get_score_history(
    workspace_id: uuid.UUID,
    date_filter: str = Query("all", description="7d, 30d, 90d, or all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> ScoreHistoryResponse:
    """Returns time-series data points of evaluated quiz attempts for score trend charts."""
    service = LearningAnalyticsService(db)
    return service.get_score_history(workspace.id, current_user.id, date_filter=date_filter)


@router.get(
    "/{workspace_id}/learning-analytics/concepts",
    response_model=ConceptAnalyticsResponse,
    summary="Get concept-level performance attribution",
)
def get_concept_analytics(
    workspace_id: uuid.UUID,
    date_filter: str = Query("all", description="7d, 30d, 90d, or all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> ConceptAnalyticsResponse:
    """Returns breakdown of accuracy, questions attempted, and evidence sufficiency per canonical concept."""
    service = LearningAnalyticsService(db)
    return service.get_concept_analytics(workspace.id, current_user.id, date_filter=date_filter)


@router.get(
    "/{workspace_id}/learning-analytics/mastery",
    response_model=MasteryAnalyticsResponse,
    summary="Get latent BKT concept mastery overview",
)
def get_mastery_analytics(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> MasteryAnalyticsResponse:
    """Returns BKT mastery projections and model validation qualification status."""
    service = LearningAnalyticsService(db)
    return service.get_mastery_overview(workspace.id, current_user.id)


@router.get(
    "/{workspace_id}/learning-analytics/activity",
    response_model=ActivityTimelineResponse,
    summary="Get educational activity timeline",
)
def get_activity_timeline(
    workspace_id: uuid.UUID,
    limit: int = Query(30, ge=5, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> ActivityTimelineResponse:
    """Returns chronological timeline of meaningful interaction events."""
    service = LearningAnalyticsService(db)
    return service.get_activity_timeline(workspace.id, current_user.id, limit=limit)


@router.get(
    "/{workspace_id}/learning-analytics/recommendations",
    response_model=List[RevisionRecommendationResponse],
    summary="Get dashboard revision recommendations panel",
)
def get_dashboard_recommendations(
    workspace_id: uuid.UUID,
    priority: Optional[str] = Query(None, description="high, medium, or low"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[RevisionRecommendationResponse]:
    """Retrieves active revision recommendations directly for the dashboard panel."""
    rec_service = RevisionRecommendationService(db)
    recs = rec_service.list_recommendations(
        workspace_id=workspace.id,
        user_id=current_user.id,
        priority=priority,
    )
    return [
        RevisionRecommendationResponse(
            id=r.id,
            workspace_id=r.workspace_id,
            user_id=r.user_id,
            concept_id=r.concept_id,
            concept_name=r.concept.name if r.concept else None,
            concept_description=r.concept.description if r.concept else None,
            recommendation_type=r.recommendation_type,
            priority=r.priority,
            explanation=r.explanation,
            evidence_summary=r.evidence_summary or {},
            model_version_id=r.model_version_id,
            status=r.status,
            linked_resources=r.linked_resources or {},
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in recs
    ]
