"""Query validation and boundary enforcement for Semantic Retrieval (Phase 3 C3.3)."""

from typing import List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models.document import Document
from backend.app.rag.retrieval.exceptions import (
    DocumentScopeException,
    InvalidQueryException,
)


class QueryValidator:
    """Validates user query constraints and workspace document scope."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def validate_query(self, query: str) -> str:
        """Validates query string and truncates if exceeding configured budget."""
        if not query or not query.strip():
            raise InvalidQueryException("Search query cannot be empty or whitespace.")

        clean_query = query.strip()
        max_len = self.settings.EMBEDDING_QUERY_MAX_LENGTH
        if len(clean_query) > max_len:
            clean_query = clean_query[:max_len]

        return clean_query

    def validate_document_scope(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        document_ids: Optional[List[uuid.UUID]],
    ) -> List[uuid.UUID]:
        """Ensures all requested document IDs belong to the active workspace and are non-deleted."""
        if not document_ids:
            return []

        unique_ids = list(set(document_ids))
        valid_docs = (
            db.query(Document.id)
            .filter(
                Document.id.in_(unique_ids),
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .all()
        )
        valid_id_set = {d[0] for d in valid_docs}

        for doc_id in unique_ids:
            if doc_id not in valid_id_set:
                raise DocumentScopeException(
                    f"Document '{doc_id}' does not exist or does not belong to workspace '{workspace_id}'."
                )

        return unique_ids
