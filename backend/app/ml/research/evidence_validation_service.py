"""Service for C10.7: Source-Grounded Evidence Validation.

Validates extracted claims, findings, and hypotheses against canonical document chunks,
performing exact-span localization, normalized overlap verification, numerical consistency checks,
qualifier/negation preservation, and semantic NLI confirmation.
"""

from difflib import SequenceMatcher
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.ml.research.nli_service import get_nli_service
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.research_intelligence import (
    ResearchEvidenceValidationRecord,
    ResearchFinding,
)
from backend.app.schemas.research_intelligence import (
    EvidenceValidationRequest,
    EvidenceValidationResponse,
)

logger = logging.getLogger(__name__)

# Regular expressions for numeric values, percentages, p-values, confidence intervals
NUMERIC_PATTERN = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?%?")
P_VALUE_PATTERN = re.compile(r"[pP]\s*([<>=])\s*(0?\.\d+)")
NEGATION_WORDS = {"not", "never", "neither", "nor", "none", "no", "fails", "failed", "unlikely", "cannot", "without"}
HEDGING_WORDS = {"suggests", "may", "might", "could", "preliminary", "hypothesize", "indicates"}


def _extract_numbers(text: str) -> List[str]:
    """Extract normalized numbers, percentages, and metrics from text."""
    return [n.strip("%").rstrip(".") for n in NUMERIC_PATTERN.findall(text) if n.strip("%").rstrip(".")]


def _check_negation(text: str) -> bool:
    """Check if text contains strong negation tokens."""
    tokens = set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))
    return bool(tokens.intersection(NEGATION_WORDS))


