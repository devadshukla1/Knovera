"""Workspace-scoped document duplicate detection service for Knovera Ingestion (Chunk C2.8)."""

from typing import Optional
import uuid
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.core.logging import get_logger
from backend.app.ingestion.errors.taxonomy import DuplicateDocumentError
from backend.app.models.document import Document

logger = get_logger("knovera.ingestion.duplicates")


class DuplicateDetectionService:
    """Service for detecting and enforcing workspace-scoped SHA-256 duplicate boundaries."""

    def check_duplicate(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        sha256_hash: str,
        exclude_document_id: Optional[uuid.UUID] = None,
        allow_failed_retry: bool = True,
    ) -> Optional[Document]:
        """Checks if an active (non-deleted) document with the given SHA-256 exists in the workspace.

        Args:
            db: Database session.
            workspace_id: The workspace scope to check within.
            sha256_hash: Lowercase SHA-256 hex string of the file content.
            exclude_document_id: Optional document ID to ignore (used during reprocessing).
            allow_failed_retry: If True, documents whose processing_status is 'failed' do not block re-upload.

        Returns:
            The existing active Document if a duplicate exists, else None.
        """
        query = (
            db.query(Document)
            .filter(
                Document.workspace_id == workspace_id,
                Document.sha256 == sha256_hash,
                Document.deleted_at.is_(None),
            )
        )
        if exclude_document_id is not None:
            query = query.filter(Document.id != exclude_document_id)

        existing = query.first()
        if existing and allow_failed_retry and existing.processing_status == "failed":
            return None
        return existing

    def ensure_not_duplicate(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        sha256_hash: str,
        exclude_document_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Enforces that no active duplicate document exists in the workspace.

        Raises:
            DuplicateDocumentError: If an active duplicate is detected.
        """
        existing = self.check_duplicate(
            db=db,
            workspace_id=workspace_id,
            sha256_hash=sha256_hash,
            exclude_document_id=exclude_document_id,
        )
        if existing:
            logger.info(
                "Duplicate document rejected in workspace %s: matches existing document %s (sha256=%s)",
                workspace_id,
                existing.id,
                sha256_hash,
            )
            raise DuplicateDocumentError(
                message=f"A document with identical content already exists in this workspace (document_id={existing.id}).",
                existing_document_id=existing.id,
            )

    def handle_integrity_error(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        sha256_hash: str,
        exc: IntegrityError,
    ) -> DuplicateDocumentError:
        """Handles race-condition IntegrityError from unique index violation on concurrent uploads.

        Converts database unique constraint violation to domain DuplicateDocumentError.
        """
        logger.warning(
            "Concurrent upload race condition detected in workspace %s for sha256 %s: %s",
            workspace_id,
            sha256_hash,
            exc,
        )
        db.rollback()
        existing = self.check_duplicate(db, workspace_id, sha256_hash)
        existing_id = existing.id if existing else uuid.uuid4()
        return DuplicateDocumentError(
            message=f"A document with identical content already exists in this workspace (document_id={existing_id}).",
            existing_document_id=existing_id,
        )
