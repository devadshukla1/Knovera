"""API endpoints for Knovera Research Intelligence (Phase 10 C10.1, C10.2, C10.3).

Exposes:
- Full research document analysis orchestration
- C10.1 Bibliographic Metadata extraction, retrieval, and manual review
- C10.2 Research Objectives, Questions, and Hypotheses extraction
- C10.3 Research Methodology, Datasets, Variables, Setup, and Metrics
- Workspace research documents catalog
"""

from datetime import datetime, timezone
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_user_workspace
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.ml.research.comparison_service import MultiPaperComparisonService
from backend.app.ml.research.contradiction_service import ContradictionDetectionService
from backend.app.ml.research.coverage_service import DocumentCoverageService
from backend.app.ml.research.dashboard_service import ResearchDashboardService
from backend.app.ml.research.evidence_validation_service import EvidenceValidationService
from backend.app.ml.research.finding_service import ResearchFindingService
from backend.app.ml.research.nli_service import NLIInferenceService
from backend.app.ml.research.orchestrator import ResearchAnalysisOrchestrator
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.research_intelligence import (
    NLIEvaluationRun,
    NLIInferenceRecord,
    ResearchAnalysisRun,
    ResearchComparisonProfile,
    ResearchFinding,
    ResearchFindingComparison,
    ResearchMetadataProfile,
    ResearchMethodologyProfile,
    ResearchObjectiveProfile,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.research_intelligence import (
    ClaimedContributionItem,
    CompareFindingsNLIRequest,
    NLIEvaluationRunRequest,
    NLIEvaluationRunResponse,
    NLIInferenceRequest,
    NLIInferenceResponse,
    ResearchAnalysisOverviewResponse,
    ResearchAnalysisRunRequest,
    ResearchAnalysisRunResponse,
    ResearchComparisonCreateRequest,
    ResearchComparisonMatrixResponse,
    ResearchComparisonResponse,
    ResearchDocumentSummary,
    ResearchFindingComparisonResponse,
    ResearchFindingResponse,
    ResearchHypothesisItem,
    ResearchMetadataProfileResponse,
    ResearchMetadataProfileUpdate,
    ResearchMethodologyProfileResponse,
    ResearchMethodologyProfileUpdate,
    ResearchObjectiveItem,
    ResearchObjectiveProfileResponse,
    ResearchObjectiveProfileUpdate,
    ResearchQuestionItem,
    EvidenceValidationRequest,
    EvidenceValidationResponse,
    ValidateFindingRequest,
    ContradictionDetectRequest,
    ContradictionReviewRequest,
    ContradictionReviewResponse,
    ResearchContradictionResponse,
    CoverageRunRequest,
    CoverageGapItem,
    DocumentCoverageRunResponse,
    ResearchDashboardSummaryResponse,
)

logger = get_logger("knovera.api.research_intelligence")

router = APIRouter()


# ---------------------------------------------------------------------------
# Workspace Document Catalog
# ---------------------------------------------------------------------------

@router.get(
    "/{workspace_id}/research-documents",
    response_model=List[ResearchDocumentSummary],
    summary="List research documents and their intelligence analysis status",
)
def list_research_documents(
    workspace_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    orchestrator = ResearchAnalysisOrchestrator()
    return orchestrator.list_research_documents(db, workspace_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Orchestration Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{workspace_id}/documents/{document_id}/research-analysis",
    response_model=ResearchAnalysisRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run full or partial research document intelligence analysis",
)
def run_research_analysis(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    request: ResearchAnalysisRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    orchestrator = ResearchAnalysisOrchestrator()
    try:
        run = orchestrator.execute_analysis(db, workspace_id, document_id, request)
        return run
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Failed executing research analysis: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Analysis failed: {str(exc)}")


@router.get(
    "/{workspace_id}/documents/{document_id}/research-analysis",
    response_model=ResearchAnalysisOverviewResponse,
    summary="Get unified research document analysis overview",
)
def get_research_analysis_overview(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    orchestrator = ResearchAnalysisOrchestrator()
    try:
        return orchestrator.get_overview(db, workspace_id, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/{workspace_id}/documents/{document_id}/research-analysis/runs",
    response_model=List[ResearchAnalysisRunResponse],
    summary="List analysis execution runs for a document",
)
def list_analysis_runs(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    runs = list(
        db.execute(
            select(ResearchAnalysisRun)
            .where(
                ResearchAnalysisRun.workspace_id == workspace_id,
                ResearchAnalysisRun.document_id == document_id,
            )
            .order_by(ResearchAnalysisRun.created_at.desc())
        ).scalars().all()
    )
    return runs


@router.get(
    "/{workspace_id}/documents/{document_id}/research-analysis/runs/{run_id}",
    response_model=ResearchAnalysisRunResponse,
    summary="Get specific analysis run details",
)
def get_analysis_run(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    run = db.execute(
        select(ResearchAnalysisRun).where(
            ResearchAnalysisRun.id == run_id,
            ResearchAnalysisRun.workspace_id == workspace_id,
            ResearchAnalysisRun.document_id == document_id,
        )
    ).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research run not found.")
    return run


# ---------------------------------------------------------------------------
# C10.1 Research Metadata Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{workspace_id}/documents/{document_id}/research-metadata/extract",
    response_model=ResearchMetadataProfileResponse,
    summary="Extract or re-extract research document metadata (C10.1)",
)
def extract_metadata_endpoint(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    force_regenerate: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    orchestrator = ResearchAnalysisOrchestrator()
    req = ResearchAnalysisRunRequest(
        extract_metadata=True,
        extract_objectives=False,
        extract_methodology=False,
        force_regenerate=force_regenerate,
    )
    try:
        orchestrator.execute_analysis(db, workspace_id, document_id, req)
        profile = db.execute(
            select(ResearchMetadataProfile).where(
                ResearchMetadataProfile.workspace_id == workspace_id,
                ResearchMetadataProfile.document_id == document_id,
            )
        ).scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metadata profile extraction did not produce a record.")
        return profile
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{workspace_id}/documents/{document_id}/research-metadata",
    response_model=ResearchMetadataProfileResponse,
    summary="Get research document metadata profile",
)
def get_metadata_profile(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    profile = db.execute(
        select(ResearchMetadataProfile).where(
            ResearchMetadataProfile.workspace_id == workspace_id,
            ResearchMetadataProfile.document_id == document_id,
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research metadata profile not found.")
    return profile


@router.patch(
    "/{workspace_id}/documents/{document_id}/research-metadata",
    response_model=ResearchMetadataProfileResponse,
    summary="Manually review or edit research metadata profile",
)
@router.patch(
    "/{workspace_id}/documents/{document_id}/research-analysis/metadata",
    response_model=ResearchMetadataProfileResponse,
    include_in_schema=False,
)
def update_metadata_profile(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: ResearchMetadataProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    profile = db.execute(
        select(ResearchMetadataProfile).where(
            ResearchMetadataProfile.workspace_id == workspace_id,
            ResearchMetadataProfile.document_id == document_id,
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metadata profile not found.")

    update_data = payload.model_dump(exclude_unset=True)
    if "authors" in update_data and update_data["authors"] is not None:
        update_data["authors"] = [a if isinstance(a, dict) else a.model_dump() for a in update_data["authors"]]

    for field, val in update_data.items():
        setattr(profile, field, val)

    profile.is_manually_edited = True
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# C10.2 Research Objective Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{workspace_id}/documents/{document_id}/research-objectives/extract",
    response_model=ResearchObjectiveProfileResponse,
    summary="Extract or re-extract research objectives (C10.2)",
)
def extract_objectives_endpoint(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    force_regenerate: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    orchestrator = ResearchAnalysisOrchestrator()
    req = ResearchAnalysisRunRequest(
        extract_metadata=False,
        extract_objectives=True,
        extract_methodology=False,
        force_regenerate=force_regenerate,
    )
    try:
        orchestrator.execute_analysis(db, workspace_id, document_id, req)
        profile = db.execute(
            select(ResearchObjectiveProfile).where(
                ResearchObjectiveProfile.workspace_id == workspace_id,
                ResearchObjectiveProfile.document_id == document_id,
            )
        ).scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective profile extraction did not produce a record.")
        return profile
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{workspace_id}/documents/{document_id}/research-objectives",
    response_model=ResearchObjectiveProfileResponse,
    summary="Get research objective profile",
)
def get_objective_profile(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    profile = db.execute(
        select(ResearchObjectiveProfile).where(
            ResearchObjectiveProfile.workspace_id == workspace_id,
            ResearchObjectiveProfile.document_id == document_id,
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research objective profile not found.")
    return profile


@router.get(
    "/{workspace_id}/documents/{document_id}/research-questions",
    response_model=List[ResearchQuestionItem],
    summary="Get research questions list for document",
)
def get_research_questions(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    profile = db.execute(
        select(ResearchObjectiveProfile).where(
            ResearchObjectiveProfile.workspace_id == workspace_id,
            ResearchObjectiveProfile.document_id == document_id,
        )
    ).scalar_one_or_none()
    if not profile:
        return []
    return [ResearchQuestionItem.model_validate(q) for q in (profile.research_questions or [])]


@router.get(
    "/{workspace_id}/documents/{document_id}/research-hypotheses",
    response_model=List[ResearchHypothesisItem],
    summary="Get research hypotheses list for document",
)
def get_research_hypotheses(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    profile = db.execute(
        select(ResearchObjectiveProfile).where(
            ResearchObjectiveProfile.workspace_id == workspace_id,
            ResearchObjectiveProfile.document_id == document_id,
        )
    ).scalar_one_or_none()
    if not profile:
        return []
    return [ResearchHypothesisItem.model_validate(h) for h in (profile.hypotheses or [])]


@router.patch(
    "/{workspace_id}/documents/{document_id}/research-objectives",
    response_model=ResearchObjectiveProfileResponse,
    summary="Manually update research objective profile",
)
@router.patch(
    "/{workspace_id}/documents/{document_id}/research-analysis/objectives",
    response_model=ResearchObjectiveProfileResponse,
    include_in_schema=False,
)
def update_objective_profile(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: ResearchObjectiveProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    profile = db.execute(
        select(ResearchObjectiveProfile).where(
            ResearchObjectiveProfile.workspace_id == workspace_id,
            ResearchObjectiveProfile.document_id == document_id,
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective profile not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(profile, field, val)

    profile.is_manually_edited = True
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# C10.3 Research Methodology Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{workspace_id}/documents/{document_id}/research-methodology/extract",
    response_model=ResearchMethodologyProfileResponse,
    summary="Extract or re-extract research methodology (C10.3)",
)
def extract_methodology_endpoint(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    force_regenerate: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    orchestrator = ResearchAnalysisOrchestrator()
    req = ResearchAnalysisRunRequest(
        extract_metadata=False,
        extract_objectives=False,
        extract_methodology=True,
        force_regenerate=force_regenerate,
    )
    try:
        orchestrator.execute_analysis(db, workspace_id, document_id, req)
        profile = db.execute(
            select(ResearchMethodologyProfile).where(
                ResearchMethodologyProfile.workspace_id == workspace_id,
                ResearchMethodologyProfile.document_id == document_id,
            )
        ).scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Methodology profile extraction did not produce a record.")
        return profile
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{workspace_id}/documents/{document_id}/research-methodology",
    response_model=ResearchMethodologyProfileResponse,
    summary="Get research methodology profile",
)
def get_methodology_profile(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    profile = db.execute(
        select(ResearchMethodologyProfile).where(
            ResearchMethodologyProfile.workspace_id == workspace_id,
            ResearchMethodologyProfile.document_id == document_id,
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research methodology profile not found.")
    return profile


@router.patch(
    "/{workspace_id}/documents/{document_id}/research-methodology",
    response_model=ResearchMethodologyProfileResponse,
    summary="Manually update research methodology profile",
)
@router.patch(
    "/{workspace_id}/documents/{document_id}/research-analysis/methodology",
    response_model=ResearchMethodologyProfileResponse,
    include_in_schema=False,
)
def update_methodology_profile(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: ResearchMethodologyProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    profile = db.execute(
        select(ResearchMethodologyProfile).where(
            ResearchMethodologyProfile.workspace_id == workspace_id,
            ResearchMethodologyProfile.document_id == document_id,
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Methodology profile not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(profile, field, val)

    profile.is_manually_edited = True
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return profile


def enrich_finding_comparison(comp: ResearchFindingComparison) -> ResearchFindingComparisonResponse:
    paper_a_title = None
    paper_b_title = None
    finding_a_statement = None
    finding_b_statement = None
    evidence_a = []
    evidence_b = []

    if comp.finding_a:
        finding_a_statement = comp.finding_a.normalized_statement or comp.finding_a.original_statement
        evidence_a = comp.finding_a.evidence or []
        if comp.finding_a.document:
            doc_a = comp.finding_a.document
            doc_meta_a = getattr(doc_a, "extraction_metadata", {}) or {}
            paper_a_title = (
                doc_meta_a.get("file_title")
                if isinstance(doc_meta_a, dict)
                else None
            ) or getattr(doc_a, "title", None) or getattr(doc_a, "original_filename", "Paper A")

    if comp.finding_b:
        finding_b_statement = comp.finding_b.normalized_statement or comp.finding_b.original_statement
        evidence_b = comp.finding_b.evidence or []
        if comp.finding_b.document:
            doc_b = comp.finding_b.document
            doc_meta_b = getattr(doc_b, "extraction_metadata", {}) or {}
            paper_b_title = (
                doc_meta_b.get("file_title")
                if isinstance(doc_meta_b, dict)
                else None
            ) or getattr(doc_b, "title", None) or getattr(doc_b, "original_filename", "Paper B")

    return ResearchFindingComparisonResponse(
        id=comp.id,
        comparison_id=comp.comparison_id,
        finding_a_id=comp.finding_a_id,
        finding_b_id=comp.finding_b_id,
        paper_a_title=paper_a_title,
        paper_b_title=paper_b_title,
        finding_a_statement=finding_a_statement,
        finding_b_statement=finding_b_statement,
        outcome_variable=comp.outcome_variable,
        comparability_status=comp.comparability_status,
        preliminary_relationship=comp.preliminary_relationship,
        nli_relation=comp.nli_relation,
        final_relation=comp.final_relation,
        comparison_rationale=comp.comparison_rationale,
        contextual_differences=comp.contextual_differences or [],
        evidence_a=evidence_a,
        evidence_b=evidence_b,
        validation_status=comp.validation_status,
        created_at=comp.created_at,
    )


# ---------------------------------------------------------------------------
# C10.4 Multi-Paper Comparison Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{workspace_id}/research-comparisons",
    response_model=ResearchComparisonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create structured multi-paper comparison",
)
def create_research_comparison(
    workspace_id: uuid.UUID,
    request: ResearchComparisonCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = MultiPaperComparisonService()
    try:
        comparison = service.create_comparison(db, workspace_id, request, user_id=current_user.id)
        return comparison
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Failed creating research comparison: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Comparison failed: {str(exc)}")


@router.get(
    "/{workspace_id}/research-comparisons",
    response_model=List[ResearchComparisonResponse],
    summary="List multi-paper comparisons in workspace",
)
def list_research_comparisons(
    workspace_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    comparisons = list(
        db.execute(
            select(ResearchComparisonProfile)
            .where(ResearchComparisonProfile.workspace_id == workspace_id)
            .order_by(ResearchComparisonProfile.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()
    )
    return comparisons


@router.get(
    "/{workspace_id}/research-comparisons/{comparison_id}",
    response_model=ResearchComparisonResponse,
    summary="Get multi-paper comparison profile",
)
def get_research_comparison(
    workspace_id: uuid.UUID,
    comparison_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    comparison = db.execute(
        select(ResearchComparisonProfile).where(
            ResearchComparisonProfile.id == comparison_id,
            ResearchComparisonProfile.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if not comparison:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research comparison profile not found.")
    return comparison


@router.get(
    "/{workspace_id}/research-comparisons/{comparison_id}/matrix",
    response_model=ResearchComparisonMatrixResponse,
    summary="Get structured comparison matrix",
)
def get_research_comparison_matrix(
    workspace_id: uuid.UUID,
    comparison_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    comparison = db.execute(
        select(ResearchComparisonProfile).where(
            ResearchComparisonProfile.id == comparison_id,
            ResearchComparisonProfile.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if not comparison:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research comparison profile not found.")

    service = MultiPaperComparisonService()
    return service.get_comparison_matrix(db, comparison)


# ---------------------------------------------------------------------------
# C10.5 Research Finding Extraction and Alignment Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{workspace_id}/documents/{document_id}/research-findings/extract",
    response_model=List[ResearchFindingResponse],
    summary="Extract empirical findings from document chunks",
)
def extract_document_findings(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    doc = db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    chunks = list(
        db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        ).scalars().all()
    )
    if not chunks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document has no processed chunks.")

    service = ResearchFindingService()
    findings = service.extract_findings_for_document(db, doc, chunks)
    return findings


@router.get(
    "/{workspace_id}/documents/{document_id}/research-findings",
    response_model=List[ResearchFindingResponse],
    summary="List extracted empirical findings for a document",
)
def list_document_findings(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    findings = list(
        db.execute(
            select(ResearchFinding)
            .where(
                ResearchFinding.document_id == document_id,
                ResearchFinding.workspace_id == workspace_id,
            )
            .order_by(ResearchFinding.created_at.asc())
        ).scalars().all()
    )
    return findings


@router.post(
    "/{workspace_id}/research-comparisons/{comparison_id}/align-findings",
    response_model=List[ResearchFindingComparisonResponse],
    summary="Align findings across papers in a comparison",
)
def align_comparison_findings(
    workspace_id: uuid.UUID,
    comparison_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    comparison = db.execute(
        select(ResearchComparisonProfile).where(
            ResearchComparisonProfile.id == comparison_id,
            ResearchComparisonProfile.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if not comparison:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparison profile not found.")

    service = ResearchFindingService()
    comps = service.align_findings_for_comparison(db, comparison_id)
    return [enrich_finding_comparison(c) for c in comps]


@router.get(
    "/{workspace_id}/research-comparisons/{comparison_id}/finding-relations",
    response_model=List[ResearchFindingComparisonResponse],
    summary="List aligned finding relations for comparison",
)
def list_aligned_finding_relations(
    workspace_id: uuid.UUID,
    comparison_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    comps = list(
        db.execute(
            select(ResearchFindingComparison)
            .where(ResearchFindingComparison.comparison_id == comparison_id)
            .order_by(ResearchFindingComparison.created_at.desc())
        ).scalars().all()
    )
    return [enrich_finding_comparison(c) for c in comps]


# ---------------------------------------------------------------------------
# C10.6 NLI Model Integration & Benchmarking Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{workspace_id}/nli/infer",
    response_model=NLIInferenceResponse,
    summary="Run Natural Language Inference on premise/hypothesis pair",
)
def infer_nli_relation(
    workspace_id: uuid.UUID,
    request: NLIInferenceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = NLIInferenceService.get_instance()
    return service.infer_pair(
        db=db,
        workspace_id=workspace_id,
        premise=request.premise,
        hypothesis=request.hypothesis,
        premise_doc_id=request.premise_doc_id,
        hypothesis_doc_id=request.hypothesis_doc_id,
        bidirectional=request.bidirectional,
    )


@router.post(
    "/{workspace_id}/research-comparisons/{comparison_id}/evaluate-nli",
    response_model=List[ResearchFindingComparisonResponse],
    summary="Evaluate NLI across all aligned findings for a comparison",
)
def evaluate_comparison_nli(
    workspace_id: uuid.UUID,
    comparison_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    comparison = db.execute(
        select(ResearchComparisonProfile).where(
            ResearchComparisonProfile.id == comparison_id,
            ResearchComparisonProfile.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if not comparison:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparison not found.")

    finding_comps = list(
        db.execute(
            select(ResearchFindingComparison).where(
                ResearchFindingComparison.comparison_id == comparison_id
            )
        ).scalars().all()
    )

    nli_service = NLIInferenceService.get_instance()
    evaluated = []
    for fc in finding_comps:
        updated = nli_service.compare_findings(db, workspace_id, fc)
        evaluated.append(updated)

    return [enrich_finding_comparison(c) for c in evaluated]


@router.post(
    "/{workspace_id}/nli/evaluate",
    response_model=NLIEvaluationRunResponse,
    summary="Run NLI benchmark evaluation dataset",
)
def run_nli_benchmark_evaluation(
    workspace_id: uuid.UUID,
    request: NLIEvaluationRunRequest = NLIEvaluationRunRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    nli_service = NLIInferenceService.get_instance()
    try:
        run = nli_service.run_benchmark_evaluation(
            db=db,
            dataset_path=request.dataset_path,
            dataset_name=request.dataset_name,
            custom_pairs=request.custom_pairs,
            workspace_id=workspace_id,
        )
        return run
    except Exception as exc:
        logger.error("Benchmark evaluation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/{workspace_id}/nli/evaluations",
    response_model=List[NLIEvaluationRunResponse],
    summary="List NLI benchmark evaluation runs",
)
def list_nli_evaluations(
    workspace_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    runs = list(
        db.execute(
            select(NLIEvaluationRun)
            .where(
                (NLIEvaluationRun.workspace_id == workspace_id) | (NLIEvaluationRun.workspace_id.is_(None))
            )
            .order_by(NLIEvaluationRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()
    )
    return runs


# ---------------------------------------------------------------------------
# C10.7 Evidence Validation Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{workspace_id}/evidence/validate",
    response_model=EvidenceValidationResponse,
    summary="Validate claim or statement against document source chunks (C10.7)",
)
def validate_evidence(
    workspace_id: uuid.UUID,
    request: EvidenceValidationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = EvidenceValidationService(db=db)
    try:
        return service.validate_claim(workspace_id=workspace_id, request=request)
    except Exception as exc:
        logger.error("Evidence validation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/{workspace_id}/evidence/validate-finding/{finding_id}",
    response_model=EvidenceValidationResponse,
    summary="Validate research finding against source passage (C10.7)",
)
def validate_finding(
    workspace_id: uuid.UUID,
    finding_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = EvidenceValidationService(db=db)
    try:
        return service.validate_finding(workspace_id=workspace_id, finding_id=finding_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Finding validation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/{workspace_id}/evidence/validations",
    response_model=List[EvidenceValidationResponse],
    summary="List evidence validation records for workspace (C10.7)",
)
def list_validations(
    workspace_id: uuid.UUID,
    document_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = EvidenceValidationService(db=db)
    return service.list_validations(workspace_id=workspace_id, document_id=document_id, status=status, limit=limit)


# ---------------------------------------------------------------------------
# C10.8 Contradiction Detection Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{workspace_id}/contradictions/detect",
    response_model=ResearchContradictionResponse,
    summary="Detect potential contradictions between two research findings (C10.8)",
)
def detect_contradiction(
    workspace_id: uuid.UUID,
    request: ContradictionDetectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = ContradictionDetectionService(db=db)
    try:
        record = service.detect_contradiction(workspace_id=workspace_id, request=request)
        fa = db.execute(select(ResearchFinding).where(ResearchFinding.id == record.finding_a_id)).scalar_one_or_none()
        fb = db.execute(select(ResearchFinding).where(ResearchFinding.id == record.finding_b_id)).scalar_one_or_none()
        da = db.execute(select(Document).where(Document.id == record.document_a_id)).scalar_one_or_none()
        db_doc = db.execute(select(Document).where(Document.id == record.document_b_id)).scalar_one_or_none()

        res_dict = {
            "id": record.id,
            "workspace_id": record.workspace_id,
            "comparison_id": record.comparison_id,
            "finding_a_id": record.finding_a_id,
            "finding_b_id": record.finding_b_id,
            "document_a_id": record.document_a_id,
            "document_b_id": record.document_b_id,
            "finding_a_statement": fa.original_statement if fa else None,
            "finding_b_statement": fb.original_statement if fb else None,
            "paper_a_title": da.original_filename if da else None,
            "paper_b_title": db_doc.original_filename if db_doc else None,
            "contradiction_category": record.contradiction_category,
            "evidence_validity_a": record.evidence_validity_a,
            "evidence_validity_b": record.evidence_validity_b,
            "comparability_status": record.comparability_status,
            "contextual_differences": record.contextual_differences,
            "stage_breakdown": record.stage_breakdown,
            "confidence_score": record.confidence_score,
            "nli_relation": record.nli_relation,
            "review_status": record.review_status,
            "human_verified": record.human_verified,
            "reviewer_notes": record.reviewer_notes,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "reviews": [],
        }
        return ResearchContradictionResponse.model_validate(res_dict)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Contradiction detection failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/{workspace_id}/contradictions",
    response_model=List[ResearchContradictionResponse],
    summary="List contradiction records for workspace (C10.8)",
)
def list_contradictions(
    workspace_id: uuid.UUID,
    category: Optional[str] = Query(None),
    review_status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = ContradictionDetectionService(db=db)
    records = service.list_contradictions(
        workspace_id=workspace_id,
        category=category,
        review_status=review_status,
        limit=limit,
    )
    result = []
    for r in records:
        fa = db.execute(select(ResearchFinding).where(ResearchFinding.id == r.finding_a_id)).scalar_one_or_none()
        fb = db.execute(select(ResearchFinding).where(ResearchFinding.id == r.finding_b_id)).scalar_one_or_none()
        da = db.execute(select(Document).where(Document.id == r.document_a_id)).scalar_one_or_none()
        db_doc = db.execute(select(Document).where(Document.id == r.document_b_id)).scalar_one_or_none()
        res_dict = {
            "id": r.id,
            "workspace_id": r.workspace_id,
            "comparison_id": r.comparison_id,
            "finding_a_id": r.finding_a_id,
            "finding_b_id": r.finding_b_id,
            "document_a_id": r.document_a_id,
            "document_b_id": r.document_b_id,
            "finding_a_statement": fa.original_statement if fa else None,
            "finding_b_statement": fb.original_statement if fb else None,
            "paper_a_title": da.original_filename if da else None,
            "paper_b_title": db_doc.original_filename if db_doc else None,
            "contradiction_category": r.contradiction_category,
            "evidence_validity_a": r.evidence_validity_a,
            "evidence_validity_b": r.evidence_validity_b,
            "comparability_status": r.comparability_status,
            "contextual_differences": r.contextual_differences,
            "stage_breakdown": r.stage_breakdown,
            "confidence_score": r.confidence_score,
            "nli_relation": r.nli_relation,
            "review_status": r.review_status,
            "human_verified": r.human_verified,
            "reviewer_notes": r.reviewer_notes,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "reviews": [
                {
                    "id": rev.id,
                    "contradiction_id": rev.contradiction_id,
                    "user_id": rev.user_id,
                    "previous_status": rev.previous_status,
                    "new_status": rev.new_status,
                    "review_action": rev.review_action,
                    "review_notes": rev.review_notes,
                    "created_at": rev.created_at,
                }
                for rev in (r.reviews or [])
            ],
        }
        result.append(ResearchContradictionResponse.model_validate(res_dict))
    return result


@router.post(
    "/{workspace_id}/contradictions/{contradiction_id}/review",
    response_model=ResearchContradictionResponse,
    summary="Submit human review decision on contradiction candidate (C10.8)",
)
def review_contradiction(
    workspace_id: uuid.UUID,
    contradiction_id: uuid.UUID,
    request: ContradictionReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = ContradictionDetectionService(db=db)
    try:
        r = service.review_contradiction(
            workspace_id=workspace_id,
            contradiction_id=contradiction_id,
            request=request,
            user_id=current_user.id,
        )
        fa = db.execute(select(ResearchFinding).where(ResearchFinding.id == r.finding_a_id)).scalar_one_or_none()
        fb = db.execute(select(ResearchFinding).where(ResearchFinding.id == r.finding_b_id)).scalar_one_or_none()
        da = db.execute(select(Document).where(Document.id == r.document_a_id)).scalar_one_or_none()
        db_doc = db.execute(select(Document).where(Document.id == r.document_b_id)).scalar_one_or_none()
        res_dict = {
            "id": r.id,
            "workspace_id": r.workspace_id,
            "comparison_id": r.comparison_id,
            "finding_a_id": r.finding_a_id,
            "finding_b_id": r.finding_b_id,
            "document_a_id": r.document_a_id,
            "document_b_id": r.document_b_id,
            "finding_a_statement": fa.original_statement if fa else None,
            "finding_b_statement": fb.original_statement if fb else None,
            "paper_a_title": da.original_filename if da else None,
            "paper_b_title": db_doc.original_filename if db_doc else None,
            "contradiction_category": r.contradiction_category,
            "evidence_validity_a": r.evidence_validity_a,
            "evidence_validity_b": r.evidence_validity_b,
            "comparability_status": r.comparability_status,
            "contextual_differences": r.contextual_differences,
            "stage_breakdown": r.stage_breakdown,
            "confidence_score": r.confidence_score,
            "nli_relation": r.nli_relation,
            "review_status": r.review_status,
            "human_verified": r.human_verified,
            "reviewer_notes": r.reviewer_notes,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "reviews": [
                {
                    "id": rev.id,
                    "contradiction_id": rev.contradiction_id,
                    "user_id": rev.user_id,
                    "previous_status": rev.previous_status,
                    "new_status": rev.new_status,
                    "review_action": rev.review_action,
                    "review_notes": rev.review_notes,
                    "created_at": rev.created_at,
                }
                for rev in (r.reviews or [])
            ],
        }
        return ResearchContradictionResponse.model_validate(res_dict)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Review action failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ---------------------------------------------------------------------------
# C10.9 Document Coverage Gap Analysis Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{workspace_id}/coverage/runs",
    response_model=DocumentCoverageRunResponse,
    summary="Trigger multi-document coverage gap analysis (C10.9)",
)
def create_coverage_run(
    workspace_id: uuid.UUID,
    request: CoverageRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = DocumentCoverageService(db=db)
    try:
        return service.analyze_coverage(workspace_id=workspace_id, request=request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Coverage analysis failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/{workspace_id}/coverage/runs",
    response_model=List[DocumentCoverageRunResponse],
    summary="List past coverage analysis runs (C10.9)",
)
def list_coverage_runs(
    workspace_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = DocumentCoverageService(db=db)
    return service.list_runs(workspace_id=workspace_id, limit=limit)


@router.get(
    "/{workspace_id}/coverage/runs/{run_id}",
    response_model=DocumentCoverageRunResponse,
    summary="Get single coverage analysis run details (C10.9)",
)
def get_coverage_run(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = DocumentCoverageService(db=db)
    run = service.get_run(workspace_id=workspace_id, run_id=run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Coverage run {run_id} not found")
    return run


# ---------------------------------------------------------------------------
# C10.10 Research Intelligence Dashboard Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{workspace_id}/dashboard",
    response_model=ResearchDashboardSummaryResponse,
    summary="Get consolidated research intelligence dashboard metrics (C10.10)",
)
def get_research_dashboard(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_user_workspace),
):
    service = ResearchDashboardService(db=db)
    try:
        return service.get_dashboard_summary(workspace_id=workspace_id)
    except Exception as exc:
        logger.error("Dashboard summary failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