class EvidenceValidationService:
    """Rigorous multi-tier evidence validator grounded in document chunks."""

    def __init__(self, db: Session):
        self.db = db
        self.nli_service = get_nli_service(db=db)

    def find_chunk_candidate(
        self,
        document_id: uuid.UUID,
        chunk_id: Optional[uuid.UUID] = None,
        target_page_number: Optional[int] = None,
        target_section: Optional[str] = None,
        claim_text: str = "",
    ) -> Optional[DocumentChunk]:
        """Resolve the most relevant document chunk for the claim."""
        if chunk_id:
            chunk = self.db.execute(
                select(DocumentChunk).where(
                    DocumentChunk.id == chunk_id,
                    DocumentChunk.document_id == document_id,
                )
            ).scalar_one_or_none()
            if chunk:
                return chunk

        # Query chunks for the document
        stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        if target_page_number is not None:
            stmt = stmt.where(DocumentChunk.page_start == target_page_number)
        
        chunks = list(self.db.execute(stmt).scalars().all())
        if not chunks and target_page_number is not None:
            # Fall back to all chunks of the document
            chunks = list(self.db.execute(select(DocumentChunk).where(DocumentChunk.document_id == document_id)).scalars().all())

        if not chunks:
            return None

        # Rank chunks by simple lexical overlap with claim
        claim_words = set(re.findall(r"\w+", claim_text.lower()))
        best_chunk = None
        best_score = -1

        for c in chunks:
            c_text = getattr(c, "content", getattr(c, "chunk_text", ""))
            c_words = set(re.findall(r"\w+", c_text.lower()))
            overlap = len(claim_words.intersection(c_words))
            if overlap > best_score:
                best_score = overlap
                best_chunk = c

        return best_chunk

    def evaluate_exact_or_normalized_span(
        self,
        claim_text: str,
        chunk_text: str,
    ) -> Tuple[bool, float, Optional[int], Optional[int], Optional[str]]:
        """Evaluate Tier 1 exact match and Tier 2 normalized token overlap.

        Returns (exact_match, overlap_ratio, char_start, char_end, excerpt).
        """
        # Exact match check
        idx = chunk_text.lower().find(claim_text.lower())
        if idx != -1:
            char_start = idx
            char_end = idx + len(claim_text)
            excerpt = chunk_text[char_start:char_end]
            return True, 1.0, char_start, char_end, excerpt

        # Sub-sequence matcher to locate closest span
        matcher = SequenceMatcher(None, claim_text.lower(), chunk_text.lower())
        match = matcher.find_longest_match(0, len(claim_text), 0, len(chunk_text))
        
        # Word set overlap
        claim_words = set(re.findall(r"\b\w{3,}\b", claim_text.lower()))
        chunk_words = set(re.findall(r"\b\w{3,}\b", chunk_text.lower()))
        jaccard = len(claim_words.intersection(chunk_words)) / max(len(claim_words.union(chunk_words)), 1)
        
        # Sequence matcher ratio
        seq_ratio = matcher.ratio()
        overlap_score = max(jaccard, seq_ratio)

        if match.size > 20:
            char_start = match.b
            char_end = match.b + match.size
            excerpt = chunk_text[char_start:char_end]
        else:
            char_start = None
            char_end = None
            excerpt = chunk_text[:200] if len(chunk_text) > 200 else chunk_text

        return False, overlap_score, char_start, char_end, excerpt

    def validate_numbers_and_qualifiers(
        self,
        claim_text: str,
        supporting_text: str,
    ) -> Tuple[bool, bool, Optional[str]]:
        """Verify that numbers and qualifiers (negations) in the claim are compatible.

        Returns (numeric_match, qualifier_match, rejection_reason).
        """
        claim_nums = _extract_numbers(claim_text)
        support_nums = _extract_numbers(supporting_text)

        numeric_match = True
        rejection_reason = None

        if claim_nums:
            # Check if all numbers mentioned in claim exist in supporting passage
            missing_nums = [n for n in claim_nums if n not in support_nums]
            if missing_nums:
                numeric_match = False
                rejection_reason = f"Numerical value mismatch: numbers {missing_nums} not found in supporting text"

        # Check negation compatibility
        claim_neg = _check_negation(claim_text)
        support_neg = _check_negation(supporting_text)

        qualifier_match = True
        if claim_neg != support_neg:
            qualifier_match = False
            if not rejection_reason:
                rejection_reason = "Qualifier/negation conflict between claim and supporting passage"

        return numeric_match, qualifier_match, rejection_reason

    def validate_claim(
        self,
        workspace_id: uuid.UUID,
        request: EvidenceValidationRequest,
    ) -> ResearchEvidenceValidationRecord:
        """Run full multi-tier evidence validation pipeline for a claim."""
        chunk = self.find_chunk_candidate(
            document_id=request.document_id,
            chunk_id=request.chunk_id,
            target_page_number=request.target_page_number,
            target_section=request.target_section,
            claim_text=request.claim_text,
        )

        if not chunk:
            record = ResearchEvidenceValidationRecord(
                workspace_id=workspace_id,
                document_id=request.document_id,
                claim_type=request.claim_type,
                claim_id=request.claim_id,
                claim_text=request.claim_text,
                target_chunk_id=request.chunk_id,
                target_page_number=request.target_page_number,
                target_section=request.target_section,
                validation_status="unsupported",
                validation_tier="tier_4_heuristic",
                confidence_score=0.1,
                exact_match=False,
                normalized_overlap=0.0,
                numeric_match=False,
                qualifier_match=False,
                rejection_reason="No corresponding document chunk located for evidence grounding",
                validation_metadata={"error": "chunk_not_found"},
            )
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            return record

        chunk_text = getattr(chunk, "content", getattr(chunk, "chunk_text", ""))
        exact_match, overlap, char_start, char_end, excerpt = self.evaluate_exact_or_normalized_span(
            request.claim_text, chunk_text
        )

        num_match, qual_match, num_qual_reason = self.validate_numbers_and_qualifiers(
            request.claim_text, chunk_text
        )

        # Tier decision logic
        tier = "tier_1_exact_span" if exact_match else ("tier_2_normalized_overlap" if overlap >= 0.60 else "tier_3_semantic_nli")
        
        # NLI semantic inference
        nli_res = self.nli_service.infer(
            premise=chunk_text[:1000],
            hypothesis=request.claim_text[:500],
            bidirectional=False,
        )
        
        # Determine status
        status = "supported"
        rejection_reason = num_qual_reason
        confidence = 0.85

        if exact_match and qual_match and num_match:
            status = "evidence_matched"
            tier = "tier_1_exact_span"
            confidence = 0.98
        elif nli_res.forward_label == "contradiction" or not qual_match:
            status = "conflicting_evidence"
            confidence = max(nli_res.forward_scores.get("contradiction", 0.8), 0.75)
            if not rejection_reason:
                rejection_reason = "Semantic contradiction detected between document chunk and extracted claim"
        elif exact_match and not num_match:
            status = "partially_supported"
            confidence = 0.65
        elif overlap >= 0.50 and qual_match and num_match:
            status = "supported"
            tier = "tier_2_normalized_overlap"
            confidence = 0.80 + (overlap * 0.15)
        elif nli_res.forward_label == "entailment" and qual_match and num_match:
            status = "supported"
            tier = "tier_3_semantic_nli"
            confidence = nli_res.forward_scores.get("entailment", 0.75)
        elif overlap >= 0.25:
            status = "partially_supported"
            tier = "tier_4_heuristic"
            confidence = 0.50
        else:
            status = "unsupported"
            tier = "tier_4_heuristic"
            confidence = 0.20
            if not rejection_reason:
                rejection_reason = "Insufficient lexical and semantic grounding in referenced chunk"

        record = ResearchEvidenceValidationRecord(
            workspace_id=workspace_id,
            document_id=request.document_id,
            claim_type=request.claim_type,
            claim_id=request.claim_id,
            claim_text=request.claim_text,
            target_chunk_id=chunk.id,
            target_page_number=getattr(chunk, "page_start", getattr(chunk, "page_number", None)),
            target_section=request.target_section or getattr(chunk, "section_title", None),
            validation_status=status,
            validation_tier=tier,
            confidence_score=round(confidence, 3),
            exact_match=exact_match,
            normalized_overlap=round(overlap, 3),
            numeric_match=num_match,
            qualifier_match=qual_match,
            char_start=char_start,
            char_end=char_end,
            supporting_text_excerpt=excerpt,
            rejection_reason=rejection_reason,
            validation_metadata={
                "nli_forward_label": nli_res.forward_label,
                "nli_forward_scores": nli_res.forward_scores,
                "chunk_id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
            },
            is_stale=False,
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def validate_finding(
        self,
        workspace_id: uuid.UUID,
        finding_id: uuid.UUID,
    ) -> ResearchEvidenceValidationRecord:
        """Validate a stored ResearchFinding against its evidence references."""
        finding = self.db.execute(
            select(ResearchFinding).where(
                ResearchFinding.id == finding_id,
                ResearchFinding.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

        if not finding:
            raise ValueError(f"Finding {finding_id} not found in workspace {workspace_id}")

        evidence_refs = getattr(finding, "evidence", None) or getattr(finding, "evidence_references", None) or []
        target_chunk_id = None
        target_page = None
        target_section = None
        
        if evidence_refs and isinstance(evidence_refs, list):
            first_ref = evidence_refs[0]
            if isinstance(first_ref, dict):
                c_id = first_ref.get("chunk_id")
                if c_id:
                    try:
                        target_chunk_id = uuid.UUID(c_id)
                    except ValueError:
                        pass
                target_page = first_ref.get("page_number")
                target_section = first_ref.get("section_title")

        req = EvidenceValidationRequest(
            document_id=finding.document_id,
            claim_type="finding",
            claim_id=finding.id,
            claim_text=finding.original_statement,
            chunk_id=target_chunk_id,
            target_page_number=target_page,
            target_section=target_section,
        )
        record = self.validate_claim(workspace_id=workspace_id, request=req)

        # Update finding's own validation_status
        finding.validation_status = record.validation_status
        self.db.commit()

        return record

    def list_validations(
        self,
        workspace_id: uuid.UUID,
        document_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[ResearchEvidenceValidationRecord]:
        """Query validation records for a workspace."""
        stmt = select(ResearchEvidenceValidationRecord).where(
            ResearchEvidenceValidationRecord.workspace_id == workspace_id
        )
        if document_id:
            stmt = stmt.where(ResearchEvidenceValidationRecord.document_id == document_id)
        if status:
            stmt = stmt.where(ResearchEvidenceValidationRecord.validation_status == status)
        stmt = stmt.order_by(ResearchEvidenceValidationRecord.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
