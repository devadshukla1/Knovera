"""Document extractors for Knovera Ingestion."""

from backend.app.ingestion.extractors.base import BaseExtractor
from backend.app.ingestion.extractors.dispatcher import (
    EXTRACTORS,
    detect_and_get_extractor,
    get_extractor_for_extension,
)
from backend.app.ingestion.extractors.docx_extractor import DOCXExtractor
from backend.app.ingestion.extractors.exceptions import (
    DOCXEncryptedError,
    DocumentCorruptedError,
    ExtractionException,
    InvalidDOCXError,
    InvalidPDFError,
    InvalidPDFSignatureError,
    InvalidPPTXError,
    NoExtractableTextError,
    ParagraphLimitExceededError,
    PDFEncryptedError,
    PDFPageLimitExceededError,
    PDFTextLimitExceededError,
    PPTXEncryptedError,
    SlideLimitExceededError,
    UnsupportedFormatError,
)
from backend.app.ingestion.extractors.pdf_extractor import PyMuPDFExtractor
from backend.app.ingestion.extractors.pptx_extractor import PPTXExtractor

__all__ = [
    "BaseExtractor",
    "PyMuPDFExtractor",
    "DOCXExtractor",
    "PPTXExtractor",
    "EXTRACTORS",
    "get_extractor_for_extension",
    "detect_and_get_extractor",
    "ExtractionException",
    "InvalidPDFSignatureError",
    "InvalidPDFError",
    "PDFEncryptedError",
    "PDFPageLimitExceededError",
    "PDFTextLimitExceededError",
    "InvalidDOCXError",
    "DOCXEncryptedError",
    "ParagraphLimitExceededError",
    "InvalidPPTXError",
    "PPTXEncryptedError",
    "SlideLimitExceededError",
    "UnsupportedFormatError",
    "NoExtractableTextError",
    "DocumentCorruptedError",
]
