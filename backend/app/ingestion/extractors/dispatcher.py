"""Format detection and extractor dispatch for Knovera Ingestion."""

from pathlib import Path
from typing import Dict, Optional

from backend.app.ingestion.extractors.base import BaseExtractor
from backend.app.ingestion.extractors.docx_extractor import DOCXExtractor
from backend.app.ingestion.extractors.exceptions import UnsupportedFormatError
from backend.app.ingestion.extractors.pdf_extractor import PyMuPDFExtractor
from backend.app.ingestion.extractors.pptx_extractor import PPTXExtractor
from backend.app.ingestion.extractors.txt_extractor import TXTExtractor

# Global registry of format-specific extractors
EXTRACTORS: Dict[str, BaseExtractor] = {
    ".pdf": PyMuPDFExtractor(),
    ".docx": DOCXExtractor(),
    ".pptx": PPTXExtractor(),
    ".txt": TXTExtractor(),
    ".md": TXTExtractor(),
}


def get_extractor_for_extension(extension: str) -> BaseExtractor:
    """Returns the extractor corresponding to the specified file extension (.pdf, .docx, .pptx)."""
    norm_ext = extension.strip().lower()
    if not norm_ext.startswith("."):
        norm_ext = f".{norm_ext}"

    extractor = EXTRACTORS.get(norm_ext)
    if not extractor:
        raise UnsupportedFormatError(
            f"Unsupported file format '{norm_ext}'. Supported formats: {list(EXTRACTORS.keys())}"
        )
    return extractor


def detect_and_get_extractor(file_path: Path) -> BaseExtractor:
    """Detects format from file path extension and returns registered extractor."""
    ext = file_path.suffix.lower()
    return get_extractor_for_extension(ext)
