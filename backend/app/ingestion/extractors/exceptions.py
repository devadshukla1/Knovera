"""Ingestion and extraction exceptions with standardized error codes."""

from typing import Optional


class ExtractionException(Exception):
    """Base exception for document extraction failures."""

    error_code: str = "extraction_failed"

    def __init__(self, message: str, error_code: Optional[str] = None) -> None:
        super().__init__(message)
        if error_code:
            self.error_code = error_code


# PDF Exceptions
class InvalidPDFSignatureError(ExtractionException):
    """Raised when file signature lacks valid %PDF header."""

    error_code = "invalid_pdf_signature"


class InvalidPDFError(ExtractionException):
    """Raised when PDF bytes cannot be opened or parsed by PyMuPDF."""

    error_code = "invalid_pdf"


class PDFEncryptedError(ExtractionException):
    """Raised when PDF is encrypted or requires a password."""

    error_code = "pdf_encrypted"


class PDFPageLimitExceededError(ExtractionException):
    """Raised when PDF page count exceeds configured MAX_PDF_PAGES."""

    error_code = "pdf_page_limit_exceeded"


class PDFTextLimitExceededError(ExtractionException):
    """Raised when extracted text exceeds MAX_EXTRACTED_TEXT_CHARS."""

    error_code = "pdf_text_limit_exceeded"


# DOCX Exceptions
class InvalidDOCXError(ExtractionException):
    """Raised when DOCX file is corrupted, not a valid ZIP container, or unreadable."""

    error_code = "invalid_docx"


class DOCXEncryptedError(ExtractionException):
    """Raised when DOCX document is password-protected or encrypted."""

    error_code = "docx_encrypted"


class ParagraphLimitExceededError(ExtractionException):
    """Raised when DOCX paragraph count exceeds configured threshold."""

    error_code = "docx_paragraph_limit_exceeded"


# PPTX Exceptions
class InvalidPPTXError(ExtractionException):
    """Raised when PPTX file is corrupted, not a valid presentation container, or unreadable."""

    error_code = "invalid_pptx"


class PPTXEncryptedError(ExtractionException):
    """Raised when PPTX presentation is password-protected or encrypted."""

    error_code = "pptx_encrypted"


class SlideLimitExceededError(ExtractionException):
    """Raised when PPTX slide count exceeds configured MAX_PPTX_SLIDES."""

    error_code = "pptx_slide_limit_exceeded"


# General Ingestion Exceptions
class UnsupportedFormatError(ExtractionException):
    """Raised when the document format or MIME type is not supported."""

    error_code = "unsupported_file_type"


class NoExtractableTextError(ExtractionException):
    """Raised when document contains no extractable text (e.g. scanned document or blank)."""

    error_code = "no_extractable_text"


class DocumentCorruptedError(ExtractionException):
    """Raised when a document container is structurally corrupted."""

    error_code = "document_corrupted"
