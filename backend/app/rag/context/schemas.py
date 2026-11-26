"""Schemas for Context Construction and Evidence Packaging (Phase 3 C3.5)."""

from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ContextSource(BaseModel):
    """Single evidence chunk prepared for generation prompt with assigned prompt-local source ID."""

    model_config = ConfigDict(from_attributes=True)

    source_id: str = Field(..., description="Prompt-local source identifier, e.g. 'S1', 'S2'")
    chunk_id: uuid.UUID = Field(..., description="PostgreSQL authoritative chunk UUID")
    document_id: uuid.UUID = Field(..., description="Parent document UUID")
    workspace_id: uuid.UUID = Field(..., description="Authoritative workspace UUID")
    document_name: str = Field(..., description="Human-readable filename")

    page_start: Optional[int] = Field(None, description="1-based starting page number for PDFs")
    page_end: Optional[int] = Field(None, description="1-based ending page number for PDFs")
    slide_number: Optional[int] = Field(None, description="1-based slide number for presentations")
    section_title: Optional[str] = Field(None, description="Document section or heading title")

    content: str = Field(..., description="Evidence text excerpt")
    retrieval_rank: int = Field(..., ge=1, description="1-based semantic retrieval rank")
    retrieval_distance: Optional[float] = Field(None, description="Chroma cosine distance")
    is_truncated: bool = Field(default=False, description="True if passage was excerpted due to budget")
    source_segments: List[Dict[str, Any]] = Field(default_factory=list, description="Original source coordinates")


class ContextPackage(BaseModel):
    """Complete structured evidence package passed to prompt engineering."""

    query: str = Field(..., description="User search / question query")
    sources: List[ContextSource] = Field(default_factory=list, description="Ordered, deduplicated evidence sources")

    included_source_count: int = Field(default=0, ge=0)
    omitted_source_count: int = Field(default=0, ge=0)

    estimated_input_tokens: int = Field(default=0, ge=0, description="Estimated total tokens for this context")
    available_context_tokens: int = Field(..., ge=0, description="Total input token budget allowed by model")
    reserved_output_tokens: int = Field(..., ge=0, description="Tokens reserved for model completion")

    context_version: str = Field(default="context-v1")
    warnings: List[str] = Field(default_factory=list)

    # Fast internal lookup mapping: source_id ('S1') -> authoritative metadata
    source_mapping: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
