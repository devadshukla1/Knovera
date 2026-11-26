"""Validation Utilities and Relationship Validation Service for Knovera Knowledge Graph (Phase 7).

Provides Unicode code-point offset verification, surface-form span checking,
prompt-injection resilience, schema constraint enforcement, and the C7.4
RelationshipValidationService for rigorous relationship verification.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.llm.manager import LLMManager
from backend.app.ml.knowledge_graph.ontology import ALL_CATEGORIES
from backend.app.ml.knowledge_graph.relationships import (
    ALL_PREDICATES,
    ALLOWED_REFLEXIVE_PREDICATES,
    is_allowed_self_loop,
    is_valid_predicate,
    validate_predicate_domain_range,
)
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedConcept,
    ExtractedMention,
    ExtractedRelationship,
    NormalizedNode,
    RelationshipValidationReport,
    RelationshipValidationResult,
    RelationshipValidationStatus,
)

logger = logging.getLogger(__name__)

# Common prompt injection triggers to detect or neutralize
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*override", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:an?\s+)?unrestricted", re.IGNORECASE),
    re.compile(r"disregard\s+(?:the\s+)?above", re.IGNORECASE),
    re.compile(r"<\s*script\s*>", re.IGNORECASE),
    re.compile(r"```(?:json)?\s*\{.*\"override\":", re.IGNORECASE | re.DOTALL),
]


def verify_span(
    text: str,
    start_offset: int,
    end_offset: int,
    expected_surface_form: str,
    case_sensitive: bool = True,
) -> bool:
    """Verifies that start_offset:end_offset in text exactly matches expected_surface_form.

    Uses strict Python string indexing which operates directly on Unicode code points.
    """
    if text is None:
        return False
    if start_offset < 0 or end_offset > len(text) or start_offset >= end_offset:
        return False

    extracted_slice = text[start_offset:end_offset]
    if case_sensitive:
        return extracted_slice == expected_surface_form
    return extracted_slice.strip().lower() == expected_surface_form.strip().lower()


def locate_all_spans(
    text: str,
    surface_form: str,
    whole_word: bool = True,
) -> List[Tuple[int, int]]:
    """Locates all occurrences of surface_form in text, returning list of (start_offset, end_offset).

    If whole_word is True, respects boundary characters to prevent false partial matches.
    """
    if not text or not surface_form:
        return []

    escaped = re.escape(surface_form)
    if whole_word:
        pattern = rf"(?<!\w){escaped}(?!\w)"
    else:
        pattern = escaped

    matches = []
    try:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            matches.append((match.start(), match.end()))
    except re.error:
        idx = 0
        while True:
            pos = text.lower().find(surface_form.lower(), idx)
            if pos == -1:
                break
            matches.append((pos, pos + len(surface_form)))
            idx = pos + len(surface_form)

    return matches


def detect_prompt_injection(text: str) -> bool:
    """Detects whether text contains deliberate adversarial prompt injection markers."""
    if not text:
        return False
    for pat in PROMPT_INJECTION_PATTERNS:
        if pat.search(text):
            return True
    return False


def sanitize_text_for_extraction(text: str) -> str:
    """Sanitizes document text for safe LLM processing without losing semantic content."""
    if not text:
        return ""
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return sanitized


def validate_mention_offsets(mention: ExtractedMention, chunk_text: str) -> bool:
    """Validates that a mention's offsets resolve to its surface form in chunk_text."""
    return verify_span(
        text=chunk_text,
        start_offset=mention.start_offset,
        end_offset=mention.end_offset,
        expected_surface_form=mention.surface_form,
        case_sensitive=False,
    )


def validate_extracted_concept(
    concept: ExtractedConcept,
    chunk_text: Optional[str] = None,
) -> bool:
    """Validates an extracted concept candidate against ontology and offset constraints."""
    if not concept.name or not concept.name.strip():
        return False
    if concept.category not in ALL_CATEGORIES:
        return False
    if chunk_text is not None:
        for m in concept.mentions:
            if not validate_mention_offsets(m, chunk_text):
                return False
    return True


def validate_extracted_relationship(
    rel: ExtractedRelationship,
    valid_node_names: Optional[Set[str]] = None,
    chunk_text_by_id: Optional[Dict[str, str]] = None,
) -> bool:
    """Validates an extracted relationship against predicate taxonomy and evidence spans."""
    if not rel.source_node_name or not rel.target_node_name:
        return False
    if rel.source_node_name.strip().lower() == rel.target_node_name.strip().lower():
        if not is_allowed_self_loop(rel.predicate):
            return False
    if rel.predicate not in ALL_PREDICATES:
        return False

    if valid_node_names is not None:
        src = rel.source_node_name.strip().lower()
        tgt = rel.target_node_name.strip().lower()
        valid_lower = {n.strip().lower() for n in valid_node_names}
        if src not in valid_lower or tgt not in valid_lower:
            return False

    if chunk_text_by_id and rel.evidence:
        for ev in rel.evidence:
            chunk_txt = chunk_text_by_id.get(ev.chunk_id)
            if chunk_txt:
                if not verify_span(
                    text=chunk_txt,
                    start_offset=ev.start_offset,
                    end_offset=ev.end_offset,
                    expected_surface_form=ev.evidence_text,
                    case_sensitive=False,
                ):
                    return False
    return True


