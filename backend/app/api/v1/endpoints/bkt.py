"""API endpoints for Bayesian Knowledge Tracing (Phase 9 Chunks C9.4, C9.5, C9.6).

Exposes:
- Parameter Estimation Runs & Model Registry (C9.5)
- Learner Concept Mastery State & Provenance History (C9.6)
"""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_user_workspace
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.models.bkt import BKTEstimationRun, BKTModelVersion
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.bkt import (
    BKTEstimationRunCreate,
    BKTEstimationRunResponse,
    BKTEvaluationRunCreate,
    BKTEvaluationRunResponse,
    BKTModelActivateRequest,
    BKTModelRollbackRequest,
    BKTModelVersionResponse,
    LearnerConceptMasteryHistoryResponse,
    LearnerConceptMasteryResponse,
    LearnerMasterySummaryResponse,
)
from backend.app.services.bkt_service import BKTService

logger = get_logger("knovera.api.bkt")

router = APIRouter()


# =============================================================================
# C9.5: Parameter Estimation & Model Version Management
# =============================================================================

@router.post(
    "/{workspace_id}/bkt/parameter-estimation-runs",
    response_model=BKTEstimationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger BKT parameter estimation run via EM/Baum-Welch",
)
def create_parameter_estimation_run(
    workspace_id: uuid.UUID,
    data: BKTEstimationRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> BKTEstimationRunResponse:
    """Estimates BKT parameters P(L0), P(T), P(G), P(S) from historical learner sequences."""
    service = BKTService(db)
    run = service.run_parameter_estimation(workspace.id, data)
    return BKTEstimationRunResponse.model_validate(run)


@router.get(
    "/{workspace_id}/bkt/parameter-estimation-runs",
    response_model=List[BKTEstimationRunResponse],
    summary="List parameter estimation runs in workspace",
)
def list_parameter_estimation_runs(
    workspace_id: uuid.UUID,
    concept_id: Optional[uuid.UUID] = Query(None, description="Filter by concept ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[BKTEstimationRunResponse]:
    """Retrieves history of BKT estimation runs."""
    query = db.query(BKTEstimationRun).filter(BKTEstimationRun.workspace_id == workspace.id)
    if concept_id:
        query = query.filter(BKTEstimationRun.concept_id == concept_id)
    runs = query.order_by(BKTEstimationRun.created_at.desc()).offset(offset).limit(limit).all()
    return [BKTEstimationRunResponse.model_validate(r) for r in runs]


@router.get(
    "/{workspace_id}/bkt/parameter-estimation-runs/{run_id}",
    response_model=BKTEstimationRunResponse,
    summary="Get details of a specific estimation run",
)
def get_parameter_estimation_run(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> BKTEstimationRunResponse:
    """Retrieves metadata, iterations, and convergence metrics for a run."""
    run = (
        db.query(BKTEstimationRun)
        .filter(BKTEstimationRun.id == run_id, BKTEstimationRun.workspace_id == workspace.id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimation run not found.")
    return BKTEstimationRunResponse.model_validate(run)


@router.get(
    "/{workspace_id}/bkt/models",
    response_model=List[BKTModelVersionResponse],
    summary="List versioned BKT parameter models",
)
def list_bkt_models(
    workspace_id: uuid.UUID,
    scope: Optional[str] = Query(None, description="global or concept_specific"),
    concept_id: Optional[uuid.UUID] = Query(None, description="Filter by concept ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[BKTModelVersionResponse]:
    """Lists candidate and active BKT parameter sets."""
    service = BKTService(db)
    models = service.list_model_versions(workspace.id, scope=scope, concept_id=concept_id)
    return [BKTModelVersionResponse.model_validate(m) for m in models]


@router.get(
    "/{workspace_id}/bkt/models/{model_version_id}",
    response_model=BKTModelVersionResponse,
    summary="Get BKT model version details",
)
def get_bkt_model_version(
    workspace_id: uuid.UUID,
    model_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> BKTModelVersionResponse:
    """Retrieves full parameters and validation metrics for a specific model version."""
    model = (
        db.query(BKTModelVersion)
        .filter(BKTModelVersion.id == model_version_id, BKTModelVersion.workspace_id == workspace.id)
        .first()
    )
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model version not found.")
    return BKTModelVersionResponse.model_validate(model)


@router.post(
    "/{workspace_id}/bkt/models/{model_version_id}/activate",
    response_model=BKTModelVersionResponse,
    summary="Activate candidate BKT model version",
)
def activate_bkt_model_version(
    workspace_id: uuid.UUID,
    model_version_id: uuid.UUID,
    body: BKTModelActivateRequest = BKTModelActivateRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> BKTModelVersionResponse:
    """Activates a fitted candidate model for live online mastery updates, enforcing readiness gates."""
    service = BKTService(db)
    activated = service.activate_model_version(workspace.id, model_version_id, force=body.force)
    return BKTModelVersionResponse.model_validate(activated)


@router.post(
    "/{workspace_id}/bkt/models/rollback",
    response_model=BKTModelVersionResponse,
    summary="Rollback active BKT model to previous version",
)
def rollback_bkt_model(
    workspace_id: uuid.UUID,
    body: BKTModelRollbackRequest = BKTModelRollbackRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> BKTModelVersionResponse:
    """Reverts active BKT model version to the previous archived or specified target version."""
    service = BKTService(db)
    rolled_back = service.rollback_model_version(workspace.id, body)
    return BKTModelVersionResponse.model_validate(rolled_back)


# =============================================================================
# C9.9: Offline BKT Model Evaluation & Validation Gates
# =============================================================================

@router.post(
    "/{workspace_id}/bkt/evaluation-runs",
    response_model=BKTEvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger offline evaluation run for a BKT model version",
)
def create_bkt_evaluation_run(
    workspace_id: uuid.UUID,
    data: BKTEvaluationRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> BKTEvaluationRunResponse:
    """Evaluates predictive Log Loss, Brier score, accuracy, calibration, and baselines on held-out data."""
    service = BKTService(db)
    run = service.run_offline_evaluation(workspace.id, data, user_id=current_user.id)
    return BKTEvaluationRunResponse.model_validate(run)


@router.get(
    "/{workspace_id}/bkt/evaluation-runs",
    response_model=List[BKTEvaluationRunResponse],
    summary="List BKT evaluation runs in workspace",
)
def list_bkt_evaluation_runs(
    workspace_id: uuid.UUID,
    model_version_id: Optional[uuid.UUID] = Query(None, description="Filter by model version ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[BKTEvaluationRunResponse]:
    """Lists statistical evaluation runs for models in the workspace."""
    service = BKTService(db)
    runs = service.list_evaluation_runs(workspace.id, model_version_id=model_version_id)
    return [BKTEvaluationRunResponse.model_validate(r) for r in runs]


@router.get(
    "/{workspace_id}/bkt/evaluation-runs/{run_id}",
    response_model=BKTEvaluationRunResponse,
    summary="Get details of a specific BKT evaluation run",
)
def get_bkt_evaluation_run(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> BKTEvaluationRunResponse:
    """Retrieves full evaluation report including calibration bins and baselines."""
    service = BKTService(db)
    run = service.get_evaluation_run(workspace.id, run_id)
    return BKTEvaluationRunResponse.model_validate(run)


@router.get(
    "/{workspace_id}/bkt/models/{model_version_id}/evaluation",
    response_model=List[BKTEvaluationRunResponse],
    summary="Get all evaluation runs for a model version",
)
def get_model_evaluation_runs(
    workspace_id: uuid.UUID,
    model_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[BKTEvaluationRunResponse]:
    """Retrieves all evaluation runs associated with a specific BKT model version."""
    service = BKTService(db)
    runs = service.list_evaluation_runs(workspace.id, model_version_id=model_version_id)
    return [BKTEvaluationRunResponse.model_validate(r) for r in runs]


# =============================================================================
# C9.6: Learner Concept Mastery & Provenance History
# =============================================================================

@router.get(
    "/{workspace_id}/bkt/learners/me/mastery",
    response_model=List[LearnerConceptMasteryResponse],
    summary="Get all concept masteries for authenticated learner",
)
def get_my_concept_masteries(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[LearnerConceptMasteryResponse]:
    """Retrieves the caller's current concept mastery probability states."""
    service = BKTService(db)
    return service.get_learner_masteries(workspace.id, current_user.id)


@router.get(
    "/{workspace_id}/bkt/learners/me/concepts/{concept_id}/mastery",
    response_model=LearnerConceptMasteryResponse,
    summary="Get learner mastery for a specific concept",
)
def get_my_single_concept_mastery(
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> LearnerConceptMasteryResponse:
    """Retrieves posterior and predicted next mastery probabilities for a single concept."""
    service = BKTService(db)
    return service.get_concept_mastery(workspace.id, current_user.id, concept_id)


@router.get(
    "/{workspace_id}/bkt/learners/me/concepts/{concept_id}/history",
    response_model=List[LearnerConceptMasteryHistoryResponse],
    summary="Get update history of a learner on a concept",
)
def get_my_concept_mastery_history(
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> List[LearnerConceptMasteryHistoryResponse]:
    """Retrieves the chronological audit log of Bayesian updates for this concept."""
    service = BKTService(db)
    return service.get_concept_mastery_history(workspace.id, current_user.id, concept_id)


@router.get(
    "/{workspace_id}/bkt/learners/me/mastery/summary",
    response_model=LearnerMasterySummaryResponse,
    summary="Get overall mastery summary for authenticated learner",
)
def get_my_mastery_summary(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
) -> LearnerMasterySummaryResponse:
    """Summarizes mastered, developing, and insufficient-data counts across concepts."""
    service = BKTService(db)
    return service.get_mastery_summary(workspace.id, current_user.id)
