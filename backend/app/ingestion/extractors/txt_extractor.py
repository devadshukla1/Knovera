"""Plain text and Markdown extractor implementation for Knovera Ingestion."""

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.ingestion.extractors.base import BaseExtractor
from backend.app.ingestion.extractors.exceptions import (
    ExtractionException,
    NoExtractableTextError,
    PDFTextLimitExceededError,
)
from backend.app.ingestion.schemas.extracted_document import (
    ExtractedBlock,
    ExtractedDocument,
)

logger = get_logger("knovera.ingestion.txt")


class TXTExtractor(BaseExtractor):
    """Extracts structured text blocks, headings, lists, and paragraphs from text/markdown files."""

    def __init__(self, max_text_chars: Optional[int] = None) -> None:
        settings = get_settings()
        self.max_text_chars = max_text_chars or settings.MAX_EXTRACTED_TEXT_CHARS

    def _read_file_content(self, file_path: Path) -> str:
        """Reads file text attempting multiple encodings gracefully (UTF-8 with BOM, UTF-8, Latin-1)."""
        raw_bytes = file_path.read_bytes()
        if not raw_bytes:
            raise NoExtractableTextError("Uploaded text file is empty (0 bytes).")

        # Encoding fallback hierarchy
        encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
        content: Optional[str] = None
        for enc in encodings:
            try:
                content = raw_bytes.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if content is None:
            # Final fallback with replacement characters
            content = raw_bytes.decode("utf-8", errors="replace")

        return content

    def extract_document(
        self,
        file_path: Path,
        document_id: Optional[uuid.UUID] = None,
    ) -> ExtractedDocument:
        """Extracts structured blocks and hierarchy from a plain text or Markdown note."""
        path = Path(file_path)
        if not path.is_file():
            raise ExtractionException(f"Text file not found: {path}")

        raw_content = self._read_file_content(path)
        # Normalize newlines
        content = raw_content.replace("\r\n", "\n").replace("\r", "\n")

        # Split into logical paragraphs by double-newline or explicit section breaks
        raw_paragraphs = re.split(r"\n\s*\n", content)

        blocks: List[ExtractedBlock] = []
        section_stack: List[str] = []
        current_section_title: Optional[str] = None
        total_chars = 0
        block_idx = 0
        para_idx = 0

        for para in raw_paragraphs:
            cleaned = para.strip()
            if not cleaned:
                continue

            para_idx += 1
            lines = [ln.strip() for ln in cleaned.split("\n") if ln.strip()]
            if not lines:
                continue

            first_line = lines[0]
            # Detect Markdown headings (# Heading) or short capitalized header lines
            is_md_heading = first_line.startswith("#")
            is_cap_heading = (
                len(lines) == 1
                and len(first_line) < 80
                and (first_line.isupper() or (first_line.endswith(":") and not first_line.startswith("-")))
            )

            if is_md_heading or is_cap_heading:
                # Heading block
                heading_level = 1
                if is_md_heading:
                    m = re.match(r"^(#+)\s*(.*)", first_line)
                    if m:
                        heading_level = len(m.group(1))
                        clean_title = m.group(2).strip()
                    else:
                        clean_title = first_line.lstrip("#").strip()
                else:
                    clean_title = first_line.rstrip(":").strip()

                current_section_title = clean_title
                # Simple stack tracking
                if heading_level <= 1:
                    section_stack = [clean_title]
                else:
                    while len(section_stack) >= heading_level:
                        section_stack.pop()
                    section_stack.append(clean_title)

                block = ExtractedBlock(
                    block_index=block_idx,
                    block_type="heading",
                    text=clean_title,
                    source_type="txt_paragraph",
                    page_number=None,
                    slide_number=None,
                    section_title=current_section_title,
                    section_path=list(section_stack),
                    paragraph_index=para_idx,
                    warnings=[],
                    metadata={"heading_level": heading_level},
                )
                blocks.append(block)
                block_idx += 1
                total_chars += len(clean_title)

                # If there were remaining lines in the same block after the heading
                if len(lines) > 1:
                    sub_text = "\n".join(lines[1:]).strip()
                    if sub_text:
                        sub_block = ExtractedBlock(
                            block_index=block_idx,
                            block_type="paragraph",
                            text=sub_text,
                            source_type="txt_paragraph",
                            page_number=None,
                            slide_number=None,
                            section_title=current_section_title,
                            section_path=list(section_stack),
                            paragraph_index=para_idx,
                            warnings=[],
                            metadata={},
                        )
                        blocks.append(sub_block)
                        block_idx += 1
                        total_chars += len(sub_text)
            else:
                # Check for bullet / list items
                is_list = any(re.match(r"^[\*\-•\d+\.]\s+", ln) for ln in lines)
                block_type = "list_item" if is_list else "paragraph"

                block = ExtractedBlock(
                    block_index=block_idx,
                    block_type=block_type,
                    text=cleaned,
                    source_type="txt_paragraph",
                    page_number=None,
                    slide_number=None,
                    section_title=current_section_title,
                    section_path=list(section_stack),
                    paragraph_index=para_idx,
                    warnings=[],
                    metadata={},
                )
                blocks.append(block)
                block_idx += 1
                total_chars += len(cleaned)

            if total_chars > self.max_text_chars:
                raise PDFTextLimitExceededError(
                    f"Extracted characters ({total_chars}) exceed limit of {self.max_text_chars}."
                )

        if total_chars == 0 or len(blocks) == 0:
            raise NoExtractableTextError("No extractable text or content found in text file.")

        now_iso = datetime.now(timezone.utc).isoformat()
        return ExtractedDocument(
            document_id=document_id,
            filename=path.name,
            file_type=path.suffix.lower() or ".txt",
            total_pages=None,
            total_slides=None,
            blocks=blocks,
            parser_name="txt_extractor",
            parser_version="1.0.0",
            extracted_at=now_iso,
            total_characters=total_chars,
            warnings=[],
        )
