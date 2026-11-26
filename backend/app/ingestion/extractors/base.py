"""Base extractor interface for Knovera document ingestion."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
import uuid

from backend.app.ingestion.schemas.extracted_document import ExtractedDocument


class BaseExtractor(ABC):
    """Abstract interface for format-specific text and structure extractors."""

    @abstractmethod
    def extract_document(
        self,
        file_path: Path,
        document_id: Optional[uuid.UUID] = None,
    ) -> ExtractedDocument:
        """Extracts structured blocks and format provenance into an ExtractedDocument."""
        pass

    def extract(
        self,
        file_path: Path,
        document_id: Optional[uuid.UUID] = None,
    ) -> Any:
        """Default or format-specific extraction entry point."""
        return self.extract_document(file_path, document_id=document_id)
