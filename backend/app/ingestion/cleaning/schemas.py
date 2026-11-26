"""Schemas and statistics for text cleaning and normalisation in Knovera."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from backend.app.ingestion.schemas.extracted_document import ExtractedBlock


class CleaningMetadata(BaseModel):
    """Detailed deterministic statistics and telemetry from text normalisation."""

    model_config = ConfigDict(frozen=True)

    original_character_count: int = Field(..., ge=0)
    normalised_character_count: int = Field(..., ge=0)
    removed_control_characters: int = Field(default=0, ge=0)
    normalised_unicode_characters: int = Field(default=0, ge=0)
    whitespace_changes: int = Field(default=0, ge=0)
    dehyphenation_count: int = Field(default=0, ge=0)
    boilerplate_lines_removed: int = Field(default=0, ge=0)
    cleaning_version: str = Field(default="v1.0")
    warnings: List[str] = Field(default_factory=list)


class NormalisedBlock(BaseModel):
    """A cleaned and normalised block of document text preserving provenance."""

    model_config = ConfigDict(frozen=True)

    block_index: int = Field(..., ge=0)
    block_type: str = Field(...)
    raw_text: str = Field(..., description="Original text prior to cleaning")
    text: str = Field(..., description="Normalised clean text")
    source_type: str = Field(...)

    page_number: Optional[int] = None
    slide_number: Optional[int] = None

    section_title: Optional[str] = None
    section_path: List[str] = Field(default_factory=list)
    paragraph_index: Optional[int] = None
    table_index: Optional[int] = None
    row_index: Optional[int] = None

    source_start_offset: Optional[int] = None
    source_end_offset: Optional[int] = None

    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NormalisedDocument(BaseModel):
    """Normalized document representation ready for structure-aware semantic chunking."""

    model_config = ConfigDict(frozen=True)

    document_id: Optional[uuid.UUID] = None
    filename: str
    file_type: str
    total_pages: Optional[int] = None
    total_slides: Optional[int] = None

    blocks: List[NormalisedBlock] = Field(default_factory=list)
    cleaning_metadata: CleaningMetadata

    parser_name: str
    parser_version: str
    normalised_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
