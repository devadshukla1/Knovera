"""Citation repository for PostgreSQL persistence and authorized detail retrieval (Phase 3 C3.8)."""

from typing import List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.citations.exceptions import (
    CitationAccessDeniedError,
    CitationNotFoundError,
)
from backend.app.citations.schemas import CitationDetail, CitationDraft
from backend.app.core.logging import get_logger
from backend.app.models.citation import Citation
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.workspace import Workspace

logger = get_logger("knovera.citations.repository")


class CitationRepository:
    """Handles database persistence and retrieval of citation records."""

    def create_citations(
        self,
        db: Session,
        message_id: uuid.UUID,
        drafts: List[CitationDraft],
    ) -> List[Citation]:
        """Persists citation draft records for a completed assistant message."""
        citation_records: List[Citation] = []

        for idx, draft in enumerate(drafts):
            citation = Citation(
                id=uuid.uuid4(),
                workspace_id=draft.workspace_id,
                message_id=message_id,
                chunk_id=draft.chunk_id,
                claim_index=draft.claim_index,
                display_order=draft.display_order or (idx + 1),
                quote_text=draft.quote_text,
                relevance_score=draft.relevance_score,
            )
            db.add(citation)
            citation_records.append(citation)

        db.flush()
        return citation_records

    def get_citation_detail(
        self,
        db: Session,
        citation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CitationDetail:
        """Loads citation detail verifying workspace ownership and document active state.

        Args:
            db: Database session.
            citation_id: Citation record UUID.
            user_id: Authenticated user UUID.

        Raises:
            CitationNotFoundError: If citation record or active document is not found.
            CitationAccessDeniedError: If citation belongs to a workspace owned by another user.
        """
        citation = (
            db.query(Citation)
            .filter(Citation.id == citation_id)
            .first()
        )
        if not citation:
            raise CitationNotFoundError(f"Citation with ID {citation_id} was not found.")

        # Verify workspace ownership
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == citation.workspace_id)
            .first()
        )
        if not workspace:
            raise CitationNotFoundError(f"Parent workspace for citation {citation_id} was not found.")

        if workspace.owner_user_id != user_id:
            logger.warning(
                "Access denied for user %s to citation %s in workspace %s",
                user_id,
                citation_id,
                workspace.id,
            )
            raise CitationAccessDeniedError("Access to this citation is denied.")

        # Load authoritative chunk and document
        chunk = (
            db.query(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(
                DocumentChunk.id == citation.chunk_id,
                DocumentChunk.workspace_id == workspace.id,
                Document.workspace_id == workspace.id,
                Document.deleted_at.is_(None),
            )
            .first()
        )
        if not chunk:
            raise CitationNotFoundError("The underlying evidence chunk or document has been removed.")

        doc: Document = chunk.document
        doc_ext = (doc.file_extension or "").lower()

        # Format location accurately
        if doc_ext == ".pdf":
            loc_type = "pdf_pages"
            p_start = chunk.page_start or 1
            p_end = chunk.page_end or p_start
            loc_label = f"Page {p_start}" if p_start == p_end else f"Pages {p_start}–{p_end}"
        elif doc_ext in (".pptx", ".ppt"):
            loc_type = "pptx_slide"
            s_num = chunk.slide_number or 1
            loc_label = f"Slide {s_num}"
        elif doc_ext in (".docx", ".doc"):
            loc_type = "docx_section"
            sec = chunk.section_title or "Section"
            loc_label = f"Section: {sec}"
        else:
            loc_type = "document"
            loc_label = "Document"

        # Excerpt
        clean = " ".join(chunk.content.split())
        excerpt = clean[:250] + "..." if len(clean) > 250 else clean

        # Extract section path from source segments if available
        sec_path: list[str] = []
        if chunk.source_segments:
            for seg in chunk.source_segments:
                if isinstance(seg, dict) and "section_path" in seg and seg["section_path"]:
                    sec_path = seg["section_path"]
                    break

        return CitationDetail(
            citation_id=citation.id,
            display_number=citation.display_order,
            chunk_id=chunk.id,
            document_id=doc.id,
            document_name=doc.original_filename,
            document_type=doc.media_type or doc_ext,
            location_type=loc_type,
            location_label=loc_label,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            slide_number=chunk.slide_number,
            slide_title=None,
            section_title=chunk.section_title,
            section_path=sec_path,
            source_segments=chunk.source_segments or [],
            quote_text=citation.quote_text,
            excerpt=excerpt,
            claim_index=citation.claim_index,
            relevance_score=citation.relevance_score,
            created_at=citation.created_at,
        )
