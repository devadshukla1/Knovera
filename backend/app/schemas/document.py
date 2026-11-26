"""Pydantic request and response schemas for documents, pages, chunks, and ingestion jobs."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    """Public representation of a document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    original_filename: str
    media_type: str
    file_size_bytes: int
    processing_status: str
    processing_stage: Optional[str] = None
    page_count: Optional[int] = None
    slide_count: Optional[int] = None
    extracted_block_count: Optional[int] = None
    total_characters: Optional[int] = None
    chunk_count: Optional[int] = None
    pipeline_version: Optional[str] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    """Detailed document representation including extraction metadata."""

    extraction_metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentPageResponse(BaseModel):
    """Extracted text and provenance for a single page."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    extracted_text: str
    character_count: int
    is_empty: bool
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class DocumentPagesListResponse(BaseModel):
    """List of document pages."""

    document_id: uuid.UUID
    total_pages: int
    pages: List[DocumentPageResponse]


class DocumentChunkResponse(BaseModel):
    """Chunk representation with semantic content and source provenance."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    workspace_id: uuid.UUID
    chunk_index: int
    content: str
    content_hash: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    slide_number: Optional[int] = None
    section_title: Optional[str] = None
    token_count: Optional[int] = None
    token_count_method: Optional[str] = None
    parser_version: str
    cleaning_version: str
    chunking_version: str
    source_segments: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    created_at: datetime


class DocumentChunksListResponse(BaseModel):
    """List of chunks for a document."""

    document_id: uuid.UUID
    total_chunks: int
    chunks: List[DocumentChunkResponse]


class IngestionJobResponse(BaseModel):
    """Execution status and metrics for an ingestion job."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    workspace_id: uuid.UUID
    job_type: str
    status: str
    stage: Optional[str] = None
    attempt_count: int
    max_attempts: int
    last_error_code: Optional[str] = None
    last_error_summary: Optional[str] = None
    processing_metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    pipeline_version: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class IngestionJobsListResponse(BaseModel):
    """List of ingestion jobs for a document."""

    document_id: uuid.UUID
    total_jobs: int
    jobs: List[IngestionJobResponse]
