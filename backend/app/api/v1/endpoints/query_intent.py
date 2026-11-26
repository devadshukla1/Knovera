"""FastAPI endpoints for Query Intent Prediction and Health Diagnostics (Phase 5 C5.8)."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.ml.query_intent.service import (
    QueryIntentInferenceError,
    QueryIntentModelUnavailableError,
    QueryIntentService,
    QueryIntentValidationError,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.query_intent import (
    QueryIntentReadinessResponse,
    QueryIntentRequest,
    QueryIntentResponse,
    TopIntentScore,
)

logger = get_logger("knovera.api.query_intent")
router = APIRouter()


def _get_query_intent_service() -> QueryIntentService:
    """Dependency provider for QueryIntentService singleton."""
    return QueryIntentService.get_instance()


@router.post(
    "/predict",
    response_model=QueryIntentResponse,
    status_code=status.HTTP_200_OK,
    summary="Classify query into an authoritative intent category",
)
@router.post(
    "",
    response_model=QueryIntentResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def predict_query_intent(
    payload: QueryIntentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: QueryIntentService = Depends(_get_query_intent_service),
) -> QueryIntentResponse:
    """Classifies user query intent using the approved machine learning model.

    Enforces authentication, validates optional workspace authorization,
    and returns authoritative intent predictions with confidence scores.
    """
    # 1. Workspace access validation (if workspace_id supplied)
    if payload.workspace_id is not None:
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == payload.workspace_id)
            .first()
        )
        if not workspace:
            logger.warning(
                "Workspace not found: workspace_id=%s",
                payload.workspace_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

    # 2. Query execution via non-blocking service
    try:
        prediction = await service.predict(payload.query)
        top_intents = [
            TopIntentScore(intent=item["intent"], score=item["score"])
            for item in prediction.top_intents
        ]
        return QueryIntentResponse(
            predicted_intent=prediction.predicted_intent,
            top_intents=top_intents,
            prediction_score=prediction.prediction_score,
            confidence_type=prediction.confidence_type,
            model_type=prediction.model_type,
            model_version=prediction.model_id,
            taxonomy_version=prediction.taxonomy_version,
            preprocessing_version=prediction.preprocessing_version,
            prediction_latency_ms=prediction.prediction_latency_ms,
            sanitized_query=prediction.sanitized_query,
        )
    except QueryIntentValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err),
        )
    except QueryIntentModelUnavailableError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(err),
        )
    except QueryIntentInferenceError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query intent inference failed",
        )
    except Exception as err:
        logger.error("Unhandled error in query intent prediction: %s", err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal query intent classification failure",
        )


@router.get(
    "/readiness",
    response_model=QueryIntentReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get query intent model readiness diagnostics",
)
def get_query_intent_readiness(
    service: QueryIntentService = Depends(_get_query_intent_service),
) -> QueryIntentReadinessResponse:
    """Returns runtime model readiness status, taxonomy version, and loaded model metadata."""
    readiness = service.is_ready()
    return QueryIntentReadinessResponse(**readiness)
