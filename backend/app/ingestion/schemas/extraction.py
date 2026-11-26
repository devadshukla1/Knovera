"""Pydantic schemas for document and page extraction results."""

import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExtractionWarning(BaseModel):
    """Warning produced during page or document extraction."""

    model_config = ConfigDict(frozen=True)

    page_number: int
    code: str
    message: str


class PageExtractionResult(BaseModel):
    """Structured extraction output for a single document page (1-based index)."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(..., ge=1, description="1-based page number")
    text: str = Field(..., description="Extracted raw text preserving linebreaks and layout order")
    character_count: int = Field(..., ge=0)
    is_empty: bool = Field(default=False)
    warnings: List[ExtractionWarning] = Field(default_factory=list)


class DocumentExtractionResult(BaseModel):
    """Aggregate extraction output for an entire document."""

    model_config = ConfigDict(frozen=True)

    document_id: Optional[uuid.UUID] = None
    page_count: int = Field(..., ge=0)
    total_characters: int = Field(..., ge=0)
    extracted_pages: int = Field(..., ge=0)
    empty_pages: int = Field(..., ge=0)
    parser_name: str = "PyMuPDF"
    parser_version: str
    extracted_at: str
    ocr_required: bool = False
    warnings: List[ExtractionWarning] = Field(default_factory=list)
    pages: List[PageExtractionResult] = Field(default_factory=list)
