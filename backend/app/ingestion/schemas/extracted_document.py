"""Common structured extraction representation for Knovera Ingestion.

Unified data model across all document types (PDF, DOCX, PPTX).
Decouples extractors from downstream text cleaning and semantic chunking.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ExtractedBlock(BaseModel):
    """Atomic structural unit of content extracted from a document."""

    model_config = ConfigDict(frozen=True)

    block_index: int = Field(..., ge=0, description="Sequential 0-based index of the block in the document")
    block_type: str = Field(
        ...,
        description="Type of structural block: heading, paragraph, list_item, table, slide_title, shape_text, page_text",
    )
    text: str = Field(..., description="Extracted raw text content of the block")
    source_type: str = Field(
        ...,
        description="Source format origin: pdf_page, docx_paragraph, docx_table, pptx_slide, pptx_shape, pptx_table",
    )

    # Provenance tracking (format-specific coordinates)
    page_number: Optional[int] = Field(None, ge=1, description="1-based page number for PDF documents")
    slide_number: Optional[int] = Field(None, ge=1, description="1-based slide number for PPTX presentations")

    # Structural hierarchy context
    section_title: Optional[str] = Field(None, description="Immediate heading or section title context")
    section_path: List[str] = Field(
        default_factory=list,
        description="Full hierarchical section path, e.g. ['Machine Learning', 'Supervised', 'Classification']",
    )
    paragraph_index: Optional[int] = Field(None, ge=0, description="Paragraph index in DOCX")
    table_index: Optional[int] = Field(None, ge=0, description="Table index in document")
    row_index: Optional[int] = Field(None, ge=0, description="Row index if table row")

    source_start_offset: Optional[int] = Field(None, ge=0, description="Character start offset in source text")
    source_end_offset: Optional[int] = Field(None, ge=0, description="Character end offset in source text")

    warnings: List[str] = Field(default_factory=list, description="Warnings or unsupported elements in this block")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Format-specific metadata dictionary")


class ExtractedDocument(BaseModel):
    """Aggregate extracted document representation containing ordered blocks and provenance."""

    model_config = ConfigDict(frozen=True)

    document_id: Optional[uuid.UUID] = Field(None, description="Document UUID")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="Detected format extension: .pdf, .docx, .pptx")

    total_pages: Optional[int] = Field(None, ge=0, description="Total physical pages (PDF only)")
    total_slides: Optional[int] = Field(None, ge=0, description="Total slides (PPTX only)")

    blocks: List[ExtractedBlock] = Field(default_factory=list, description="Ordered extracted content blocks")

    parser_name: str = Field(..., description="Name of the extractor parser")
    parser_version: str = Field(..., description="Version of the extractor parser")
    extracted_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 extraction timestamp",
    )
    total_characters: int = Field(default=0, ge=0, description="Total character count across all blocks")
    warnings: List[Dict[str, Any]] = Field(default_factory=list, description="Document-level warnings")
