"""Typed document metadata and provenance schema for Knovera Ingestion."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class DocumentMetadata(BaseModel):
    """Authoritative structured metadata model for ingested documents per C2.6 specification."""

    model_config = ConfigDict(frozen=True)

    document_id: uuid.UUID
    workspace_id: uuid.UUID

    filename: str
    extension: str
    media_type: str
    file_size_bytes: int
    sha256: str

    page_count: Optional[int] = None
    slide_count: Optional[int] = None

    extracted_block_count: int = Field(default=0, ge=0)
    total_characters: int = Field(default=0, ge=0)

    empty_page_count: int = Field(default=0, ge=0)
    empty_slide_count: int = Field(default=0, ge=0)

    parser_name: str
    parser_version: str

    cleaning_version: str = "v1.0"
    chunking_version: str = "semantic-v1"
    pipeline_version: str = "v1.0"

    chunk_count: int = Field(default=0, ge=0)
    total_chunk_characters: int = Field(default=0, ge=0)
    token_count_method: str = "estimate_v1"

    processing_status: str
    processing_stage: Optional[str] = None

    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    processing_metrics: Dict[str, Any] = Field(default_factory=dict)
