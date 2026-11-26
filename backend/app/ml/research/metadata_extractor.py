"""Research Document Metadata Extractor (Phase 10 C10.1).

Extracts structured bibliographic and descriptive metadata from research documents
(PDF, DOCX, PPTX) combining first-page/title section analysis, embedded container
metadata inspection, regex validators, and LLM-assisted structured extraction.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from backend.app.core.logging import get_logger
from backend.app.llm.manager import LLMManager
from backend.app.llm.schemas import ChatMessage, LLMGenerationRequest, MessageRole
from backend.app.ml.research.prompts import build_metadata_extraction_prompt
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.schemas.research_intelligence import (
    AuthorInfo,
    FieldProvenance,
    MetadataConflict,
    ResearchDocumentType,
    ResearchEvidenceReference,
    ResearchMetadataProfileCreate,
)

logger = get_logger("knovera.research.metadata_extractor")

# Regex validators
DOI_REGEX = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b")
ARXIV_REGEX = re.compile(r"\b(arXiv:\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)
YEAR_REGEX = re.compile(r"\b(19\d{2}|20[0-2]\d)\b")
ORCID_REGEX = re.compile(r"\b(\d{4}-\d{4}-\d{4}-\d{3}[\dX])\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")


class ResearchMetadataExtractor:
    """Service for extracting bibliographic and descriptive research document metadata (C10.1)."""

    def __init__(self, llm_manager: Optional[LLMManager] = None, enable_llm: bool = True):
        self.llm_manager = llm_manager
        self.enable_llm = enable_llm

    def extract_from_document(
        self,
        document: Document,
        chunks: List[DocumentChunk],
        run_id: Optional[uuid.UUID] = None,
    ) -> ResearchMetadataProfileCreate:
        """Extracts complete metadata profile with provenance and conflict reconciliation."""
        if not chunks:
            # Fallback for empty document
            return self._build_empty_profile(document, run_id=run_id)

        # 1. Select relevant chunks (first few pages/chunks contain title, authors, abstract, headers)
        title_chunks = chunks[:5]
        context_text = self._assemble_context(title_chunks)
        embedded_meta = document.extraction_metadata or {}

        # 2. Run deterministic extraction pass
        det_data, det_evidence = self._run_deterministic_pass(
            context_text=context_text,
            chunks=title_chunks,
            document=document,
        )

        # 3. LLM-assisted extraction if enabled and LLMManager is available
        llm_data: Dict[str, Any] = {}
        llm_raw_response: Optional[str] = None
        manager = (self.llm_manager or LLMManager.get_instance()) if self.enable_llm else None

        if manager:
            prompt = build_metadata_extraction_prompt(
                context_text=context_text,
                embedded_metadata=embedded_meta,
                filename=document.original_filename,
            )
            try:
                active_provider = manager.get_active_provider()
                model_name = getattr(manager.settings, "LLM_MODEL", "mock-model") or "mock-model"
                llm_req = LLMGenerationRequest(
                    model=model_name,
                    messages=[
                        ChatMessage(
                            role=MessageRole.SYSTEM,
                            content="You are a strict, evidence-grounded research metadata extractor. Output only valid JSON.",
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
                logger.warning("LLM metadata extraction failed: %s. Using deterministic fallback.", exc)

        if llm_raw_response:
            try:
                clean_json = self._clean_json(llm_raw_response)
                llm_data = json.loads(clean_json)
            except Exception as exc:
                logger.warning("Failed to parse LLM JSON for metadata: %s", exc)

        # 4. Merge deterministic & LLM results, preserving source hierarchy
        merged_profile = self._merge_and_validate(
            document=document,
            chunks=title_chunks,
            det_data=det_data,
            det_evidence=det_evidence,
            llm_data=llm_data,
            embedded_meta=embedded_meta,
            run_id=run_id,
        )

        return merged_profile

    def _assemble_context(self, chunks: List[DocumentChunk], max_chars: int = 12000) -> str:
        """Assembles textual context from chunks with page/section headers."""
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
        context_text: str,
        chunks: List[DocumentChunk],
        document: Document,
    ) -> Tuple[Dict[str, Any], Dict[str, List[ResearchEvidenceReference]]]:
        """Runs high-precision deterministic regex & heuristic extractors."""
        data: Dict[str, Any] = {}
        evidence: Dict[str, List[ResearchEvidenceReference]] = {}

        # 1. DOI
        doi_match = DOI_REGEX.search(context_text)
        if doi_match:
            doi_val = doi_match.group(1).rstrip(".")
            data["doi"] = doi_val
            evidence["doi"] = [self._find_evidence_for_text(doi_val, chunks, document.id)]

        # 2. arXiv
        arxiv_match = ARXIV_REGEX.search(context_text)
        if arxiv_match:
            arxiv_val = arxiv_match.group(1)
            data["arxiv_id"] = arxiv_val
            evidence["arxiv_id"] = [self._find_evidence_for_text(arxiv_val, chunks, document.id)]

        # 3. Publication Year
        year_match = YEAR_REGEX.search(context_text)
        if year_match:
            year_int = int(year_match.group(1))
            if 1950 <= year_int <= 2030:
                data["publication_year"] = year_int
                evidence["publication_year"] = [self._find_evidence_for_text(str(year_int), chunks, document.id)]

        # 4. Fallback Title from first line or document filename
        first_chunk = chunks[0] if chunks else None
        if first_chunk and first_chunk.content:
            lines = [line.strip() for line in first_chunk.content.split("\n") if len(line.strip()) > 5]
            if lines:
                candidate_title = lines[0]
                # If first line looks like a header, try second line
                if candidate_title.lower().startswith(("arxiv", "ieee", "acm", "journal", "proceedings")) and len(lines) > 1:
                    candidate_title = lines[1]
                data["title"] = candidate_title
                evidence["title"] = [
                    ResearchEvidenceReference(
                        document_id=str(document.id),
                        chunk_id=str(first_chunk.id),
                        page_number=first_chunk.page_start,
                        section_title=first_chunk.section_title,
                        evidence_text=candidate_title,
                    )
                ]

        # 5. Document Type Heuristics
        lower_content = context_text.lower()
        if "proceedings of" in lower_content or "conference on" in lower_content:
            data["document_type"] = "conference_paper"
        elif "arxiv" in lower_content:
            data["document_type"] = "preprint"
        elif "thesis" in lower_content or "dissertation" in lower_content:
            data["document_type"] = "thesis"
        elif "technical report" in lower_content:
            data["document_type"] = "technical_report"
        elif document.file_extension.lower() == ".pptx":
            data["document_type"] = "research_presentation"
        else:
            data["document_type"] = "journal_article"

        return data, evidence

    def _merge_and_validate(
        self,
        document: Document,
        chunks: List[DocumentChunk],
        det_data: Dict[str, Any],
        det_evidence: Dict[str, List[ResearchEvidenceReference]],
        llm_data: Dict[str, Any],
        embedded_meta: Dict[str, Any],
        run_id: Optional[uuid.UUID],
    ) -> ResearchMetadataProfileCreate:
        """Merges LLM outputs with deterministic data, verifies source evidence and conflicts."""
        first_chunk = chunks[0] if chunks else None

        # Title resolution
        title = llm_data.get("title") or det_data.get("title") or document.original_filename.rsplit(".", 1)[0]
        title = title.strip()

        # Document Type
        raw_doc_type = llm_data.get("document_type") or det_data.get("document_type") or "unknown"
        valid_doc_types = {
            "journal_article", "conference_paper", "preprint", "thesis", "dissertation",
            "technical_report", "research_proposal", "working_paper", "systematic_review",
            "survey_paper", "research_presentation", "unknown"
        }
        document_type: ResearchDocumentType = raw_doc_type if raw_doc_type in valid_doc_types else "unknown"

        # Abstract
        abstract = llm_data.get("abstract")

        # Authors
        raw_authors = llm_data.get("authors", [])
        authors: List[AuthorInfo] = []
        if isinstance(raw_authors, list):
            for idx, a in enumerate(raw_authors):
                if isinstance(a, dict) and a.get("name"):
                    authors.append(
                        AuthorInfo(
                            name=str(a["name"]).strip(),
                            order=int(a.get("order", idx + 1)),
                            affiliation=a.get("affiliation"),
                            department=a.get("department"),
                            institution=a.get("institution"),
                            country=a.get("country"),
                            is_corresponding=bool(a.get("is_corresponding", False)),
                            orcid=a.get("orcid"),
                        )
                    )

        # DOI & arXiv
        doi = det_data.get("doi") or llm_data.get("doi")
        if doi and not DOI_REGEX.match(doi):
            doi = None  # Invalidate invalid DOI format

        arxiv_id = det_data.get("arxiv_id") or llm_data.get("arxiv_id")

        # Year validation
        year = llm_data.get("publication_year") or det_data.get("publication_year")
        if year is not None:
            try:
                year = int(year)
                if not (1800 <= year <= 2030):
                    year = None
            except (ValueError, TypeError):
                year = None

        # Conflicts between content & embedded metadata
        conflicts: List[MetadataConflict] = []
        embedded_title = embedded_meta.get("title")
        if embedded_title and isinstance(embedded_title, str) and embedded_title.strip():
            emb_clean = embedded_title.strip()
            # If embedded title is radically different from extracted content title
            if emb_clean.lower() != title.lower() and not (emb_clean in title or title in emb_clean):
                conflicts.append(
                    MetadataConflict(
                        field="title",
                        content_value=title,
                        embedded_value=emb_clean,
                        conflict_reason="Embedded document metadata title differs from title on first page content.",
                        chosen_source="document_content",
                        resolution_status="resolved_content",
                    )
                )

        # Metadata fields provenance dictionary
        meta_fields: Dict[str, FieldProvenance] = {}

        # Default chunk reference
        default_ref = [
            ResearchEvidenceReference(
                document_id=str(document.id),
                chunk_id=str(first_chunk.id) if first_chunk else None,
                page_number=first_chunk.page_start if first_chunk else None,
                section_title=first_chunk.section_title if first_chunk else None,
                evidence_text=title[:200],
            )
        ] if first_chunk else []

        # Add Title Provenance
        meta_fields["title"] = FieldProvenance(
            field="title",
            value=title,
            extraction_status="extracted",
            source_type="document_content",
            extraction_method="llm_assisted" if llm_data.get("title") else "deterministic",
            validation_status="validated",
            confidence=0.95,
            evidence=det_evidence.get("title") or default_ref,
        )

        # Add Publication Year Provenance
        if year is not None:
            meta_fields["publication_year"] = FieldProvenance(
                field="publication_year",
                value=year,
                extraction_status="extracted",
                source_type="document_content",
                extraction_method="deterministic" if det_data.get("publication_year") else "llm_assisted",
                validation_status="validated",
                confidence=0.90,
                evidence=det_evidence.get("publication_year") or default_ref,
            )
        else:
            meta_fields["publication_year"] = FieldProvenance(
                field="publication_year",
                value=None,
                extraction_status="missing",
                source_type="inferred",
                extraction_method="deterministic",
                validation_status="validated",
                confidence=1.0,
                evidence=[],
            )

        # Add DOI Provenance
        if doi:
            meta_fields["doi"] = FieldProvenance(
                field="doi",
                value=doi,
                extraction_status="extracted",
                source_type="document_content",
                extraction_method="deterministic",
                validation_status="validated",
                confidence=0.98,
                evidence=det_evidence.get("doi") or default_ref,
            )

        return ResearchMetadataProfileCreate(
            workspace_id=document.workspace_id,
            document_id=document.id,
            run_id=run_id,
            document_version=document.pipeline_version or "v1.0",
            document_type=document_type,
            title=title,
            subtitle=llm_data.get("subtitle"),
            alternative_title=llm_data.get("alternative_title"),
            language=llm_data.get("language") or "en",
            abstract=abstract,
            keywords=llm_data.get("keywords") or [],
            authors=authors,
            publication_year=year,
            publication_date=llm_data.get("publication_date"),
            journal_name=llm_data.get("journal_name"),
            conference_name=llm_data.get("conference_name"),
            publisher=llm_data.get("publisher"),
            volume=llm_data.get("volume"),
            issue=llm_data.get("issue"),
            page_range=llm_data.get("page_range"),
            doi=doi,
            arxiv_id=arxiv_id,
            isbn_issn=llm_data.get("isbn_issn"),
            publication_status=llm_data.get("publication_status"),
            funding_organization=llm_data.get("funding_organization"),
            acknowledgements=llm_data.get("acknowledgements"),
            grant_identifiers=llm_data.get("grant_identifiers") or [],
            research_domain=llm_data.get("research_domain"),
            subdomain=llm_data.get("subdomain"),
            metadata_fields=meta_fields,
            conflicts=conflicts,
            validation_status="needs_review" if conflicts else "validated",
        )

    def _find_evidence_for_text(
        self,
        query: str,
        chunks: List[DocumentChunk],
        document_id: uuid.UUID,
    ) -> ResearchEvidenceReference:
        """Finds matching chunk and snippet for given query text."""
        for chunk in chunks:
            if query.lower() in chunk.content.lower():
                # Extract snippet around match
                idx = chunk.content.lower().find(query.lower())
                start = max(0, idx - 40)
                end = min(len(chunk.content), idx + len(query) + 40)
                snippet = chunk.content[start:end].replace("\n", " ").strip()
                return ResearchEvidenceReference(
                    document_id=str(document_id),
                    chunk_id=str(chunk.id),
                    page_number=chunk.page_start,
                    section_title=chunk.section_title,
                    evidence_text=snippet,
                )
        first = chunks[0] if chunks else None
        return ResearchEvidenceReference(
            document_id=str(document_id),
            chunk_id=str(first.id) if first else None,
            page_number=first.page_start if first else None,
            section_title=first.section_title if first else None,
            evidence_text=query,
        )

    def _build_empty_profile(
        self,
        document: Document,
        run_id: Optional[uuid.UUID],
    ) -> ResearchMetadataProfileCreate:
        """Builds an unpopulated metadata profile when document text is empty."""
        title = document.original_filename.rsplit(".", 1)[0]
        return ResearchMetadataProfileCreate(
            workspace_id=document.workspace_id,
            document_id=document.id,
            run_id=run_id,
            document_version=document.pipeline_version or "v1.0",
            document_type="unknown",
            title=title,
            language="en",
            metadata_fields={
                "title": FieldProvenance(
                    field="title",
                    value=title,
                    extraction_status="derived",
                    source_type="embedded_metadata",
                    extraction_method="deterministic",
                    validation_status="needs_review",
                    confidence=0.5,
                    evidence=[],
                )
            },
            conflicts=[],
            validation_status="needs_review",
        )

    def _clean_json(self, raw_text: str) -> str:
        """Strips markdown code fences and cleans JSON output."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()