class RelationshipValidationService:
    """C7.4 Dedicated service for validating relationship endpoints, ontology, evidence, and polarity."""

    def __init__(self, llm_manager: Optional[LLMManager] = None) -> None:
        self.llm_manager = llm_manager

    def validate_relationships(
        self,
        workspace_id: str,
        relationships: List[ExtractedRelationship],
        nodes: List[NormalizedNode],
        chunks: List[Dict[str, Any]],  # [{id, content, content_hash?, workspace_id?}]
        extraction_run_id: Optional[str] = None,
        use_llm_review: bool = False,
    ) -> RelationshipValidationReport:
        """Executes the full C7.4 validation pipeline across candidate relationships."""
        start_time = time.perf_counter()

        report = RelationshipValidationReport(
            workspace_id=workspace_id,
            extraction_run_id=extraction_run_id,
            candidate_count=len(relationships),
            validation_policy_version="1.0.0",
        )

        if not relationships:
            report.validation_duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return report

        # Index canonical nodes by ID and lowercase name
        node_by_id: Dict[str, NormalizedNode] = {}
        node_by_name: Dict[str, NormalizedNode] = {}
        for n in nodes:
            if n.id:
                node_by_id[str(n.id)] = n
            node_by_name[n.name.strip().lower()] = n
            node_by_name[n.normalized_name.strip().lower()] = n
            for alias in n.aliases:
                node_by_name[alias.strip().lower()] = n

        # Index chunks
        chunk_by_id: Dict[str, Dict[str, Any]] = {str(c.get("id")): c for c in chunks}

        # Step 1: Detect contradictions within the batch
        contradiction_pairs = self._detect_batch_contradictions(relationships)
        report.contradiction_warnings = len(contradiction_pairs)

        # Step 2: Validate each candidate relationship
        now = datetime.now(timezone.utc)

        for rel in relationships:
            res = self._validate_single_relationship(
                rel=rel,
                workspace_id=workspace_id,
                node_by_id=node_by_id,
                node_by_name=node_by_name,
                chunk_by_id=chunk_by_id,
                now=now,
            )

            # Check if flagged by batch contradiction
            rel_key = self._get_rel_key(rel)
            if rel_key in contradiction_pairs:
                res.warnings.append(f"Contradictory claim detected in extraction batch: {contradiction_pairs[rel_key]}")
                if res.status == RelationshipValidationStatus.VALIDATED.value:
                    res.status = RelationshipValidationStatus.NEEDS_REVIEW.value
                    res.reasons.append("Flagged for review due to conflicting claims in corpus.")

            # Optional Semantic LLM Review
            if use_llm_review and res.status in {RelationshipValidationStatus.VALIDATED.value, RelationshipValidationStatus.NEEDS_REVIEW.value}:
                self._apply_semantic_review(rel, res, chunk_by_id)

            # Update report statistics
            if res.status == RelationshipValidationStatus.VALIDATED.value:
                report.validated_count += 1
                rel.validation_status = RelationshipValidationStatus.VALIDATED.value
            elif res.status == RelationshipValidationStatus.NEEDS_REVIEW.value:
                report.needs_review_count += 1
                rel.validation_status = RelationshipValidationStatus.NEEDS_REVIEW.value
            else:
                report.rejected_count += 1
                rel.validation_status = RelationshipValidationStatus.REJECTED.value

            if not res.endpoint_valid:
                report.invalid_endpoint_count += 1
            if not res.predicate_valid:
                report.invalid_predicate_count += 1
            if not res.evidence_valid:
                report.invalid_evidence_count += 1

            for reason in res.reasons:
                if "stale" in reason.lower():
                    report.stale_evidence_count += 1
                if "workspace" in reason.lower():
                    report.workspace_integrity_failures += 1

            if rel.is_negated:
                report.negation_findings += 1
            if rel.modality in {"hypothetical", "uncertain"}:
                report.modality_findings += 1

            report.results.append(res)

        report.validation_duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return report

    def _validate_single_relationship(
        self,
        rel: ExtractedRelationship,
        workspace_id: str,
        node_by_id: Dict[str, NormalizedNode],
        node_by_name: Dict[str, NormalizedNode],
        chunk_by_id: Dict[str, Dict[str, Any]],
        now: datetime,
    ) -> RelationshipValidationResult:
        """Validates all constraints on a single relationship candidate."""
        res = RelationshipValidationResult(
            relationship_id=rel.id,
            source_node_id=rel.source_node_id,
            target_node_id=rel.target_node_id,
            source_node_name=rel.source_node_name,
            target_node_name=rel.target_node_name,
            predicate=rel.predicate,
            status=RelationshipValidationStatus.VALIDATED.value,
            validation_method="deterministic",
            ontology_version="1.0.0",
            validated_at=now,
        )

        # 1. Endpoint Resolution & Validation
        src_node = None
        if rel.source_node_id and str(rel.source_node_id) in node_by_id:
            src_node = node_by_id[str(rel.source_node_id)]
        elif rel.source_node_name:
            src_node = node_by_name.get(rel.source_node_name.strip().lower())

        tgt_node = None
        if rel.target_node_id and str(rel.target_node_id) in node_by_id:
            tgt_node = node_by_id[str(rel.target_node_id)]
        elif rel.target_node_name:
            tgt_node = node_by_name.get(rel.target_node_name.strip().lower())

        if not src_node:
            res.endpoint_valid = False
            res.reasons.append(f"Subject '{rel.source_node_name}' does not resolve to a canonical knowledge node.")
        if not tgt_node:
            res.endpoint_valid = False
            res.reasons.append(f"Object '{rel.target_node_name}' does not resolve to a canonical knowledge node.")

        if src_node and tgt_node:
            res.endpoint_valid = True
            res.source_node_id = str(src_node.id) if src_node.id else None
            res.target_node_id = str(tgt_node.id) if tgt_node.id else None
            rel.source_node_id = res.source_node_id
            rel.target_node_id = res.target_node_id

            # Workspace consistency
            if src_node.workspace_id and str(src_node.workspace_id) != workspace_id:
                res.endpoint_valid = False
                res.reasons.append(f"Subject node belongs to workspace {src_node.workspace_id}, not current workspace {workspace_id}.")
            if tgt_node.workspace_id and str(tgt_node.workspace_id) != workspace_id:
                res.endpoint_valid = False
                res.reasons.append(f"Object node belongs to workspace {tgt_node.workspace_id}, not current workspace {workspace_id}.")

            # Self-loop check
            if src_node.name.strip().lower() == tgt_node.name.strip().lower():
                if not is_allowed_self_loop(rel.predicate):
                    res.endpoint_valid = False
                    res.reasons.append(f"Invalid self-loop for non-reflexive predicate '{rel.predicate}'.")
                else:
                    res.warnings.append(f"Self-loop detected on reflexive predicate '{rel.predicate}'.")
        else:
            res.endpoint_valid = False

        # 2. Predicate & Ontology Constraints
        if not is_valid_predicate(rel.predicate):
            res.predicate_valid = False
            res.reasons.append(f"Predicate '{rel.predicate}' is not recognized in relationship ontology.")
        else:
            res.predicate_valid = True
            # Domain and Range validation
            src_cat = src_node.category if src_node else None
            tgt_cat = tgt_node.category if tgt_node else None
            is_valid_types, type_err = validate_predicate_domain_range(rel.predicate, src_cat, tgt_cat)
            if not is_valid_types:
                res.predicate_valid = False
                res.reasons.append(f"Ontology domain/range violation: {type_err}")

        # 3. Evidence Verification
        if not rel.evidence:
            res.evidence_valid = False
            res.reasons.append("Relationship has zero source evidence records.")
        else:
            valid_evidence_count = 0
            for ev in rel.evidence:
                ev_chunk = chunk_by_id.get(str(ev.chunk_id))
                if not ev_chunk:
                    res.reasons.append(f"Referenced source chunk '{ev.chunk_id}' not found in current corpus.")
                    continue

                # Workspace check on chunk
                chunk_ws = ev_chunk.get("workspace_id")
                if chunk_ws and str(chunk_ws) != workspace_id:
                    res.reasons.append(f"Source chunk '{ev.chunk_id}' belongs to another workspace ({chunk_ws}).")
                    continue

                chunk_content = ev_chunk.get("content", "")

                # Stale content hash verification
                chunk_hash = ev_chunk.get("content_hash") or ev_chunk.get("clean_text_hash")
                if chunk_hash:
                    actual_hash = hashlib.sha256(chunk_content.encode("utf-8")).hexdigest()
                    if actual_hash != chunk_hash:
                        res.reasons.append(f"Source chunk '{ev.chunk_id}' content hash mismatch (evidence is stale).")
                        continue

                # Character offset checks
                if ev.start_offset < 0 or ev.end_offset > len(chunk_content) or ev.start_offset >= ev.end_offset:
                    res.reasons.append(f"Invalid evidence offsets [{ev.start_offset}:{ev.end_offset}] for chunk length {len(chunk_content)}.")
                    continue

                # Exact text match
                extracted_slice = chunk_content[ev.start_offset:ev.end_offset]
                if extracted_slice != ev.evidence_text:
                    if extracted_slice.strip().lower() == ev.evidence_text.strip().lower():
                        res.warnings.append("Evidence text matched chunk text with minor whitespace/case differences.")
                        valid_evidence_count += 1
                    else:
                        res.reasons.append(
                            f"Evidence text '{ev.evidence_text[:30]}' does not match text slice '{extracted_slice[:30]}' at [{ev.start_offset}:{ev.end_offset}]."
                        )
                else:
                    valid_evidence_count += 1

            if valid_evidence_count > 0:
                res.evidence_valid = True
            else:
                res.evidence_valid = False
                res.reasons.append("None of the provided evidence records are verifiable.")

        # 4. Final Status Assignment
        if not res.endpoint_valid or not res.predicate_valid or not res.evidence_valid:
            res.status = RelationshipValidationStatus.REJECTED.value
        elif res.warnings or rel.modality in {"hypothetical", "uncertain"}:
            # Flag for review if there are warnings or hypothetical/uncertain modality
            res.status = RelationshipValidationStatus.NEEDS_REVIEW.value
        else:
            res.status = RelationshipValidationStatus.VALIDATED.value

        return res

    def _detect_batch_contradictions(
        self,
        relationships: List[ExtractedRelationship],
    ) -> Dict[Tuple[str, str, str], str]:
        """Detects conflicting claims within the batch (e.g. A rel B with opposite polarity)."""
        seen_claims: Dict[Tuple[str, str, str], ExtractedRelationship] = {}
        contradictions: Dict[Tuple[str, str, str], str] = {}

        for rel in relationships:
            src = rel.source_node_name.strip().lower()
            tgt = rel.target_node_name.strip().lower()
            pred = rel.predicate.strip().lower()

            key = (src, pred, tgt)
            if key in seen_claims:
                prior = seen_claims[key]
                if prior.is_negated != rel.is_negated:
                    conflict_desc = f"Affirmation and negation clash: one claim asserts '{pred}', another asserts not '{pred}'"
                    contradictions[key] = conflict_desc
            else:
                seen_claims[key] = rel

        return contradictions

    def _get_rel_key(self, rel: ExtractedRelationship) -> Tuple[str, str, str]:
        return (
            rel.source_node_name.strip().lower(),
            rel.predicate.strip().lower(),
            rel.target_node_name.strip().lower(),
        )

    def _apply_semantic_review(
        self,
        rel: ExtractedRelationship,
        res: RelationshipValidationResult,
        chunk_by_id: Dict[str, Dict[str, Any]],
    ) -> None:
        """Applies optional LLM-assisted semantic check for nuanced claims."""
        manager = self.llm_manager or LLMManager.get_instance()
        if not manager:
            return

        evidence_sample = ""
        for ev in rel.evidence:
            chunk = chunk_by_id.get(str(ev.chunk_id))
            if chunk and chunk.get("content"):
                evidence_sample = ev.evidence_text
                break

        if not evidence_sample or detect_prompt_injection(evidence_sample):
            return

        prompt = (
            "You are a knowledge graph verification agent.\n"
            f"Subject: '{rel.source_node_name}'\n"
            f"Predicate: '{rel.predicate}'\n"
            f"Object: '{rel.target_node_name}'\n"
            f"Is Negated: {rel.is_negated}\n"
            f"Evidence: \"{evidence_sample[:400]}\"\n\n"
            "Evaluate if the evidence strictly supports this relationship. "
            "Output ONLY JSON: {\"supported\": true/false, \"reason\": \"explanation\"}"
        )

        try:
            raw = ""
            if hasattr(manager, "complete"):
                raw = manager.complete(prompt=prompt, temperature=0.0, max_tokens=150)
            elif hasattr(manager, "generate_sync"):
                raw = manager.generate_sync(prompt)

            if raw and "{" in raw:
                clean_json = raw[raw.find("{"):raw.rfind("}") + 1]
                data = json.loads(clean_json)
                if not data.get("supported", True):
                    res.status = RelationshipValidationStatus.NEEDS_REVIEW.value
                    res.warnings.append(f"Semantic LLM review flagged claim: {data.get('reason', 'unsupported')}")
        except Exception as e:
            logger.debug("Optional semantic review exception ignored: %s", e)
