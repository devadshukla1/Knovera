"""Citation Mapper mapping verified source metadata to location-aware CitationDrafts (Phase 3 C3.8)."""

from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.citations.schemas import CitationDraft
from backend.app.core.logging import get_logger
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.rag.prompts.schemas import FactClaim

logger = get_logger("knovera.citations.mapper")


class CitationMapper:
    """Constructs verifiable, location-aware citation drafts from database records."""

    def create_citation_drafts(
        self,
        claims: List[FactClaim],
        source_mapping: Dict[str, Dict[str, Any]],
        db: Session,
        workspace_id: uuid.UUID,
    ) -> List[CitationDraft]:
        """Maps model claims and prompt-local source IDs to structured CitationDrafts.

        Args:
            claims: Model-extracted fact claims containing source_ids (['S1']).
            source_mapping: Authoritative ContextPackage source_mapping.
            db: Database session.
            workspace_id: Current workspace UUID.

        Returns:
            Ordered list of CitationDraft items.
        """
        drafts: List[CitationDraft] = []
        seen_pairs: set[tuple[str, Optional[int]]] = set()
        display_order = 1

        for claim_idx, claim in enumerate(claims):
            for sid in claim.source_ids:
                clean_sid = sid.strip().upper()
                if clean_sid not in source_mapping:
                    continue

                pair_key = (clean_sid, claim_idx)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                meta = source_mapping[clean_sid]
                chunk_id = uuid.UUID(str(meta["chunk_id"]))

                draft = self._build_single_draft(
                    clean_sid=clean_sid,
                    chunk_id=chunk_id,
                    claim_idx=claim_idx,
                    display_order=display_order,
                    db=db,
                    workspace_id=workspace_id,
                    meta=meta,
                )
                if draft:
                    drafts.append(draft)
                    display_order += 1

        # If claims didn't link any citations but sources were in mapping,
        # create general draft citations for referenced sources
        if not drafts and source_mapping:
            for clean_sid, meta in source_mapping.items():
                chunk_id = uuid.UUID(str(meta["chunk_id"]))
                draft = self._build_single_draft(
                    clean_sid=clean_sid,
                    chunk_id=chunk_id,
                    claim_idx=None,
                    display_order=display_order,
                    db=db,
                    workspace_id=workspace_id,
                    meta=meta,
                )
                if draft:
                    drafts.append(draft)
                    display_order += 1

        return drafts

    def _build_single_draft(
        self,
        clean_sid: str,
        chunk_id: uuid.UUID,
        claim_idx: Optional[int],
        display_order: int,
        db: Session,
        workspace_id: uuid.UUID,
        meta: Dict[str, Any],
    ) -> Optional[CitationDraft]:
        """Queries authoritative chunk and document to build CitationDraft."""
        chunk = (
            db.query(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(
                DocumentChunk.id == chunk_id,
                DocumentChunk.workspace_id == workspace_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .first()
        )
        if not chunk:
            return None

        doc: Document = chunk.document
        doc_ext = (doc.file_extension or "").lower()

        # Extract section_path from meta or source_segments if present
        section_path = meta.get("section_path") or []
        if not section_path and chunk.source_segments:
            for seg in chunk.source_segments:
                if isinstance(seg, dict) and "section_path" in seg and seg["section_path"]:
                    section_path = seg["section_path"]
                    break

        # Format location accurately per document type
        location_type, location_label = self._format_location(
            doc_ext=doc_ext,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            slide_number=chunk.slide_number,
            section_title=chunk.section_title,
            section_path=section_path,
            source_segments=chunk.source_segments or [],
        )

        # Generate clean excerpt from authoritative chunk content
        excerpt = self._extract_clean_excerpt(chunk.content)

        return CitationDraft(
            source_id=clean_sid,
            chunk_id=chunk.id,
            document_id=doc.id,
            workspace_id=workspace_id,
            claim_index=claim_idx,
            display_order=display_order,
            document_name=doc.original_filename,
            document_type=doc.media_type or doc_ext,
            location_type=location_type,
            location_label=location_label,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            slide_number=chunk.slide_number,
            slide_title=meta.get("slide_title"),
            section_title=chunk.section_title,
            section_path=section_path,
            paragraph_index=meta.get("paragraph_index"),
            source_segments=chunk.source_segments or [],
            quote_text=None,  # verified later if model supplied an exact quote
            excerpt=excerpt,
            relevance_score=meta.get("retrieval_distance"),
        )

    def _format_location(
        self,
        doc_ext: str,
        page_start: Optional[int],
        page_end: Optional[int],
        slide_number: Optional[int],
        section_title: Optional[str],
        section_path: List[str],
        source_segments: List[Dict[str, Any]],
    ) -> tuple[str, str]:
        """Generates location_type and strictly accurate 1-based location_label."""
        if doc_ext == ".pdf":
            loc_type = "pdf_pages"
            if page_start and page_end:
                if page_start == page_end:
                    loc_label = f"Page {page_start}"
                else:
                    loc_label = f"Pages {page_start}–{page_end}"
            elif page_start:
                loc_label = f"Page {page_start}"
            else:
                loc_label = "Page 1"
            return loc_type, loc_label

        elif doc_ext in (".pptx", ".ppt"):
            loc_type = "pptx_slide"
            if slide_number:
                loc_label = f"Slide {slide_number}"
            else:
                loc_label = "Slide 1"
            return loc_type, loc_label

        elif doc_ext in (".docx", ".doc"):
            loc_type = "docx_section"
            if section_title:
                loc_label = f"Section: {section_title}"
            elif section_path:
                loc_label = f"Section: {section_path[-1]}"
            else:
                loc_label = "Document Section"
            return loc_type, loc_label

        # Default multi-segment / text
        if len(source_segments) > 1:
            return "multi_segment", f"{len(source_segments)} segments"
        return "document", "Document"

    def _extract_clean_excerpt(self, content: str, max_chars: int = 250) -> str:
        """Extracts a readable excerpt cleanly bounded at word boundary."""
        if not content:
            return ""
        clean = " ".join(content.split())
        if len(clean) <= max_chars:
            return clean

        truncated = clean[:max_chars]
        last_space = truncated.rfind(" ")
        if last_space > 100:
            truncated = truncated[:last_space]
        return truncated + "..."
