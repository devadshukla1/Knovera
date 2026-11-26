"""Service for C10.10: Consolidated Research Intelligence Dashboard.

Aggregates workspace-wide research metrics, evidence verification statuses,
empirical contradiction candidates, and multi-document coverage gaps for full-stack presentation.
"""

from collections import Counter
import logging
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.app.models.document import Document
from backend.app.models.research_intelligence import (
    DocumentCoverageAnalysisRun,
    DocumentCoverageGap,
    ResearchAnalysisRun,
    ResearchComparisonProfile,
    ResearchContradictionRecord,
    ResearchEvidenceValidationRecord,
    ResearchFinding,
    ResearchMetadataProfile,
    ResearchMethodologyProfile,
    ResearchObjectiveProfile,
)
from backend.app.schemas.research_intelligence import (
    CoverageGapItem,
    EvidenceValidationResponse,
    ResearchContradictionResponse,
    ResearchDashboardSummaryResponse,
)

logger = logging.getLogger(__name__)


class ResearchDashboardService:
    """Consolidates high-performance projections for research intelligence overview."""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_summary(
        self,
        workspace_id: uuid.UUID,
    ) -> ResearchDashboardSummaryResponse:
        """Compute aggregated research intelligence summary for a workspace."""
        # 1. Total documents in workspace
        total_docs = self.db.execute(
            select(func.count(Document.id)).where(Document.workspace_id == workspace_id)
        ).scalar_one() or 0

        # 2. Extraction profile counts
        meta_count = self.db.execute(
            select(func.count(ResearchMetadataProfile.id)).where(ResearchMetadataProfile.workspace_id == workspace_id)
        ).scalar_one() or 0

        obj_count = self.db.execute(
            select(func.count(ResearchObjectiveProfile.id)).where(ResearchObjectiveProfile.workspace_id == workspace_id)
        ).scalar_one() or 0

        meth_count = self.db.execute(
            select(func.count(ResearchMethodologyProfile.id)).where(ResearchMethodologyProfile.workspace_id == workspace_id)
        ).scalar_one() or 0

        # 3. Comparisons and findings
        comp_count = self.db.execute(
            select(func.count(ResearchComparisonProfile.id)).where(ResearchComparisonProfile.workspace_id == workspace_id)
        ).scalar_one() or 0

        finding_count = self.db.execute(
            select(func.count(ResearchFinding.id)).where(ResearchFinding.workspace_id == workspace_id)
        ).scalar_one() or 0

        # 4. Evidence validation breakdown
        val_rows = self.db.execute(
            select(ResearchEvidenceValidationRecord.validation_status, func.count(ResearchEvidenceValidationRecord.id))
            .where(ResearchEvidenceValidationRecord.workspace_id == workspace_id)
            .group_by(ResearchEvidenceValidationRecord.validation_status)
        ).all()
        validation_stats = {status: count for status, count in val_rows}

        # 5. Contradiction breakdown
        contra_rows = self.db.execute(
            select(ResearchContradictionRecord.review_status, func.count(ResearchContradictionRecord.id))
            .where(ResearchContradictionRecord.workspace_id == workspace_id)
            .group_by(ResearchContradictionRecord.review_status)
        ).all()
        contradiction_stats = {status: count for status, count in contra_rows}

        # 6. Coverage stats
        cov_runs_count = self.db.execute(
            select(func.count(DocumentCoverageAnalysisRun.id)).where(DocumentCoverageAnalysisRun.workspace_id == workspace_id)
        ).scalar_one() or 0

        gap_rows = self.db.execute(
            select(DocumentCoverageGap.severity, func.count(DocumentCoverageGap.id))
            .where(DocumentCoverageGap.workspace_id == workspace_id)
            .group_by(DocumentCoverageGap.severity)
        ).all()
        gap_stats = {sev: count for sev, count in gap_rows}

        # 7. Recent records
        recent_validations = list(
            self.db.execute(
                select(ResearchEvidenceValidationRecord)
                .where(ResearchEvidenceValidationRecord.workspace_id == workspace_id)
                .order_by(ResearchEvidenceValidationRecord.created_at.desc())
                .limit(10)
            ).scalars().all()
        )

        recent_contradictions = list(
            self.db.execute(
                select(ResearchContradictionRecord)
                .where(ResearchContradictionRecord.workspace_id == workspace_id)
                .options(joinedload(ResearchContradictionRecord.reviews))
                .order_by(ResearchContradictionRecord.created_at.desc())
                .limit(10)
            ).unique().scalars().all()
        )

        # Enrich contradictions with statements
        enriched_contradictions = []
        for c in recent_contradictions:
            fa = self.db.execute(select(ResearchFinding).where(ResearchFinding.id == c.finding_a_id)).scalar_one_or_none()
            fb = self.db.execute(select(ResearchFinding).where(ResearchFinding.id == c.finding_b_id)).scalar_one_or_none()
            da = self.db.execute(select(Document).where(Document.id == c.document_a_id)).scalar_one_or_none()
            db = self.db.execute(select(Document).where(Document.id == c.document_b_id)).scalar_one_or_none()

            contra_dict = {
                "id": c.id,
                "workspace_id": c.workspace_id,
                "comparison_id": c.comparison_id,
                "finding_a_id": c.finding_a_id,
                "finding_b_id": c.finding_b_id,
                "document_a_id": c.document_a_id,
                "document_b_id": c.document_b_id,
                "finding_a_statement": fa.original_statement if fa else None,
                "finding_b_statement": fb.original_statement if fb else None,
                "paper_a_title": da.original_filename if da else None,
                "paper_b_title": db.original_filename if db else None,
                "contradiction_category": c.contradiction_category,
                "evidence_validity_a": c.evidence_validity_a,
                "evidence_validity_b": c.evidence_validity_b,
                "comparability_status": c.comparability_status,
                "contextual_differences": c.contextual_differences,
                "stage_breakdown": c.stage_breakdown,
                "confidence_score": c.confidence_score,
                "nli_relation": c.nli_relation,
                "review_status": c.review_status,
                "human_verified": c.human_verified,
                "reviewer_notes": c.reviewer_notes,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "reviews": [
                    {
                        "id": r.id,
                        "contradiction_id": r.contradiction_id,
                        "user_id": r.user_id,
                        "previous_status": r.previous_status,
                        "new_status": r.new_status,
                        "review_action": r.review_action,
                        "review_notes": r.review_notes,
                        "created_at": r.created_at,
                    }
                    for r in (c.reviews or [])
                ],
            }
            enriched_contradictions.append(contra_dict)

        recent_gaps = list(
            self.db.execute(
                select(DocumentCoverageGap)
                .where(DocumentCoverageGap.workspace_id == workspace_id)
                .order_by(DocumentCoverageGap.created_at.desc())
                .limit(10)
            ).scalars().all()
        )

        return ResearchDashboardSummaryResponse(
            workspace_id=workspace_id,
            total_research_documents=total_docs,
            extraction_stats={
                "metadata_extracted": meta_count,
                "objectives_extracted": obj_count,
                "methodologies_extracted": meth_count,
            },
            total_comparisons=comp_count,
            total_findings=finding_count,
            validation_stats=validation_stats,
            contradiction_stats=contradiction_stats,
            coverage_stats={
                "total_runs": cov_runs_count,
                "total_gaps": sum(gap_stats.values()),
                "severity_breakdown": gap_stats,
            },
            recent_contradictions=[ResearchContradictionResponse.model_validate(c) for c in enriched_contradictions],
            recent_validations=[EvidenceValidationResponse.model_validate(v) for v in recent_validations],
            recent_gaps=[CoverageGapItem.model_validate(g) for g in recent_gaps],
        )
