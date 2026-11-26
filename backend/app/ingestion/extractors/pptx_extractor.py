"""PPTX extractor implementation for Knovera Ingestion using python-pptx."""

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid
import zipfile

import pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.shapes.group import GroupShape

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.ingestion.extractors.base import BaseExtractor
from backend.app.ingestion.extractors.exceptions import (
    ExtractionException,
    InvalidPPTXError,
    NoExtractableTextError,
    PDFTextLimitExceededError,
    PPTXEncryptedError,
    SlideLimitExceededError,
)
from backend.app.ingestion.schemas.extracted_document import (
    ExtractedBlock,
    ExtractedDocument,
)

logger = get_logger("knovera.ingestion.pptx")


class PPTXExtractor(BaseExtractor):
    """Extracts structured text, titles, bullet lists, and tables from PPTX slides in reading order."""

    def __init__(
        self,
        max_slides: Optional[int] = None,
        max_text_chars: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.max_slides = max_slides or getattr(settings, "MAX_PPTX_SLIDES", 500)
        self.max_text_chars = max_text_chars or settings.MAX_EXTRACTED_TEXT_CHARS

    def validate_pptx_container(self, file_path: Path) -> None:
        """Validates that file is a readable ZIP container containing ppt/presentation.xml."""
        if not file_path.is_file():
            raise InvalidPPTXError(f"PPTX file not found: {file_path}")

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                for zinfo in zf.infolist():
                    if zinfo.flag_bits & 0x1:
                        raise PPTXEncryptedError(
                            "The uploaded PPTX presentation is password-protected or encrypted."
                        )

                namelist = zf.namelist()
                if "ppt/presentation.xml" not in namelist and not any(n.startswith("ppt/") for n in namelist):
                    raise InvalidPPTXError(
                        "File is not a valid PPTX presentation (missing ppt/presentation.xml)."
                    )
        except zipfile.BadZipFile as exc:
            raise InvalidPPTXError(f"Corrupted or invalid PPTX ZIP package: {exc}") from exc
        except PPTXEncryptedError:
            raise
        except Exception as exc:
            raise InvalidPPTXError(f"Unable to inspect PPTX container: {exc}") from exc

    def _collect_shapes(self, shapes) -> List[Any]:
        """Recursively flattens shapes, expanding group shapes."""
        flattened = []
        for shape in shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                flattened.extend(self._collect_shapes(shape.shapes))
            else:
                flattened.append(shape)
        return flattened

    def _format_table(self, table, table_index: int, slide_number: int) -> str:
        """Formats a PPTX table into markdown/pipe-delimited text."""
        rows_text: List[str] = []
        for row in table.rows:
            cells = [re.sub(r"\s+", " ", cell.text.strip()) for cell in row.cells]
            rows_text.append(" | ".join(cells))

        if not rows_text:
            return ""

        formatted = f"Slide {slide_number} Table {table_index + 1}:\n"
        if len(rows_text) >= 1:
            formatted += f"{rows_text[0]}\n"
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
        """Extracts structured slide blocks, titles, and tables from PPTX slides."""
        self.validate_pptx_container(file_path)

        try:
            prs = pptx.Presentation(str(file_path))
        except Exception as exc:
            logger.warning("python-pptx failed to open %s: %s", file_path.name, exc)
            raise InvalidPPTXError(f"Failed to parse PPTX presentation structure: {exc}") from exc

        slide_count = len(prs.slides)
        if slide_count == 0:
            raise InvalidPPTXError("PPTX presentation contains 0 slides.")

        if slide_count > self.max_slides:
            raise SlideLimitExceededError(
                f"Presentation contains {slide_count} slides, which exceeds limit of {self.max_slides}."
            )

        blocks: List[ExtractedBlock] = []
        warnings: List[Dict[str, Any]] = []
        total_characters = 0
        block_idx = 0

        try:
            for slide_idx, slide in enumerate(prs.slides):
                slide_number = slide_idx + 1  # 1-based indexing

                # Identify slide title if present
                slide_title: Optional[str] = None
                try:
                    if slide.shapes.title and slide.shapes.title.text.strip():
                        slide_title = slide.shapes.title.text.strip()
                except Exception:
                    pass

                # Collect and sort shapes in geometric reading order: top-to-bottom, left-to-right
                raw_shapes = self._collect_shapes(slide.shapes)
                ordered_shapes = sorted(
                    raw_shapes,
                    key=lambda s: (getattr(s, "top", 0) or 0, getattr(s, "left", 0) or 0),
                )

                table_idx_on_slide = 0

                for shape in ordered_shapes:
                    # 1. Handle Tables
                    if shape.has_table:
                        table_text = self._format_table(
                            shape.table,
                            table_index=table_idx_on_slide,
                            slide_number=slide_number,
                        )
                        table_idx_on_slide += 1
                        if table_text:
                            block = ExtractedBlock(
                                block_index=block_idx,
                                block_type="table",
                                text=table_text,
                                source_type="pptx_table",
                                page_number=None,
                                slide_number=slide_number,
                                section_title=slide_title,
                                section_path=[slide_title] if slide_title else [f"Slide {slide_number}"],
                                table_index=table_idx_on_slide,
                                warnings=[],
                                metadata={
                                    "slide_number": slide_number,
                                    "row_count": len(shape.table.rows),
                                    "col_count": len(shape.table.columns),
                                },
                            )
                            blocks.append(block)
                            block_idx += 1
                            total_characters += len(table_text)

                    # 2. Handle Text Boxes & Placeholders
                    elif shape.has_text_frame:
                        for paragraph in shape.text_frame.paragraphs:
                            p_text = paragraph.text.strip()
                            if not p_text:
                                continue

                            # Check if this shape is the title shape
                            is_title = shape == getattr(slide.shapes, "title", None)
                            block_type = "slide_title" if is_title else "shape_text"

                            # Bullet prefix if indent level > 0
                            bullet_prefix = "- " if paragraph.level and paragraph.level > 0 else ""
                            full_text = f"{bullet_prefix}{p_text}" if bullet_prefix and not p_text.startswith("-") else p_text

                            block = ExtractedBlock(
                                block_index=block_idx,
                                block_type=block_type,
                                text=full_text,
                                source_type="pptx_shape",
                                page_number=None,
                                slide_number=slide_number,
                                section_title=slide_title,
                                section_path=[slide_title] if slide_title else [f"Slide {slide_number}"],
                                warnings=[],
                                metadata={
                                    "slide_number": slide_number,
                                    "level": paragraph.level,
                                    "is_title": is_title,
                                },
                            )
                            blocks.append(block)
                            block_idx += 1
                            total_characters += len(full_text)

                    if total_characters > self.max_text_chars:
                        raise PDFTextLimitExceededError(
                            f"Extracted characters ({total_characters}) exceed limit of {self.max_text_chars}."
                        )

            if total_characters == 0 or len(blocks) == 0:
                raise NoExtractableTextError("No extractable text or content found in PPTX presentation.")

            now_iso = datetime.now(timezone.utc).isoformat()
            return ExtractedDocument(
                document_id=document_id,
                filename=file_path.name,
                file_type=".pptx",
                total_pages=None,
                total_slides=slide_count,
                blocks=blocks,
                parser_name="python-pptx",
                parser_version=pptx.__version__,
                extracted_at=now_iso,
                total_characters=total_characters,
                warnings=warnings,
            )

        except (
            InvalidPPTXError,
            PPTXEncryptedError,
            SlideLimitExceededError,
            PDFTextLimitExceededError,
            NoExtractableTextError,
        ):
            raise
        except Exception as exc:
            logger.exception("Unexpected error during PPTX extraction: %s", exc)
            raise ExtractionException(f"Unexpected error during PPTX extraction: {exc}") from exc
