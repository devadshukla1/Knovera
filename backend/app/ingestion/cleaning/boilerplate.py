"""Conservative repeated header, footer, and institutional noise detection for Knovera."""

from collections import Counter
import re
from typing import List, Set, Tuple

from backend.app.ingestion.schemas.extracted_document import ExtractedBlock

# Known patterns for institutional stamps, slide watermarks, lecture numbers, and course codes
INSTITUTIONAL_NOISE_PATTERNS = [
    re.compile(r"(?i)\b(?:dept\.?|department\s+of)\s+cse\s*&\s*it\b"),
    re.compile(r"(?i)\bjiit\b"),
    re.compile(r"(?i)\bnoida\b"),
    re.compile(r"(?i)\bjaypee\s+institute\b"),
    re.compile(r"(?i)\blecture\s*[-–—:]\s*\d+\b"),
    re.compile(r"(?i)\b\d{1,2}[A-Z]{1,4}\d{1,4}[A-Z0-9]*\b"),  # e.g., 9M12CS112
    re.compile(r"(?i).*metaheuristics\s+in\s+modell?ing\s+and\s+optimization.*"),
    re.compile(r"(?i)^dr\.?\s+[A-Z][a-z]+.*"),
    re.compile(r"(?i)^(?:slide|page)\s+\d+(?:\s*(?:of|/)\s*\d+)?$"),
    re.compile(r"(?i).*of\s+cse\s*&\s*it\s*,\s*jiit\s*,\s*noida.*"),
    re.compile(r"(?i).*\[\d+\]\s*•.*"),
]


def is_noise_line(text: str) -> bool:
    """Checks whether a single line is an institutional watermark, course code, or slide header/footer."""
    clean = text.strip()
    if not clean:
        return False
    for pat in INSTITUTIONAL_NOISE_PATTERNS:
        if pat.search(clean):
            return True
    return False


def clean_text_of_noise(text: str) -> str:
    """Strips institutional header lines, course codes, and bullet noise fragments."""
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        if is_noise_line(line):
            continue
        # Also clean out leading noisy fragments like 'of CSE&IT, JIIT, NOIDA' at line start
        stripped_line = re.sub(r"(?i)^of\s+cse\s*&\s*it\s*,\s*jiit\s*,\s*noida\s*", "", line).strip()
        stripped_line = re.sub(r"(?i)^lecture\s*[-–—:]\s*\d+[^•\n]*", "", stripped_line).strip()
        if stripped_line:
            cleaned_lines.append(stripped_line)
    return "\n".join(cleaned_lines).strip()


class BoilerplateDetector:
    """Detects and filters out repeated header and footer lines and institutional noise across pages/slides."""

    def __init__(self, min_repetitions: int = 2, enabled: bool = True) -> None:
        self.min_repetitions = min_repetitions
        self.enabled = enabled

    def detect_repeated_lines(self, blocks: List[ExtractedBlock]) -> Set[str]:
        """Finds short text lines that appear identically across at least min_repetitions pages/slides."""
        page_lines: dict[int, list[str]] = {}

        for block in blocks:
            page_id = block.page_number or block.slide_number
            if page_id is None:
                continue

            lines = [line.strip() for line in block.text.split("\n") if line.strip()]
            if not lines:
                continue

            if page_id not in page_lines:
                page_lines[page_id] = []

            # Check candidate headers (first 3 lines) or footers (last 3 lines)
            if len(lines) <= 3:
                page_lines[page_id].extend(lines)
            else:
                page_lines[page_id].extend(lines[:3])
                page_lines[page_id].extend(lines[-3:])

        if len(page_lines) < self.min_repetitions:
            return set()

        line_page_presence: dict[str, set[int]] = {}
        for page_id, candidates in page_lines.items():
            for line in set(candidates):
                if 3 <= len(line) <= 100:
                    line_page_presence.setdefault(line, set()).add(page_id)

        repeated: Set[str] = {
            line for line, pages in line_page_presence.items() if len(pages) >= self.min_repetitions
        }
        return repeated

    def filter_boilerplate(
        self, blocks: List[ExtractedBlock]
    ) -> Tuple[List[ExtractedBlock], int]:
        """If enabled, removes detected boilerplate and institutional noise lines; otherwise passes through untouched."""
        if not self.enabled:
            return blocks, 0

        repeated_lines = self.detect_repeated_lines(blocks)

        filtered_blocks: List[ExtractedBlock] = []
        removed_count = 0

        for block in blocks:
            lines = block.text.split("\n")
            surviving_lines = []
            for line in lines:
                clean_line = line.strip()
                if clean_line in repeated_lines or is_noise_line(clean_line):
                    removed_count += 1
                else:
                    # Strip any inline noise prefix
                    clean_prefix = re.sub(r"(?i)^of\s+cse\s*&\s*it\s*,\s*jiit\s*,\s*noida\s*", "", clean_line).strip()
                    if clean_prefix:
                        surviving_lines.append(clean_prefix)
                    else:
                        removed_count += 1

            new_text = "\n".join(surviving_lines).strip()
            if new_text and len(new_text) >= 10:
                filtered_blocks.append(
                    ExtractedBlock(
                        block_index=block.block_index,
                        block_type=block.block_type,
                        text=new_text,
                        source_type=block.source_type,
                        page_number=block.page_number,
                        slide_number=block.slide_number,
                        section_title=block.section_title,
                        section_path=block.section_path,
                        paragraph_index=block.paragraph_index,
                        table_index=block.table_index,
                        row_index=block.row_index,
                        source_start_offset=block.source_start_offset,
                        source_end_offset=block.source_end_offset,
                        warnings=block.warnings,
                        metadata=block.metadata,
                    )
                )

        return filtered_blocks, removed_count
