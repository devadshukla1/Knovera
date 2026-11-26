"""DOCX extractor implementation for Knovera Ingestion using python-docx."""

from datetime import datetime, timezone
import io
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid
import zipfile

import docx
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.ingestion.extractors.base import BaseExtractor
from backend.app.ingestion.extractors.exceptions import (
    DOCXEncryptedError,
    ExtractionException,
    InvalidDOCXError,
    NoExtractableTextError,
    ParagraphLimitExceededError,
    PDFTextLimitExceededError,
)
from backend.app.ingestion.schemas.extracted_document import (
    ExtractedBlock,
    ExtractedDocument,
)

logger = get_logger("knovera.ingestion.docx")


class DOCXExtractor(BaseExtractor):
    """Extracts structured text, headings hierarchy, and tables from DOCX files."""

    def __init__(
        self,
        max_paragraphs: Optional[int] = None,
        max_text_chars: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.max_paragraphs = max_paragraphs or getattr(settings, "MAX_DOCX_PARAGRAPHS", 10_000)
        self.max_text_chars = max_text_chars or settings.MAX_EXTRACTED_TEXT_CHARS

    def validate_docx_container(self, file_path: Path) -> None:
        """Validates that file is a readable ZIP container containing word/document.xml."""
        if not file_path.is_file():
            raise InvalidDOCXError(f"DOCX file not found: {file_path}")

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                # Check for password/encryption
                for zinfo in zf.infolist():
                    if zinfo.flag_bits & 0x1:
                        raise DOCXEncryptedError(
                            "The uploaded DOCX document is password-protected or encrypted."
                        )

                namelist = zf.namelist()
                # Typical DOCX contains [Content_Types].xml and word/document.xml
                if "word/document.xml" not in namelist and not any(n.startswith("word/") for n in namelist):
                    raise InvalidDOCXError(
                        "File is not a valid DOCX document (missing word/document.xml)."
                    )
        except zipfile.BadZipFile as exc:
            raise InvalidDOCXError(f"Corrupted or invalid DOCX ZIP package: {exc}") from exc
        except DOCXEncryptedError:
            raise
        except Exception as exc:
            raise InvalidDOCXError(f"Unable to inspect DOCX container: {exc}") from exc

    def _format_table(self, table: Table, table_index: int) -> str:
        """Formats a docx Table into a clean markdown/pipe-delimited table string."""
        rows_text: List[str] = []
        for row in table.rows:
            # Clean each cell text and collapse inner newlines
            cells = [re.sub(r"\s+", " ", cell.text.strip()) for cell in row.cells]
            rows_text.append(" | ".join(cells))

        if not rows_text:
            return ""

        # Format header with separator if table has >= 1 row
        formatted = f"Table {table_index + 1}:\n"
        if len(rows_text) >= 1:
            formatted += f"{rows_text[0]}\n"
            # Add separator bar
            col_count = len(table.rows[0].cells)
            formatted += f"{' | '.join(['---'] * col_count)}\n"
            for r in rows_text[1:]:
                formatted += f"{r}\n"
        return formatted.strip()

    def extract_document(
        self,
        file_path: Path,
        document_id: Optional[uuid.UUID] = None,
    ) -> ExtractedDocument:
        """Extracts structured blocks, heading hierarchy, and tables in document reading order."""
        self.validate_docx_container(file_path)

        try:
            doc = docx.Document(str(file_path))
        except Exception as exc:
            logger.warning("python-docx failed to open %s: %s", file_path.name, exc)
            raise InvalidDOCXError(f"Failed to parse DOCX document structure: {exc}") from exc

        blocks: List[ExtractedBlock] = []
        warnings: List[Dict[str, Any]] = []

        # Hierarchy tracking: section_path stack [(level: int, title: str)]
        section_stack: List[tuple[int, str]] = []
        current_section_title: Optional[str] = None

        total_characters = 0
        paragraph_count = 0
        table_count = 0
        block_idx = 0

        try:
            # Iterate through body elements in true document order (paragraphs and tables interleaved)
            for child in doc.element.body.iterchildren():
                if isinstance(child, CT_P):
                    paragraph = Paragraph(child, doc)
                    text = paragraph.text.strip()
                    if not text:
                        continue

                    paragraph_count += 1
                    if paragraph_count > self.max_paragraphs:
                        raise ParagraphLimitExceededError(
                            f"Document exceeds paragraph limit of {self.max_paragraphs}."
                        )

                    style_name = (paragraph.style.name if paragraph.style else "Normal").strip()
                    style_lower = style_name.lower()

                    # Detect heading levels (e.g. "Heading 1", "Heading 2", or "Title")
                    heading_level = None
                    if style_lower == "title":
                        heading_level = 0
                    elif "heading" in style_lower:
                        match = re.search(r"heading\s*(\d+)", style_lower)
                        if match:
                            heading_level = int(match.group(1))

                    if heading_level is not None:
                        # Pop deeper or equal levels from stack
                        while section_stack and section_stack[-1][0] >= heading_level:
                            section_stack.pop()
                        section_stack.append((heading_level, text))
                        current_section_title = text
                        current_path = [title for _, title in section_stack]

                        block = ExtractedBlock(
                            block_index=block_idx,
                            block_type="heading",
                            text=text,
                            source_type="docx_paragraph",
                            page_number=None,
                            slide_number=None,
                            section_title=current_section_title,
                            section_path=current_path,
                            paragraph_index=paragraph_count,
                            warnings=[],
                            metadata={"style": style_name, "heading_level": heading_level},
                        )
                    else:
                        current_path = [title for _, title in section_stack]
                        block_type = "list_item" if ("list" in style_lower or "bullet" in style_lower) else "paragraph"

                        block = ExtractedBlock(
                            block_index=block_idx,
                            block_type=block_type,
                            text=text,
                            source_type="docx_paragraph",
                            page_number=None,
                            slide_number=None,
                            section_title=current_section_title,
                            section_path=current_path,
                            paragraph_index=paragraph_count,
                            warnings=[],
                            metadata={"style": style_name},
                        )

                    blocks.append(block)
                    block_idx += 1
                    total_characters += len(text)

                elif isinstance(child, CT_Tbl):
                    table = Table(child, doc)
                    table_count += 1
                    table_text = self._format_table(table, table_index=table_count - 1)
                    if not table_text:
                        continue

                    current_path = [title for _, title in section_stack]
                    block = ExtractedBlock(
                        block_index=block_idx,
                        block_type="table",
                        text=table_text,
                        source_type="docx_table",
                        page_number=None,
                        slide_number=None,
                        section_title=current_section_title,
                        section_path=current_path,
                        table_index=table_count,
                        warnings=[],
                        metadata={"row_count": len(table.rows), "col_count": len(table.columns)},
                    )
                    blocks.append(block)
                    block_idx += 1
                    total_characters += len(table_text)

                if total_characters > self.max_text_chars:
                    raise PDFTextLimitExceededError(
                        f"Extracted characters ({total_characters}) exceed limit of {self.max_text_chars}."
                    )

            if total_characters == 0 or len(blocks) == 0:
                raise NoExtractableTextError("No extractable text or content found in DOCX file.")

            now_iso = datetime.now(timezone.utc).isoformat()
            return ExtractedDocument(
                document_id=document_id,
                filename=file_path.name,
                file_type=".docx",
                total_pages=None,
                total_slides=None,
                blocks=blocks,
                parser_name="python-docx",
                parser_version=docx.__version__,
                extracted_at=now_iso,
                total_characters=total_characters,
                warnings=warnings,
            )

        except (
            InvalidDOCXError,
            DOCXEncryptedError,
            ParagraphLimitExceededError,
            PDFTextLimitExceededError,
            NoExtractableTextError,
        ):
            raise
        except Exception as exc:
            logger.exception("Unexpected error during DOCX extraction: %s", exc)
            raise ExtractionException(f"Unexpected error during DOCX extraction: {exc}") from exc
