"""API endpoints for Knovera Revision Recommendations (Phase 9 C9.7).

Exposes:
- Recommendation generation based on BKT mastery & quiz performance
- Recommendation listing, retrieval, and status updates
- Concept-level revision resource resolution
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
from backend.app.schemas.recommendation import (
    ConceptRevisionResourcesResponse,
    RevisionRecommendationGenerateRequest,
    RevisionRecommendationResponse,
    RevisionRecommendationStatusUpdate,
)
from backend.app.services.recommendation_service import RevisionRecommendationService

logger = get_logger("knovera.api.recommendations")

router = APIRouter()


@router.post(
    "/{workspace_id}/recommendations/generate",
    response_model=List[RevisionRecommendationResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate explainable revision recommendations for learner",
)
def generate_revision_recommendations(
    workspace_id: uuid.UUID,
    req: RevisionRecommendationGenerateRequest = RevisionRecommendationGenerateRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[RevisionRecommendationResponse]:
    """Evaluates learner concept states, evidence sufficiency, and quiz outcomes to produce ranked recommendations."""
    service = RevisionRecommendationService(db)
    recs = service.generate_recommendations(workspace.id, current_user.id, req)
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


@router.get(
    "/{workspace_id}/recommendations",
    response_model=List[RevisionRecommendationResponse],
    summary="List revision recommendations for authenticated learner",
)
def list_revision_recommendations(
    workspace_id: uuid.UUID,
    priority: Optional[str] = Query(None, description="high, medium, or low"),
    recommendation_type: Optional[str] = Query(None, description="Filter by recommendation type"),
    status_filter: Optional[str] = Query(None, alias="status", description="suggested, viewed, started, completed"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[RevisionRecommendationResponse]:
    """Retrieves active recommendations tailored to the caller."""
    service = RevisionRecommendationService(db)
    recs = service.list_recommendations(
        workspace_id=workspace.id,
        user_id=current_user.id,
        priority=priority,
        rec_type=recommendation_type,
        rec_status=status_filter,
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


@router.get(
    "/{workspace_id}/recommendations/{recommendation_id}",
    response_model=RevisionRecommendationResponse,
    summary="Get details of a revision recommendation",
)
def get_revision_recommendation(
    workspace_id: uuid.UUID,
    recommendation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> RevisionRecommendationResponse:
    """Retrieves a single recommendation ensuring workspace and user authorization."""
    service = RevisionRecommendationService(db)
    r = service.get_recommendation(workspace.id, recommendation_id, current_user.id)
    return RevisionRecommendationResponse(
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


@router.patch(
    "/{workspace_id}/recommendations/{recommendation_id}/status",
    response_model=RevisionRecommendationResponse,
    summary="Update recommendation lifecycle status",
)
def update_recommendation_status(
    workspace_id: uuid.UUID,
    recommendation_id: uuid.UUID,
    data: RevisionRecommendationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> RevisionRecommendationResponse:
    """Updates recommendation status to viewed, started, completed, or dismissed."""
    service = RevisionRecommendationService(db)
    r = service.update_recommendation_status(workspace.id, recommendation_id, current_user.id, data)
    return RevisionRecommendationResponse(
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


@router.get(
    "/{workspace_id}/concepts/{concept_id}/revision-resources",
    response_model=ConceptRevisionResourcesResponse,
    summary="Get all study materials linked to a concept",
)
def get_concept_revision_resources(
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> ConceptRevisionResourcesResponse:
    """Discovers notes, flashcards, questions, and source chunks for a canonical concept."""
    service = RevisionRecommendationService(db)
    return service.get_concept_revision_resources(workspace.id, concept_id)
