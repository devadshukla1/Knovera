"""Citation Validator validating model source IDs against ContextPackage and PostgreSQL (Phase 3 C3.8)."""

from typing import Any, Dict, List, Optional, Set
import uuid
from sqlalchemy.orm import Session

from backend.app.citations.exceptions import (
    CitationDocumentDeletedError,
    CitationWorkspaceMismatchError,
    UnknownSourceIdError,
)
from backend.app.core.logging import get_logger
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.rag.context.schemas import ContextPackage

logger = get_logger("knovera.citations.validator")


class CitationValidator:
    """Validates prompt-local source IDs and ensures PostgreSQL provenance integrity."""

    def validate_source_ids(
        self,
        source_ids: List[str],
        context_package: ContextPackage,
        db: Session,
        workspace_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Validates that candidate source IDs are authorized and present in PostgreSQL.

        Args:
            source_ids: List of prompt-local source IDs (e.g. ['S1', 'S2']).
            context_package: The ContextPackage used for generation.
            db: Active SQLAlchemy database session.
            workspace_id: The authenticated workspace UUID.

        Returns:
            List of verified source metadata dictionaries.

        Raises:
            UnknownSourceIdError: If an unrecognized source ID is encountered.
            CitationWorkspaceMismatchError: If a source belongs to another workspace.
            CitationDocumentDeletedError: If a cited document has been deleted.
        """
        valid_sources: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()

        for sid in source_ids:
            clean_sid = sid.strip().upper()
            if not clean_sid.startswith("S") or clean_sid in seen_ids:
                continue
            seen_ids.add(clean_sid)

            if clean_sid not in context_package.source_mapping:
                logger.warning("Model cited unknown source ID '%s' not in ContextPackage", clean_sid)
                raise UnknownSourceIdError(f"Source ID '{clean_sid}' does not exist in the active retrieval context.")

            meta = context_package.source_mapping[clean_sid]
            chunk_id = uuid.UUID(str(meta["chunk_id"]))

            # Verify chunk and active document in PostgreSQL
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
                # Check whether it's deleted or from a wrong workspace
                deleted_check = (
                    db.query(Document)
                    .join(DocumentChunk, DocumentChunk.document_id == Document.id)
                    .filter(DocumentChunk.id == chunk_id)
                    .first()
                )
                if deleted_check and deleted_check.deleted_at is not None:
                    raise CitationDocumentDeletedError(f"Cited document for chunk {chunk_id} has been deleted.")
                if deleted_check and deleted_check.workspace_id != workspace_id:
                    raise CitationWorkspaceMismatchError(
                        f"Cross-workspace citation breach: chunk {chunk_id} does not belong to workspace {workspace_id}."
                    )
                raise UnknownSourceIdError(f"Chunk {chunk_id} for source {clean_sid} was not found in database.")

            valid_sources.append(meta)

        return valid_sources
