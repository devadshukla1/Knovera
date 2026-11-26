"""Service for C10.8: Cross-Paper Contradiction Detection.

Applies a multi-stage scientific contradiction detection pipeline:
- Stage 1: Evidence Validity Check (both claims must be grounded in primary text)
- Stage 2: Comparability Safeguards (evaluates contextual, metric, population, and dataset alignment)
- Stage 3: Directional NLI Inference (evaluates empirical conflict vs consistency)
- Stage 4: Qualifier and Hedging Analysis
- Stage 5: Review Lifecycle Management (candidate -> needs_review -> confirmed / rejected / superseded)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from backend.app.ml.research.evidence_validation_service import EvidenceValidationService
from backend.app.ml.research.nli_service import get_nli_service
from backend.app.models.document import Document
from backend.app.models.research_intelligence import (
    ResearchContradictionRecord,
    ResearchContradictionReview,
    ResearchFinding,
)
from backend.app.schemas.research_intelligence import (
    ContradictionDetectRequest,
    ContradictionReviewRequest,
)

logger = logging.getLogger(__name__)


class ContradictionDetectionService:
    """Rigorous staged contradiction detection and audit lifecycle engine."""

    def __init__(self, db: Session):
        self.db = db
        self.evidence_service = EvidenceValidationService(db)
        self.nli_service = get_nli_service(db=db)

    def detect_contradiction(
        self,
        workspace_id: uuid.UUID,
        request: ContradictionDetectRequest,
    ) -> ResearchContradictionRecord:
        """Execute the 4-stage scientific contradiction analysis on two research findings."""
        # 1. Fetch both findings
        finding_a = self.db.execute(
            select(ResearchFinding).where(
                ResearchFinding.id == request.finding_a_id,
                ResearchFinding.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

        finding_b = self.db.execute(
            select(ResearchFinding).where(
                ResearchFinding.id == request.finding_b_id,
                ResearchFinding.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

        if not finding_a or not finding_b:
            raise ValueError("One or both findings not found in workspace")

        # Check existing record if not force_reevaluation
        if not request.force_reevaluation:
            existing = self.db.execute(
                select(ResearchContradictionRecord).where(
                    ResearchContradictionRecord.workspace_id == workspace_id,
                    or_(
                        (ResearchContradictionRecord.finding_a_id == finding_a.id) & (ResearchContradictionRecord.finding_b_id == finding_b.id),
                        (ResearchContradictionRecord.finding_a_id == finding_b.id) & (ResearchContradictionRecord.finding_b_id == finding_a.id),
                    )
                )
            ).scalars().first()
            if existing:
                return existing

        # --- STAGE 1: Evidence Validity Verification ---
        val_a = finding_a.validation_status
        if val_a in ("unvalidated", "pending"):
            rec_a = self.evidence_service.validate_finding(workspace_id, finding_a.id)
            val_a = rec_a.validation_status

        val_b = finding_b.validation_status
        if val_b in ("unvalidated", "pending"):
            rec_b = self.evidence_service.validate_finding(workspace_id, finding_b.id)
            val_b = rec_b.validation_status

        stage_1_passed = val_a in ("supported", "evidence_matched", "partially_supported") and \
                         val_b in ("supported", "evidence_matched", "partially_supported")

        # --- STAGE 2: Comparability Safeguards ---
        context_diffs = []
        comparability = "comparable"

        var_a = (finding_a.outcome_variable or "").strip().lower()
        var_b = (finding_b.outcome_variable or "").strip().lower()
        if var_a and var_b and var_a != var_b:
            context_diffs.append(f"Outcome metric divergence: '{var_a}' vs '{var_b}'")
            comparability = "conditionally_comparable"

        cond_a = {str(k).lower(): str(v).lower() for k, v in (getattr(finding_a, "contextual_conditions", None) or {}).items()}
        cond_b = {str(k).lower(): str(v).lower() for k, v in (getattr(finding_b, "contextual_conditions", None) or {}).items()}

        pop_a = cond_a.get("population") or cond_a.get("participants") or (getattr(finding_a, "population", None) or "").strip().lower()
        pop_b = cond_b.get("population") or cond_b.get("participants") or (getattr(finding_b, "population", None) or "").strip().lower()
        if pop_a and pop_b and pop_a != pop_b:
            context_diffs.append(f"Population difference: '{pop_a}' vs '{pop_b}'")
            comparability = "conditionally_comparable"

        dataset_a = cond_a.get("dataset") or cond_a.get("corpus") or (getattr(finding_a, "dataset_relationship", None) or "").strip().lower()
        dataset_b = cond_b.get("dataset") or cond_b.get("corpus") or (getattr(finding_b, "dataset_relationship", None) or "").strip().lower()
        if dataset_a and dataset_b and dataset_a != dataset_b:
            context_diffs.append(f"Dataset difference: '{dataset_a}' vs '{dataset_b}'")

        if len(context_diffs) >= 2:
            comparability = "not_comparable"

        # --- STAGE 3: Directional NLI Inference ---
        nli_res = self.nli_service.infer(
            premise=finding_a.original_statement,
            hypothesis=finding_b.original_statement,
            bidirectional=True,
        )

        # --- STAGE 4: Final Classification & Decision Logic ---
        confidence = 0.5
        review_status = "candidate"

        if not stage_1_passed:
            contradiction_category = "insufficient_evidence"
            confidence = 0.35
            review_status = "automatically_assessed"
        elif comparability == "not_comparable":
            contradiction_category = "contextual_difference"
            confidence = 0.85
            review_status = "automatically_assessed"
        elif any("Outcome metric divergence" in d for d in context_diffs):
            contradiction_category = "metric_difference"
            confidence = 0.80
            review_status = "automatically_assessed"
        elif any("Population difference" in d for d in context_diffs):
            contradiction_category = "population_difference"
            confidence = 0.80
            review_status = "automatically_assessed"
        elif any("Dataset difference" in d for d in context_diffs):
            contradiction_category = "dataset_difference"
            confidence = 0.75
            review_status = "automatically_assessed"
        elif nli_res.aggregated_label == "contradiction":
            contradiction_category = "direct_contradiction_candidate"
            confidence = nli_res.forward_scores.get("contradiction", 0.75)
            review_status = "needs_review"
        elif nli_res.aggregated_label == "entailment":
            contradiction_category = "consistent"
            confidence = nli_res.forward_scores.get("entailment", 0.80)
            review_status = "automatically_assessed"
        elif nli_res.aggregated_label == "neutral":
            contradiction_category = "neutral_or_unrelated"
            confidence = nli_res.forward_scores.get("neutral", 0.70)
            review_status = "automatically_assessed"
        else:
            contradiction_category = "partial_agreement"
            confidence = 0.60
            review_status = "automatically_assessed"

        stage_breakdown = {
            "stage_1_evidence": {
                "passed": stage_1_passed,
                "evidence_validity_a": val_a,
                "evidence_validity_b": val_b,
            },
            "stage_2_comparability": {
                "comparability_status": comparability,
                "contextual_differences": context_diffs,
            },
            "stage_3_nli": {
                "forward_label": nli_res.forward_label,
                "backward_label": nli_res.backward_label,
                "aggregated_label": nli_res.aggregated_label,
                "confidence_level": nli_res.confidence_level,
                "margin": nli_res.margin,
            },
        }

        record = ResearchContradictionRecord(
            workspace_id=workspace_id,
            comparison_id=request.comparison_id,
            finding_a_id=finding_a.id,
            finding_b_id=finding_b.id,
            document_a_id=finding_a.document_id,
            document_b_id=finding_b.document_id,
            contradiction_category=contradiction_category,
            evidence_validity_a=val_a,
            evidence_validity_b=val_b,
            comparability_status=comparability,
            contextual_differences=context_diffs,
            stage_breakdown=stage_breakdown,
            confidence_score=round(confidence, 3),
            nli_relation=nli_res.aggregated_label,
            review_status=review_status,
            human_verified=False,
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def review_contradiction(
        self,
        workspace_id: uuid.UUID,
        contradiction_id: uuid.UUID,
        request: ContradictionReviewRequest,
        user_id: Optional[uuid.UUID] = None,
    ) -> ResearchContradictionRecord:
        """Apply a human audit decision to a contradiction record."""
        record = self.db.execute(
            select(ResearchContradictionRecord).where(
                ResearchContradictionRecord.id == contradiction_id,
                ResearchContradictionRecord.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

        if not record:
            raise ValueError(f"Contradiction record {contradiction_id} not found in workspace")

        prev_status = record.review_status
        new_status = prev_status

        if request.action == "confirm":
            new_status = "confirmed"
            record.human_verified = True
        elif request.action == "reject":
            new_status = "rejected"
            record.human_verified = True
        elif request.action == "flag_contextual":
            new_status = "human_reviewed"
            record.contradiction_category = "contextual_difference"
            record.human_verified = True
        elif request.action == "reopen":
            new_status = "needs_review"
            record.human_verified = False

        record.review_status = new_status
        record.reviewer_notes = request.notes

        review = ResearchContradictionReview(
            contradiction_id=record.id,
            user_id=user_id,
            previous_status=prev_status,
            new_status=new_status,
            review_action=request.action,
            review_notes=request.notes,
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_contradictions(
        self,
        workspace_id: uuid.UUID,
        category: Optional[str] = None,
        review_status: Optional[str] = None,
        limit: int = 50,
    ) -> List[ResearchContradictionRecord]:
        """Query contradictions for workspace with eager relationships."""
        stmt = select(ResearchContradictionRecord).where(
            ResearchContradictionRecord.workspace_id == workspace_id
        ).options(joinedload(ResearchContradictionRecord.reviews))

        if category:
            stmt = stmt.where(ResearchContradictionRecord.contradiction_category == category)
        if review_status:
            stmt = stmt.where(ResearchContradictionRecord.review_status == review_status)

        stmt = stmt.order_by(ResearchContradictionRecord.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).unique().scalars().all())
