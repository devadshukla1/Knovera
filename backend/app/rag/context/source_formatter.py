"""Structured evidence formatting for LLM prompt context (Phase 3 C3.5)."""

from typing import List
from backend.app.rag.context.schemas import ContextSource


class SourceFormatter:
    """Formats context sources with unambiguous provenance markers."""

    def format_single_source(self, source: ContextSource) -> str:
        """Formats an individual source block."""
        header_lines = [f"SOURCE [{source.source_id}]"]
        header_lines.append(f"Document: {source.document_name}")

        location_parts = []
        if source.page_start is not None and source.page_start > 0:
            if source.page_end and source.page_end != source.page_start and source.page_end > 0:
                location_parts.append(f"Pages {source.page_start}–{source.page_end}")
            else:
                location_parts.append(f"Page {source.page_start}")

        if source.slide_number is not None and source.slide_number > 0:
            location_parts.append(f"Slide {source.slide_number}")

        if source.section_title:
            location_parts.append(f"Section: {source.section_title}")

        if location_parts:
            header_lines.append(f"Location: {', '.join(location_parts)}")

        truncation_notice = " [TRUNCATED DUE TO CONTEXT BUDGET]" if source.is_truncated else ""
        header_lines.append(f"CONTENT{truncation_notice}:")
        header_lines.append(source.content.strip())

        return "\n".join(header_lines)

    def format_all_sources(self, sources: List[ContextSource]) -> str:
        """Concatenates all sources separated by distinct structural dividers."""
        if not sources:
            return "No relevant document evidence retrieved for this query."

        formatted_blocks = [self.format_single_source(s) for s in sources]
        return "\n\n---\n\n".join(formatted_blocks)
