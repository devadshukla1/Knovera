"""Schemas for semantic chunking and source provenance in Knovera."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ChunkSegment(BaseModel):
    """Provenance mapping connecting a chunk back to its source document elements."""

    model_config = ConfigDict(frozen=True)

    source_type: str = Field(..., description="pdf_page, docx_paragraph, docx_table, pptx_slide, etc.")
    block_index: int = Field(..., ge=0)
    page_number: Optional[int] = Field(None, ge=1)
    slide_number: Optional[int] = Field(None, ge=1)
    section_title: Optional[str] = None
    paragraph_index: Optional[int] = None
    table_index: Optional[int] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None


class DocumentChunkData(BaseModel):
    """In-memory representation of a semantically chunked piece of content."""

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(..., description="Deterministic UUID5 chunk identifier")
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int = Field(..., ge=0, description="Sequential index within document")
    content: str = Field(..., description="Authoritative cleaned chunk text")
    content_hash: str = Field(..., description="SHA-256 hex digest of chunk text")

    page_start: Optional[int] = Field(None, ge=1, description="Starting 1-based page number")
    page_end: Optional[int] = Field(None, ge=1, description="Ending 1-based page number")
    slide_number: Optional[int] = Field(None, ge=1, description="PPTX slide number if applicable")
    section_title: Optional[str] = Field(None, description="Section or heading title")

    source_start_offset: Optional[int] = None
    source_end_offset: Optional[int] = None

    token_count: int = Field(..., ge=0)
    token_count_method: str = Field(default="estimate_v1")

    parser_version: str
    cleaning_version: str
    chunking_version: str

    source_segments: List[ChunkSegment] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChunkingDiagnostics(BaseModel):
    """Quality and telemetry metrics generated during semantic chunking."""

    model_config = ConfigDict(frozen=True)

    total_extracted_blocks: int = Field(..., ge=0)
    total_normalised_characters: int = Field(..., ge=0)
    chunk_count: int = Field(..., ge=0)
    min_token_count: int = Field(default=0, ge=0)
    max_token_count: int = Field(default=0, ge=0)
    avg_token_count: float = Field(default=0.0, ge=0.0)
    empty_chunk_count: int = Field(default=0, ge=0)
    target_token_budget: int
    max_token_budget: int
    overlap_token_budget: int
    chunking_version: str
    warnings: List[str] = Field(default_factory=list)
