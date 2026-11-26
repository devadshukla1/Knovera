"""Extraction orchestrator service for Knovera Phase 2."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.ingestion.extractors.exceptions import ExtractionException
from backend.app.ingestion.extractors.pdf_extractor import PyMuPDFExtractor
from backend.app.ingestion.schemas.extraction import DocumentExtractionResult
from backend.app.models.document import Document, DocumentPage
from backend.app.storage.base import StorageService

logger = get_logger("knovera.ingestion.service")


class ExtractionService:
    """Coordinates format extractor execution, database transaction, and page persistence."""

    def __init__(self, extractor: Optional[PyMuPDFExtractor] = None) -> None:
        self.pdf_extractor = extractor or PyMuPDFExtractor()

    def process_pdf_document(
        self,
        db: Session,
        document: Document,
        storage: StorageService,
    ) -> DocumentExtractionResult:
        """Executes PDF extraction and persists extracted page records transactionally.

        Guarantees:
            - Document status is updated to 'extracting' -> 'pdf_extraction' during work.
            - On success: page-by-page DocumentPage rows are persisted, and document transitions
              to 'queued' -> 'extraction_complete_awaiting_chunking'. (Never 'ready'!).
            - On failure: DocumentPage rows are rolled back, and document transitions to
              'failed' with error_code and error_summary. Original file is retained.
        """
        # 1. Update status to extracting
        document.processing_status = "extracting"
        document.processing_stage = "pdf_extraction"
        document.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(document)

        try:
            file_path = storage.get_absolute_path(document.storage_key)
            result = self.pdf_extractor.extract(file_path, document_id=document.id)

            # 2. Clear any existing page records (for idempotent reprocessing)
            db.query(DocumentPage).filter(DocumentPage.document_id == document.id).delete()

            # 3. Create DocumentPage records
            now_utc = datetime.now(timezone.utc)
            for page in result.pages:
                page_record = DocumentPage(
                    workspace_id=document.workspace_id,
                    document_id=document.id,
                    page_number=page.page_number,
                    extracted_text=page.text,
                    character_count=page.character_count,
                    is_empty=page.is_empty,
                    warnings=[w.model_dump() for w in page.warnings],
                    created_at=now_utc,
                )
                db.add(page_record)

            # 4. Update Document metadata and status
            document.page_count = result.page_count
            document.extraction_metadata = {
                "parser": result.parser_name,
                "parser_version": result.parser_version,
                "extracted_at": result.extracted_at,
                "page_count": result.page_count,
                "extracted_pages": result.extracted_pages,
                "empty_pages": result.empty_pages,
                "total_characters": result.total_characters,
                "ocr_required": result.ocr_required,
                "warnings": [w.model_dump() for w in result.warnings],
            }
            document.processing_status = "queued"
            document.processing_stage = "extraction_complete_awaiting_chunking"
            document.error_code = None
            document.error_summary = None
            document.updated_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(document)
            logger.info("Successfully persisted extraction for document %s", document.id)
            return result

        except Exception as exc:
            db.rollback()
            error_code = getattr(exc, "error_code", "pdf_extraction_failed")
            error_summary = str(exc)

            logger.warning(
                "Document %s extraction failed (%s): %s",
                document.id,
                error_code,
                error_summary,
            )

            # Update document to failed state in isolated commit
            document.processing_status = "failed"
            document.processing_stage = "pdf_extraction"
            document.error_code = error_code
            document.error_summary = error_summary
            document.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(document)

            if isinstance(exc, ExtractionException):
                raise
            raise ExtractionException(f"Extraction failed: {exc}", error_code=error_code) from exc
