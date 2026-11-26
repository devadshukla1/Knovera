"""Source Scope Resolver for Knovera Study Material Generation (Phase 8 Part 1).

Resolves authorized, active document chunks within a workspace boundary
supporting multiple scopes:
- workspace (all active documents)
- documents (specific subset of document IDs)
- document (single document)
- topic (chunks assigned to a topic cluster)
- chunks (explicit chunk IDs)

Guarantees:
- Strict workspace tenancy isolation.
- Exclusion of soft-deleted documents (deleted_at IS NOT NULL).
- Deterministic ordering by document title and chunk index.
"""

from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.ml.study_materials.schemas import SourceScope, SourceScopeType
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.topic_assignment import TopicAssignment

logger = get_logger("knovera.study_materials.source_resolver")


class ResolvedChunk(BaseModel):
    """Normalized source chunk resolved from PostgreSQL."""
    model_config = ConfigDict(from_attributes=True)

    chunk_id: UUID
    document_id: UUID
    document_title: str
    chunk_index: int
    page_number: Optional[int] = None
    heading: Optional[str] = None
    content: str
    token_count: int = 0


class SourceResolver:
    """Resolves and validates source content chunks for study material generation."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def resolve(
        self,
        workspace_id: UUID,
        scope: SourceScope,
        max_chunks: Optional[int] = None,
    ) -> List[ResolvedChunk]:
        """Resolves active chunks belonging to workspace matching scope specification."""
        logger.info(
            "Resolving source chunks for workspace %s with scope %s",
            workspace_id,
            scope.scope_type.value,
        )

        base_stmt = (
            select(DocumentChunk, Document.original_filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.workspace_id == workspace_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
        )

        if scope.scope_type in (SourceScopeType.DOCUMENT, SourceScopeType.DOCUMENTS):
            target_doc_ids = scope.document_ids or []
            if not target_doc_ids:
                logger.warning("Empty document_ids passed for document scope")
                return []
            base_stmt = base_stmt.where(DocumentChunk.document_id.in_(target_doc_ids))

        elif scope.scope_type == SourceScopeType.TOPIC:
            if not scope.topic_id:
                logger.warning("Empty topic_id passed for topic scope")
                return []
            base_stmt = (
                base_stmt.join(TopicAssignment, TopicAssignment.chunk_id == DocumentChunk.id)
                .where(
                    TopicAssignment.topic_id == scope.topic_id,
                    TopicAssignment.workspace_id == workspace_id,
                )
            )

        elif scope.scope_type == SourceScopeType.CHUNKS:
            target_chunk_ids = scope.chunk_ids or []
            if not target_chunk_ids:
                logger.warning("Empty chunk_ids passed for chunks scope")
                return []
            base_stmt = base_stmt.where(DocumentChunk.id.in_(target_chunk_ids))

        elif scope.scope_type == SourceScopeType.WORKSPACE:
            # All active documents in workspace
            pass

        # Order deterministically
        base_stmt = base_stmt.order_by(Document.original_filename.asc(), DocumentChunk.chunk_index.asc())

        if max_chunks and max_chunks > 0:
            base_stmt = base_stmt.limit(max_chunks)

        results = self.session.execute(base_stmt).all()

        resolved: List[ResolvedChunk] = []
        for chunk, doc_filename in results:
            resolved.append(
                ResolvedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_title=doc_filename,
                    chunk_index=chunk.chunk_index,
                    page_number=getattr(chunk, "page_start", None) or getattr(chunk, "page_number", None),
                    heading=getattr(chunk, "section_title", None) or getattr(chunk, "heading", None),
                    content=chunk.content or "",
                    token_count=getattr(chunk, "token_count", 0) or len((chunk.content or "").split()),
                )
            )

        logger.info(
            "Resolved %d chunks across workspace %s (scope: %s)",
            len(resolved),
            workspace_id,
            scope.scope_type.value,
        )
        return resolved
