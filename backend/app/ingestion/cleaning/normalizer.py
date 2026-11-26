"""TextNormalizer orchestrator for Knovera Ingestion."""

from datetime import datetime, timezone
from typing import List, Optional

from backend.app.core.config import get_settings
from backend.app.ingestion.cleaning.boilerplate import BoilerplateDetector
from backend.app.ingestion.cleaning.dehyphenation import conservative_dehyphenate
from backend.app.ingestion.cleaning.schemas import (
    CleaningMetadata,
    NormalisedBlock,
    NormalisedDocument,
)
from backend.app.ingestion.cleaning.unicode_norm import normalize_unicode
from backend.app.ingestion.cleaning.whitespace_norm import normalize_whitespace
from backend.app.ingestion.schemas.extracted_document import ExtractedDocument


class TextNormalizer:
    """Deterministic, non-destructive text cleaning and normalisation engine."""

    def __init__(
        self,
        enable_boilerplate_removal: Optional[bool] = None,
        version: str = "v1.0",
    ) -> None:
        settings = get_settings()
        self.enable_boilerplate = (
            enable_boilerplate_removal
            if enable_boilerplate_removal is not None
            else getattr(settings, "ENABLE_BOILERPLATE_REMOVAL", False)
        )
        self.version = getattr(settings, "CLEANING_VERSION", version)
        self.boilerplate_detector = BoilerplateDetector(
            min_repetitions=3,
            enabled=self.enable_boilerplate,
        )

    def normalize_text(self, text: str) -> tuple[str, int, int, int, int]:
        """Runs the pipeline stages on a string: Unicode NFC -> Dehyphenation -> Whitespace.

        Returns:
            tuple: (cleaned_text, control_removed, unicode_changed, dehyphen_count, whitespace_diff)
        """
        # Stage 1: Unicode NFC & Control Character Sanitization
        nfc_text, ctrl_count, uni_changes = normalize_unicode(text)

        # Stage 2: Conservative Line-Break Dehyphenation
        dehyphen_text, dehyphen_count = conservative_dehyphenate(nfc_text)

        # Stage 3: Whitespace & Newline Normalization
        clean_text, ws_diff = normalize_whitespace(dehyphen_text)

        return clean_text, ctrl_count, uni_changes, dehyphen_count, ws_diff

    def normalize_document(self, document: ExtractedDocument) -> NormalisedDocument:
        """Transforms an ExtractedDocument into a NormalisedDocument with detailed telemetry."""
        original_char_count = sum(len(b.text) for b in document.blocks)

        # Step 1: Optional conservative boilerplate filtering
        filtered_blocks, boilerplate_lines_removed = self.boilerplate_detector.filter_boilerplate(
            document.blocks
        )

        total_ctrl_removed = 0
        total_unicode_changes = 0
        total_dehyphen_count = 0
        total_ws_changes = 0

        normalised_blocks: List[NormalisedBlock] = []

        for b in filtered_blocks:
            clean_text, ctrl_count, uni_change, dehyphen_c, ws_change = self.normalize_text(b.text)

            total_ctrl_removed += ctrl_count
            total_unicode_changes += uni_change
            total_dehyphen_count += dehyphen_c
            total_ws_changes += ws_change

            # Only retain non-empty normalised blocks
            if clean_text:
                normalised_blocks.append(
                    NormalisedBlock(
                        block_index=b.block_index,
                        block_type=b.block_type,
                        raw_text=b.text,
                        text=clean_text,
                        source_type=b.source_type,
                        page_number=b.page_number,
                        slide_number=b.slide_number,
                        section_title=b.section_title,
                        section_path=b.section_path,
                        paragraph_index=b.paragraph_index,
                        table_index=b.table_index,
                        row_index=b.row_index,
                        source_start_offset=b.source_start_offset,
                        source_end_offset=b.source_end_offset,
                        warnings=b.warnings,
                        metadata=b.metadata,
                    )
                )

        normalised_char_count = sum(len(b.text) for b in normalised_blocks)

        cleaning_meta = CleaningMetadata(
            original_character_count=original_char_count,
            normalised_character_count=normalised_char_count,
            removed_control_characters=total_ctrl_removed,
            normalised_unicode_characters=total_unicode_changes,
            whitespace_changes=total_ws_changes,
            dehyphenation_count=total_dehyphen_count,
            boilerplate_lines_removed=boilerplate_lines_removed,
            cleaning_version=self.version,
            warnings=[],
        )

        return NormalisedDocument(
            document_id=document.document_id,
            filename=document.filename,
            file_type=document.file_type,
            total_pages=document.total_pages,
            total_slides=document.total_slides,
            blocks=normalised_blocks,
            cleaning_metadata=cleaning_meta,
            parser_name=document.parser_name,
            parser_version=document.parser_version,
            normalised_at=datetime.now(timezone.utc).isoformat(),
        )
