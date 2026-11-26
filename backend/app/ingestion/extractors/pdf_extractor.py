"""PyMuPDF extractor implementation for Knovera Phase 2."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import uuid
import pymupdf

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.ingestion.extractors.base import BaseExtractor
from backend.app.ingestion.extractors.exceptions import (
    ExtractionException,
    InvalidPDFError,
    InvalidPDFSignatureError,
    NoExtractableTextError,
    PDFEncryptedError,
    PDFPageLimitExceededError,
    PDFTextLimitExceededError,
)
from backend.app.ingestion.schemas.extraction import (
    DocumentExtractionResult,
    ExtractionWarning,
    PageExtractionResult,
)
from backend.app.ingestion.schemas.extracted_document import (
    ExtractedBlock,
    ExtractedDocument,
)

logger = get_logger("knovera.ingestion.pdf")


class PyMuPDFExtractor(BaseExtractor):
    """Extracts text page by page from PDF files using PyMuPDF while preserving provenance."""

    def __init__(
        self,
        max_pages: Optional[int] = None,
        max_text_chars: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.max_pages = max_pages or settings.MAX_PDF_PAGES
        self.max_text_chars = max_text_chars or settings.MAX_EXTRACTED_TEXT_CHARS

    def validate_pdf_signature(self, file_path: Path) -> None:
        """Verifies %PDF- magic signature within initial 1024 bytes per PDF standard."""
        try:
            with open(file_path, "rb") as f:
                header = f.read(1024)
            if b"%PDF-" not in header:
                logger.warning("PDF header signature missing in file: %s", file_path)
                raise InvalidPDFSignatureError(
                    "Invalid PDF signature: File does not contain standard %PDF- header."
                )
        except OSError as exc:
            logger.error("Failed to read file for signature validation: %s", exc)
            raise InvalidPDFError(f"Cannot read file for PDF validation: {exc}") from exc

    def extract(
        self,
        file_path: Path,
        document_id: Optional[uuid.UUID] = None,
    ) -> DocumentExtractionResult:
        """Extracts page text and provenance from a validated PDF file."""
        if not file_path.is_file():
            raise InvalidPDFError(f"PDF file not found at path: {file_path}")

        # 1. Validate magic header signature
        self.validate_pdf_signature(file_path)

        doc = None
        try:
            try:
                doc = pymupdf.open(str(file_path))
            except Exception as exc:
                logger.warning("PyMuPDF failed to open %s: %s", file_path.name, exc)
                raise InvalidPDFError(f"Failed to parse PDF structure: {exc}") from exc

            # 2. Check encryption / password protection
            if doc.is_encrypted or doc.needs_pass:
                logger.warning("Encrypted or password-protected PDF rejected: %s", file_path.name)
                raise PDFEncryptedError(
                    "The uploaded PDF is encrypted or password-protected and cannot be parsed."
                )

            page_count = len(doc)
            if page_count == 0:
                raise InvalidPDFError("PDF document has 0 pages.")

            # 3. Check page limit
            if page_count > self.max_pages:
                logger.warning(
                    "PDF page count (%d) exceeds limit (%d): %s",
                    page_count,
                    self.max_pages,
                    file_path.name,
                )
                raise PDFPageLimitExceededError(
                    f"PDF contains {page_count} pages, which exceeds the limit of {self.max_pages} pages."
                )

            # 4. Extract page-by-page sequentially
            pages: List[PageExtractionResult] = []
            doc_warnings: List[ExtractionWarning] = []
            total_characters = 0
            empty_pages = 0

            for page_idx in range(page_count):
                page_number = page_idx + 1  # 1-based indexing
                page = doc.load_page(page_idx)

                # Use layout-sorted text extraction
                page_text = page.get_text("text", sort=True)
                char_count = len(page_text)
                is_empty = char_count == 0 or page_text.strip() == ""

                page_warnings: List[ExtractionWarning] = []
                if is_empty:
                    empty_pages += 1
                    warn = ExtractionWarning(
                        page_number=page_number,
                        code="empty_page",
                        message="No extractable text found on this page.",
                    )
                    page_warnings.append(warn)
                    doc_warnings.append(warn)

                total_characters += char_count
                if total_characters > self.max_text_chars:
                    logger.warning(
                        "Extracted text (%d chars) exceeds limit (%d)",
                        total_characters,
                        self.max_text_chars,
                    )
                    raise PDFTextLimitExceededError(
                        f"Extracted characters ({total_characters}) exceed configured limit of {self.max_text_chars}."
                    )

                pages.append(
                    PageExtractionResult(
                        page_number=page_number,
                        text=page_text,
                        character_count=char_count,
                        is_empty=is_empty,
                        warnings=page_warnings,
                    )
                )

            # 5. Scanned / Empty PDF validation
            if total_characters == 0 or empty_pages == page_count:
                logger.warning("Scanned PDF with 0 extractable text detected: %s", file_path.name)
                raise NoExtractableTextError(
                    "No extractable text found in PDF. Scanned PDFs requiring OCR are not supported in this version."
                )

            extracted_pages = page_count - empty_pages
            now_iso = datetime.now(timezone.utc).isoformat()

            result = DocumentExtractionResult(
                document_id=document_id,
                page_count=page_count,
                total_characters=total_characters,
                extracted_pages=extracted_pages,
                empty_pages=empty_pages,
                parser_name="PyMuPDF",
                parser_version=pymupdf.__version__,
                extracted_at=now_iso,
                ocr_required=False,
                warnings=doc_warnings,
                pages=pages,
            )

            logger.info(
                "Extracted %s: %d pages (%d with text, %d empty), %d characters",
                file_path.name,
                page_count,
                extracted_pages,
                empty_pages,
                total_characters,
            )
            return result

        except (
            InvalidPDFSignatureError,
            InvalidPDFError,
            PDFEncryptedError,
            PDFPageLimitExceededError,
            PDFTextLimitExceededError,
            NoExtractableTextError,
        ):
            raise
        except Exception as exc:
            logger.exception("Unexpected error during PDF extraction: %s", exc)
            raise ExtractionException(f"Unexpected error during PDF extraction: {exc}") from exc
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    def extract_document(
        self,
        file_path: Path,
        document_id: Optional[uuid.UUID] = None,
    ) -> ExtractedDocument:
        """Extracts structured blocks and page provenance into an ExtractedDocument."""
        # Reuse existing robust validation and page extraction
        raw_result = self.extract(file_path, document_id=document_id)

        blocks: List[ExtractedBlock] = []
        block_idx = 0

        # Also open PyMuPDF document to retrieve structural block layout per page
        doc = None
        try:
            doc = pymupdf.open(str(file_path))
            for page_idx in range(len(doc)):
                page_number = page_idx + 1
                page = doc.load_page(page_idx)
                raw_blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)

                page_has_blocks = False
                for b in raw_blocks:
                    if len(b) >= 7 and b[6] == 0:  # block_type 0 is text
                        b_text = b[4].strip()
                        if b_text:
                            page_has_blocks = True
                            blocks.append(
                                ExtractedBlock(
                                    block_index=block_idx,
                                    block_type="paragraph",
                                    text=b_text,
                                    source_type="pdf_page",
                                    page_number=page_number,
                                    slide_number=None,
                                    section_title=None,
                                    section_path=[],
                                    source_start_offset=None,
                                    source_end_offset=None,
                                    warnings=[],
                                    metadata={
                                        "bbox": [round(b[0], 2), round(b[1], 2), round(b[2], 2), round(b[3], 2)],
                                        "pdf_block_no": b[5],
                                    },
                                )
                            )
                            block_idx += 1

                # If no text blocks found via get_text("blocks") but page has text
                if not page_has_blocks and raw_result.pages:
                    for p in raw_result.pages:
                        if p.page_number == page_number and not p.is_empty:
                            blocks.append(
                                ExtractedBlock(
                                    block_index=block_idx,
                                    block_type="page_text",
                                    text=p.text.strip(),
                                    source_type="pdf_page",
                                    page_number=page_number,
                                    slide_number=None,
                                    section_title=None,
                                    section_path=[],
                                    warnings=[w.message for w in p.warnings],
                                    metadata={},
                                )
                            )
                            block_idx += 1
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

        # Build unified ExtractedDocument
        return ExtractedDocument(
            document_id=document_id,
            filename=file_path.name,
            file_type=".pdf",
            total_pages=raw_result.page_count,
            total_slides=None,
            blocks=blocks,
            parser_name="PyMuPDF",
            parser_version=pymupdf.__version__,
            extracted_at=raw_result.extracted_at,
            total_characters=raw_result.total_characters,
            warnings=[w.model_dump() for w in raw_result.warnings],
        )
