"""Research Objective Extractor (Phase 10 C10.2).

Extracts primary and secondary objectives, problem statements, motivations,
research questions, hypotheses, scope, and claimed contributions from academic documents.
Distinguishes original verbatim quotations from normalized academic summaries.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from backend.app.core.logging import get_logger
from backend.app.llm.manager import LLMManager
from backend.app.llm.schemas import ChatMessage, LLMGenerationRequest, MessageRole
from backend.app.ml.research.prompts import build_objective_extraction_prompt
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.schemas.research_intelligence import (
    ClaimedContributionItem,
    ResearchEvidenceReference,
    ResearchHypothesisItem,
    ResearchObjectiveItem,
    ResearchObjectiveProfileCreate,
    ResearchQuestionItem,
)

logger = get_logger("knovera.research.objective_extractor")

# Regex heuristics for deterministic extraction fallback
OBJECTIVE_PATTERNS = [
    re.compile(r"(?:the\s+)?(?:primary\s+)?objective\s+of\s+this\s+(?:paper|study|work|research)\s+is\s+to\s+(?P<text>[^.\n]{15,250})", re.IGNORECASE),
    re.compile(r"this\s+(?:paper|study|work)\s+aims\s+to\s+(?P<text>[^.\n]{15,250})", re.IGNORECASE),
    re.compile(r"the\s+main\s+goal\s+of\s+this\s+(?:paper|study|work)\s+is\s+to\s+(?P<text>[^.\n]{15,250})", re.IGNORECASE),
    re.compile(r"we\s+(?:investigate|evaluate|propose|demonstrate)\s+(?P<text>[^.\n]{15,250})", re.IGNORECASE),
]

QUESTION_PATTERNS = [
    re.compile(r"(?:RQ\s*\d*|Research\s+Question\s*\d*)\s*[:.-]\s*(?P<text>[^?\n]+\?)", re.IGNORECASE),
    re.compile(r"\b(Can\s+[^?\n]{10,200}\?)", re.IGNORECASE),
    re.compile(r"\b(How\s+does\s+[^?\n]{10,200}\?)", re.IGNORECASE),
    re.compile(r"\b(To\s+what\s+extent\s+[^?\n]{10,200}\?)", re.IGNORECASE),
]

HYPOTHESIS_PATTERNS = [
    re.compile(r"(?:H\s*\d*|Hypothesis\s*\d*)\s*[:.-]\s*(?P<text>[^.\n]{15,250})", re.IGNORECASE),
    re.compile(r"we\s+hypothesize\s+that\s+(?P<text>[^.\n]{15,250})", re.IGNORECASE),
]

CONTRIBUTION_PATTERNS = [
    re.compile(r"(?:our\s+main\s+contributions?|contributions?\s+of\s+this\s+paper)\s+(?:are|include):?\s*(?P<text>[^.\n]{15,300})", re.IGNORECASE),
    re.compile(r"in\s+summary,\s+this\s+paper\s+makes\s+the\s+following\s+contributions?:?\s*(?P<text>[^.\n]{15,300})", re.IGNORECASE),
]


class ResearchObjectiveExtractor:
    """Service for identifying, extracting, and normalizing research objectives and claims (C10.2)."""

    def __init__(self, llm_manager: Optional[LLMManager] = None, enable_llm: bool = True):
        self.llm_manager = llm_manager
        self.enable_llm = enable_llm

    def extract_from_document(
        self,
        document: Document,
        chunks: List[DocumentChunk],
        known_concepts: Optional[List[KnowledgeNode]] = None,
        paper_title: Optional[str] = None,
        run_id: Optional[uuid.UUID] = None,
    ) -> ResearchObjectiveProfileCreate:
        """Extracts complete research objective profile with evidence and taxonomy classification."""
        if not chunks:
            return self._build_empty_profile(document, run_id=run_id)

        # 1. Filter section-aware chunks (abstract, introduction, motivation, problem, contributions)
        relevant_chunks = self._select_objective_chunks(chunks)
        context_text = self._assemble_context(relevant_chunks)

        # 2. Deterministic heuristic extraction pass
        det_data = self._run_deterministic_pass(relevant_chunks, document.id)

        # 3. LLM-assisted extraction
        llm_data: Dict[str, Any] = {}
        llm_raw_response: Optional[str] = None
        manager = (self.llm_manager or LLMManager.get_instance()) if self.enable_llm else None

        if manager:
            prompt = build_objective_extraction_prompt(
                context_text=context_text,
                paper_title=paper_title or document.original_filename,
            )
            try:
                active_provider = manager.get_active_provider()
                model_name = getattr(manager.settings, "LLM_MODEL", "mock-model") or "mock-model"
                llm_req = LLMGenerationRequest(
                    model=model_name,
                    messages=[
                        ChatMessage(
                            role=MessageRole.SYSTEM,
                            content="You are an expert academic research methodologist. Output only valid JSON.",
                        ),
                        ChatMessage(role=MessageRole.USER, content=prompt),
                    ],
                    temperature=0.1,
                    max_output_tokens=2500,
                    response_format="json_object",
                )
                import asyncio
                import concurrent.futures
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, manager.generate_with_retry(llm_req, provider=active_provider))
                        resp = future.result()
                else:
                    resp = asyncio.run(manager.generate_with_retry(llm_req, provider=active_provider))
                llm_raw_response = resp.content
            except Exception as exc:
                logger.warning("LLM objective extraction failed: %s. Using deterministic fallback.", exc)

        if llm_raw_response:
            try:
                clean_json = self._clean_json(llm_raw_response)
                llm_data = json.loads(clean_json)
            except Exception as exc:
                logger.warning("Failed to parse LLM JSON for objectives: %s", exc)

        # 4. Merge, normalize, deduplicate, and attach concept IDs
        profile = self._merge_and_validate(
            document=document,
            chunks=relevant_chunks,
            det_data=det_data,
            llm_data=llm_data,
            known_concepts=known_concepts or [],
            run_id=run_id,
        )

        return profile

    def _select_objective_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Prioritizes chunks from Introduction, Abstract, Motivation, Scope, and Contributions."""
        priority_keywords = ["abstract", "intro", "motivation", "problem", "objective", "contribution", "goal"]
        selected: List[DocumentChunk] = []

        # Find chunks with section titles matching priority keywords
        for chunk in chunks:
            if chunk.section_title:
                sec_lower = chunk.section_title.lower()
                if any(kw in sec_lower for kw in priority_keywords):
                    selected.append(chunk)

        # If not enough section matches found, fall back to the first 6 chunks
        if len(selected) < 3:
            first_chunks = chunks[:6]
            for c in first_chunks:
                if c not in selected:
                    selected.append(c)

        return selected

    def _assemble_context(self, chunks: List[DocumentChunk], max_chars: int = 12000) -> str:
        """Assembles textual context from selected chunks with section headers."""
        parts = []
        total_len = 0
        for chunk in chunks:
            page_info = f"[Page {chunk.page_start}]" if chunk.page_start else ""
            section_info = f" - Section: {chunk.section_title}" if chunk.section_title else ""
            header = f"--- CHUNK {chunk.chunk_index} {page_info}{section_info} ---"
            block = f"{header}\n{chunk.content}\n"
            if total_len + len(block) > max_chars:
                parts.append(block[: max_chars - total_len])
                break
            parts.append(block)
            total_len += len(block)
        return "\n".join(parts)

    def _run_deterministic_pass(
        self,
        chunks: List[DocumentChunk],
        document_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Extracts candidate objectives, questions, hypotheses using regex rules."""
        objectives: List[Dict[str, Any]] = []
        questions: List[Dict[str, Any]] = []
        hypotheses: List[Dict[str, Any]] = []
        contributions: List[Dict[str, Any]] = []

        seen_texts: Set[str] = set()

        for chunk in chunks:
            content = chunk.content

            # Objectives
            for pat in OBJECTIVE_PATTERNS:
                for match in pat.finditer(content):
                    text = match.group("text").strip().rstrip(".,;")
                    text_key = text.lower()[:60]
                    if text_key not in seen_texts and len(text) > 15:
                        seen_texts.add(text_key)
                        objectives.append({
                            "original_text": text,
                            "normalized_text": f"Evaluate {text.lower()}" if not text.lower().startswith(("to", "evaluate", "investigate", "propose")) else text,
                            "is_primary": len(objectives) == 0,
                            "chunk_id": str(chunk.id),
                            "page_number": chunk.page_start,
                            "evidence_text": match.group(0),
                        })

            # Research Questions
            for pat in QUESTION_PATTERNS:
                for match in pat.finditer(content):
                    text = match.group(1 if pat.groups == 1 else "text").strip()
                    text_key = text.lower()[:60]
                    if text_key not in seen_texts and len(text) > 10:
                        seen_texts.add(text_key)
                        questions.append({
                            "question_text": text,
                            "normalized_text": text,
                            "chunk_id": str(chunk.id),
                            "page_number": chunk.page_start,
                            "evidence_text": match.group(0),
                        })

            # Hypotheses
            for pat in HYPOTHESIS_PATTERNS:
                for match in pat.finditer(content):
                    text = match.group("text").strip().rstrip(".,;")
                    text_key = text.lower()[:60]
                    if text_key not in seen_texts and len(text) > 15:
                        seen_texts.add(text_key)
                        hypotheses.append({
                            "hypothesis_text": text,
                            "hypothesis_type": "alternative",
                            "chunk_id": str(chunk.id),
                            "page_number": chunk.page_start,
                            "evidence_text": match.group(0),
                        })

            # Contributions
            for pat in CONTRIBUTION_PATTERNS:
                for match in pat.finditer(content):
                    text = match.group("text").strip().rstrip(".,;")
                    text_key = text.lower()[:60]
                    if text_key not in seen_texts and len(text) > 15:
                        seen_texts.add(text_key)
                        contributions.append({
                            "contribution_text": text,
                            "contribution_type": "claimed",
                            "chunk_id": str(chunk.id),
                            "page_number": chunk.page_start,
                            "evidence_text": match.group(0),
                        })

        return {
            "objectives": objectives,
            "questions": questions,
            "hypotheses": hypotheses,
            "contributions": contributions,
        }

    def _merge_and_validate(
        self,
        document: Document,
        chunks: List[DocumentChunk],
        det_data: Dict[str, Any],
        llm_data: Dict[str, Any],
        known_concepts: List[KnowledgeNode],
        run_id: Optional[uuid.UUID],
    ) -> ResearchObjectiveProfileCreate:
        """Merges LLM and deterministic items, normalizes text, and links concept IDs."""
        first_chunk = chunks[0] if chunks else None
        default_evidence = [
            ResearchEvidenceReference(
                document_id=str(document.id),
                chunk_id=str(first_chunk.id) if first_chunk else None,
                page_number=first_chunk.page_start if first_chunk else None,
                section_title=first_chunk.section_title if first_chunk else None,
                evidence_text=chunks[0].content[:200] if chunks else "Document Introduction",
            )
        ]

        # 1. Primary Objective & Narrative Elements
        primary_obj = llm_data.get("primary_objective")
        if not primary_obj and det_data.get("objectives"):
            primary_obj = det_data["objectives"][0]["original_text"]

        problem_stmt = llm_data.get("problem_statement")
        motivation = llm_data.get("motivation")
        research_scope = llm_data.get("research_scope") or {}

        # 2. Objectives List
        raw_objs = llm_data.get("objectives", [])
        objectives: List[ResearchObjectiveItem] = []
        seen_obj_keys: Set[str] = set()

        if isinstance(raw_objs, list) and raw_objs:
            for item in raw_objs:
                if isinstance(item, dict) and item.get("original_text"):
                    orig = str(item["original_text"]).strip()
                    key = orig.lower()[:50]
                    if key not in seen_obj_keys:
                        seen_obj_keys.add(key)
                        ev_text = item.get("evidence_text") or orig
                        ref = self._resolve_evidence(ev_text, chunks, document.id) or default_evidence
                        concept_ids = self._match_concepts(orig, known_concepts)
                        is_prim = bool(item.get("is_primary", len(objectives) == 0))
                        objectives.append(
                            ResearchObjectiveItem(
                                objective_type="primary_objective" if is_prim else "secondary_objective",
                                original_text=orig,
                                normalized_text=item.get("normalized_text") or orig,
                                is_primary=is_prim,
                                scope_details=item.get("scope_details", {}),
                                evidence=ref,
                                extraction_status="extracted",
                                validation_status="validated",
                                associated_concept_ids=concept_ids,
                            )
                        )
        else:
            # Deterministic fallback
            for item in det_data.get("objectives", []):
                orig = item["original_text"]
                key = orig.lower()[:50]
                if key not in seen_obj_keys:
                    seen_obj_keys.add(key)
                    ref = [
                        ResearchEvidenceReference(
                            document_id=str(document.id),
                            chunk_id=item.get("chunk_id"),
                            page_number=item.get("page_number"),
                            evidence_text=item["evidence_text"],
                        )
                    ]
                    objectives.append(
                        ResearchObjectiveItem(
                            objective_type="primary_objective" if item["is_primary"] else "secondary_objective",
                            original_text=orig,
                            normalized_text=item["normalized_text"],
                            is_primary=item["is_primary"],
                            evidence=ref,
                            extraction_status="extracted",
                            validation_status="validated",
                            associated_concept_ids=self._match_concepts(orig, known_concepts),
                        )
                    )

        # 3. Research Questions List
        raw_rqs = llm_data.get("research_questions", [])
        research_questions: List[ResearchQuestionItem] = []
        seen_rq_keys: Set[str] = set()

        if isinstance(raw_rqs, list) and raw_rqs:
            for item in raw_rqs:
                if isinstance(item, dict) and item.get("question_text"):
                    q_text = str(item["question_text"]).strip()
                    key = q_text.lower()[:50]
                    if key not in seen_rq_keys:
                        seen_rq_keys.add(key)
                        ev_text = item.get("evidence_text") or q_text
                        ref = self._resolve_evidence(ev_text, chunks, document.id) or default_evidence
                        research_questions.append(
                            ResearchQuestionItem(
                                question_text=q_text,
                                normalized_text=item.get("normalized_text") or q_text,
                                evidence=ref,
                                extraction_status="extracted",
                                validation_status="validated",
                            )
                        )
        else:
            for item in det_data.get("questions", []):
                q_text = item["question_text"]
                key = q_text.lower()[:50]
                if key not in seen_rq_keys:
                    seen_rq_keys.add(key)
                    research_questions.append(
                        ResearchQuestionItem(
                            question_text=q_text,
                            normalized_text=item["normalized_text"],
                            evidence=[
                                ResearchEvidenceReference(
                                    document_id=str(document.id),
                                    chunk_id=item.get("chunk_id"),
                                    page_number=item.get("page_number"),
                                    evidence_text=item["evidence_text"],
                                )
                            ],
                            extraction_status="extracted",
                            validation_status="validated",
                        )
                    )

        # 4. Hypotheses List
        raw_hyps = llm_data.get("hypotheses", [])
        hypotheses: List[ResearchHypothesisItem] = []
        seen_hyp_keys: Set[str] = set()

        if isinstance(raw_hyps, list) and raw_hyps:
            for item in raw_hyps:
                if isinstance(item, dict) and item.get("hypothesis_text"):
                    h_text = str(item["hypothesis_text"]).strip()
                    key = h_text.lower()[:50]
                    if key not in seen_hyp_keys:
                        seen_hyp_keys.add(key)
                        ev_text = item.get("evidence_text") or h_text
                        ref = self._resolve_evidence(ev_text, chunks, document.id) or default_evidence
                        valid_types = {"null", "alternative", "directional", "non_directional", "other"}
                        htype = item.get("hypothesis_type", "alternative")
                        hypotheses.append(
                            ResearchHypothesisItem(
                                hypothesis_text=h_text,
                                hypothesis_type=htype if htype in valid_types else "alternative",
                                evidence=ref,
                                extraction_status="extracted",
                                validation_status="validated",
                            )
                        )
        else:
            for item in det_data.get("hypotheses", []):
                h_text = item["hypothesis_text"]
                key = h_text.lower()[:50]
                if key not in seen_hyp_keys:
                    seen_hyp_keys.add(key)
                    hypotheses.append(
                        ResearchHypothesisItem(
                            hypothesis_text=h_text,
                            hypothesis_type=item["hypothesis_type"],
                            evidence=[
                                ResearchEvidenceReference(
                                    document_id=str(document.id),
                                    chunk_id=item.get("chunk_id"),
                                    page_number=item.get("page_number"),
                                    evidence_text=item["evidence_text"],
                                )
                            ],
                            extraction_status="extracted",
                            validation_status="validated",
                        )
                    )

        # 5. Claimed Contributions List
        raw_cnts = llm_data.get("claimed_contributions", [])
        claimed_contributions: List[ClaimedContributionItem] = []
        seen_cnt_keys: Set[str] = set()

        if isinstance(raw_cnts, list) and raw_cnts:
            for item in raw_cnts:
                if isinstance(item, dict) and item.get("contribution_text"):
                    c_text = str(item["contribution_text"]).strip()
                    key = c_text.lower()[:50]
                    if key not in seen_cnt_keys:
                        seen_cnt_keys.add(key)
                        ev_text = item.get("evidence_text") or c_text
                        ref = self._resolve_evidence(ev_text, chunks, document.id) or default_evidence
                        valid_types = {"proposed", "implemented", "claimed", "demonstrated"}
                        ctype = item.get("contribution_type", "claimed")
                        claimed_contributions.append(
                            ClaimedContributionItem(
                                contribution_text=c_text,
                                contribution_type=ctype if ctype in valid_types else "claimed",
                                evidence=ref,
                                extraction_status="extracted",
                            )
                        )
        else:
            for item in det_data.get("contributions", []):
                c_text = item["contribution_text"]
                key = c_text.lower()[:50]
                if key not in seen_cnt_keys:
                    seen_cnt_keys.add(key)
                    claimed_contributions.append(
                        ClaimedContributionItem(
                            contribution_text=c_text,
                            contribution_type=item["contribution_type"],
                            evidence=[
                                ResearchEvidenceReference(
                                    document_id=str(document.id),
                                    chunk_id=item.get("chunk_id"),
                                    page_number=item.get("page_number"),
                                    evidence_text=item["evidence_text"],
                                )
                            ],
                            extraction_status="extracted",
                        )
                    )

        return ResearchObjectiveProfileCreate(
            workspace_id=document.workspace_id,
            document_id=document.id,
            run_id=run_id,
            document_version=document.pipeline_version or "v1.0",
            primary_objective=primary_obj,
            problem_statement=problem_stmt,
            motivation=motivation,
            research_scope=research_scope,
            objectives=objectives,
            research_questions=research_questions,
            hypotheses=hypotheses,
            claimed_contributions=claimed_contributions,
            validation_status="validated" if (objectives or primary_obj) else "needs_review",
        )

    def _match_concepts(self, text: str, known_concepts: List[Any]) -> List[str]:
        """Matches concept labels within extracted objective text and returns concept IDs."""
        matched: List[str] = []
        lower_text = text.lower()
        for node in known_concepts:
            node_name = getattr(node, "name", None) or getattr(node, "canonical_name", None)
            if node_name and node_name.lower() in lower_text:
                matched.append(str(node.id))
                continue
            aliases = getattr(node, "aliases", []) or []
            if any(alias.lower() in lower_text for alias in aliases if alias):
                matched.append(str(node.id))
        return matched

    def _resolve_evidence(
        self,
        query: str,
        chunks: List[DocumentChunk],
        document_id: uuid.UUID,
    ) -> List[ResearchEvidenceReference]:
        """Resolves matching chunk location for a given evidence quote."""
        clean_q = query.strip().replace("\n", " ")
        if len(clean_q) > 80:
            clean_q = clean_q[:80]
        for chunk in chunks:
            if clean_q.lower() in chunk.content.lower():
                return [
                    ResearchEvidenceReference(
                        document_id=str(document_id),
                        chunk_id=str(chunk.id),
                        page_number=chunk.page_start,
                        section_title=chunk.section_title,
                        evidence_text=query[:300],
                    )
                ]
        return []

    def _build_empty_profile(
        self,
        document: Document,
        run_id: Optional[uuid.UUID],
    ) -> ResearchObjectiveProfileCreate:
        """Returns empty profile when document text is empty."""
        return ResearchObjectiveProfileCreate(
            workspace_id=document.workspace_id,
            document_id=document.id,
            run_id=run_id,
            document_version=document.pipeline_version or "v1.0",
            primary_objective=None,
            problem_statement=None,
            motivation=None,
            research_scope={},
            objectives=[],
            research_questions=[],
            hypotheses=[],
            claimed_contributions=[],
            validation_status="needs_review",
        )

    def _clean_json(self, raw_text: str) -> str:
        """Strips markdown code fences and cleans JSON output."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()
