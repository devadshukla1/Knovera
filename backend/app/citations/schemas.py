"""Schemas for Knovera citation drafts and presentation details (Phase 3 C3.8)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class CitationDraft(BaseModel):
    """In-memory citation candidate assembled before database persistence."""

    model_config = ConfigDict(from_attributes=True)

    source_id: str = Field(..., description="Prompt-local source identifier (e.g. 'S1')")
    chunk_id: uuid.UUID = Field(..., description="Authoritative PostgreSQL chunk UUID")
    document_id: uuid.UUID = Field(..., description="Authoritative PostgreSQL document UUID")
    workspace_id: uuid.UUID = Field(..., description="Workspace boundary UUID")

    claim_index: Optional[int] = Field(None, description="Index of supported claim")
    display_order: int = Field(default=0, ge=0, description="Sequential citation display index")

    document_name: str = Field(..., description="Original filename from PostgreSQL")
    document_type: str = Field(default="application/pdf", description="Media type or extension")

    location_type: str = Field(..., description="'pdf_pages', 'docx_section', 'pptx_slide', etc.")
    location_label: str = Field(..., description="Human-readable location label (e.g. 'Pages 4–5')")

    page_start: Optional[int] = Field(None, ge=1, description="1-based starting page")
    page_end: Optional[int] = Field(None, ge=1, description="1-based ending page")
    slide_number: Optional[int] = Field(None, ge=1, description="1-based slide number")
    slide_title: Optional[str] = Field(None, description="PPTX slide heading")

    section_title: Optional[str] = Field(None, description="DOCX section heading")
    section_path: List[str] = Field(default_factory=list, description="DOCX heading path")
    paragraph_index: Optional[int] = Field(None, description="DOCX paragraph index")

    source_segments: List[Dict[str, Any]] = Field(default_factory=list, description="Original source coordinates")
    quote_text: Optional[str] = Field(None, description="Exact verified verbatim quote from chunk")
    excerpt: str = Field(..., description="Authoritative chunk preview text")
    relevance_score: Optional[float] = Field(None, description="Optional cosine similarity / relevance score")


class CitationDetail(BaseModel):
    """Public API model for displaying full citation provenance and text."""

    model_config = ConfigDict(from_attributes=True)

    citation_id: uuid.UUID = Field(..., description="Citation record UUID")
    display_number: int = Field(default=1, ge=1, description="1-based citation number (1, 2, ...)")

    chunk_id: uuid.UUID = Field(..., description="Underlying chunk UUID")
    document_id: uuid.UUID = Field(..., description="Document UUID")
    document_name: str = Field(..., description="Original document filename")
    document_type: str = Field(default="application/pdf")

    location_type: str = Field(..., description="'pdf_pages', 'docx_section', 'pptx_slide'")
    location_label: str = Field(..., description="Formatted location string")

    page_start: Optional[int] = Field(None, ge=1)
    page_end: Optional[int] = Field(None, ge=1)
    slide_number: Optional[int] = Field(None, ge=1)
    slide_title: Optional[str] = None

    section_title: Optional[str] = None
    section_path: List[str] = Field(default_factory=list)

    source_segments: List[Dict[str, Any]] = Field(default_factory=list)
    quote_text: Optional[str] = None
    excerpt: str = Field(..., description="Clean excerpt of original evidence")

    claim_index: Optional[int] = None
    relevance_score: Optional[float] = None
    created_at: Optional[datetime] = None
