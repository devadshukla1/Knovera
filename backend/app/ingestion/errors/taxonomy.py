"""Standardized error taxonomy and retry classification for Knovera Ingestion (Chunk C2.8)."""

from typing import Optional, Union
import uuid

from backend.app.ingestion.extractors.exceptions import ExtractionException


# --- Custom Domain Exceptions for C2.8 ---

class DuplicateDocumentError(ExtractionException):
    """Raised when an active document with identical SHA-256 already exists in the workspace."""

    error_code = "duplicate_document"

    def __init__(self, message: str, existing_document_id: uuid.UUID) -> None:
        super().__init__(message, error_code=self.error_code)
        self.existing_document_id = existing_document_id


class FileIntegrityMismatchError(ExtractionException):
    """Raised when SHA-256 of stored bytes does not match recorded document hash."""

    error_code = "file_integrity_mismatch"


class StorageFileMissingError(ExtractionException):
    """Raised when physical file cannot be located on disk."""

    error_code = "storage_file_missing"


class JobAlreadyRunningError(ExtractionException):
    """Raised when another worker is actively processing the target document/job."""

    error_code = "job_already_running"


class ProcessingTimeoutError(ExtractionException):
    """Raised when ingestion stage exceeds bounded execution timeout."""

    error_code = "processing_timeout"


class RetryLimitExceededError(ExtractionException):
    """Raised when an ingestion job reaches maximum retry attempts."""

    error_code = "retry_limit_exceeded"


# --- Error Classification Taxonomy ---

PERMANENT_ERRORS = {
    # Upload errors
    "unsupported_file_type",
    "file_too_large",
    "empty_file",
    "empty_upload",
    "invalid_file_signature",
    "invalid_pdf_signature",
    "invalid_zip_signature",
    "duplicate_document",
    "workspace_not_found",
    # Format extraction errors
    "invalid_pdf",
    "pdf_encrypted",
    "invalid_docx",
    "docx_encrypted",
    "invalid_pptx",
    "pptx_encrypted",
    "no_extractable_text",
    "pdf_page_limit_exceeded",
    "pptx_slide_limit_exceeded",
    "docx_paragraph_limit_exceeded",
    "pdf_text_limit_exceeded",
    # Chunking and provenance validation errors
    "chunk_provenance_invalid",
    "chunk_size_validation_failed",
    "normalization_failed",
    "empty_normalized_document",
}

RETRYABLE_ERRORS = {
    "storage_write_failed",
    "database_persistence_failed",
    "file_integrity_mismatch",
    "storage_file_missing",
    "processing_timeout",
    "temporary_io_error",
    "connection_error",
    "lock_acquisition_failed",
}

SAFE_ERROR_SUMMARIES = {
    "duplicate_document": "This document already exists in the current workspace.",
    "unsupported_file_type": "Only PDF (.pdf), Word (.docx), and PowerPoint (.pptx) documents are supported.",
    "file_too_large": "The uploaded file exceeds the maximum allowed size limit.",
    "empty_file": "The uploaded file is empty (0 bytes).",
    "invalid_pdf_signature": "File does not contain a valid %PDF- header signature.",
    "invalid_zip_signature": "File is not a valid OpenXML ZIP package.",
    "pdf_encrypted": "The PDF document is password-protected or encrypted and cannot be processed.",
    "docx_encrypted": "The Word document is password-protected or encrypted.",
    "pptx_encrypted": "The PowerPoint presentation is password-protected or encrypted.",
    "no_extractable_text": "No extractable text found. Scanned documents requiring OCR are not supported in this version.",
    "pdf_page_limit_exceeded": "Document exceeds maximum allowed page count.",
    "pptx_slide_limit_exceeded": "Presentation exceeds maximum allowed slide count.",
    "docx_paragraph_limit_exceeded": "Document exceeds maximum allowed paragraph count.",
    "pdf_text_limit_exceeded": "Total extracted character count exceeds safety limit.",
    "chunk_provenance_invalid": "Document failed source provenance and coordinate integrity checks.",
    "file_integrity_mismatch": "Document content failed cryptographic SHA-256 integrity verification.",
    "storage_write_failed": "Failed to write file to storage. Temporary error, safe to retry.",
    "database_persistence_failed": "Failed to persist document data in database. Temporary error, safe to retry.",
    "retry_limit_exceeded": "Document failed processing after multiple retry attempts.",
}


def is_retryable_error(error_code_or_exc: Union[str, Exception]) -> bool:
    """Determines whether a given error code or exception qualifies for bounded retry."""
    if isinstance(error_code_or_exc, str):
        code = error_code_or_exc
    else:
        code = getattr(error_code_or_exc, "error_code", "")

    if code in PERMANENT_ERRORS:
        return False
    if code in RETRYABLE_ERRORS:
        return True

    # Check for common transient database or network exceptions
    exc_str = str(error_code_or_exc).lower()
    if any(k in exc_str for k in ("operationalerror", "timeout", "connection reset", "broken pipe", "deadlock")):
        return True

    # Default to permanent if unknown to avoid infinite retries
    return False


def get_safe_error_summary(error_code: str, fallback_message: Optional[str] = None) -> str:
    """Returns a sanitized, user-safe error summary for API responses."""
    return SAFE_ERROR_SUMMARIES.get(error_code, fallback_message or "An error occurred during document processing.")
