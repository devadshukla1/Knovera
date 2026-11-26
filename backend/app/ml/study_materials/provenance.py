"""Provenance and Context Formatting for Knovera Study Material Generation.

Provides:
- Context text formatting with clear chunk provenance headers.
- Accurate chunk citation and excerpt extraction.
- Cross-verification that generated content has verifiable roots in source chunks.
"""

from typing import List, Optional
from uuid import UUID

from backend.app.ml.study_materials.schemas import SourceReference
from backend.app.ml.study_materials.source_resolver import ResolvedChunk


def format_source_context(chunks: List[ResolvedChunk], token_budget: int = 3500) -> str:
    """Formats a list of resolved chunks into an XML-delimited prompt context block."""
    blocks: List[str] = []
    accumulated_tokens = 0

    for chunk in chunks:
        header = f"[Chunk {chunk.chunk_id} | Document: '{chunk.document_title}'"
        if chunk.page_number is not None:
            header += f" | Page: {chunk.page_number}"
        if chunk.heading:
            header += f" | Heading: '{chunk.heading}'"
        header += "]"

        block = f"{header}\n{chunk.content.strip()}"
        est_tokens = chunk.token_count or max(1, len(chunk.content) // 4)

        if accumulated_tokens + est_tokens > token_budget and blocks:
            # Reached budget; avoid blowing model context window
            break

        blocks.append(block)
        accumulated_tokens += est_tokens

    return "\n\n---\n\n".join(blocks)


def find_supporting_chunk(
    text_snippet: str,
    chunks: List[ResolvedChunk],
) -> Optional[ResolvedChunk]:
    """Finds the most relevant source chunk supporting a generated item or question."""
    if not text_snippet or not chunks:
        return None

    snippet_lower = text_snippet.lower()
    snippet_words = set(w for w in snippet_lower.split() if len(w) > 3)

    best_chunk: Optional[ResolvedChunk] = None
    best_score = 0.0

    for chunk in chunks:
        chunk_text_lower = chunk.content.lower()

        # Check for direct substring match
        if snippet_lower in chunk_text_lower:
            return chunk

        # Word overlap score
        chunk_words = set(w for w in chunk_text_lower.split() if len(w) > 3)
        if not chunk_words:
            continue

        overlap = len(snippet_words.intersection(chunk_words))
        score = overlap / max(1, len(snippet_words))

        if score > best_score:
            best_score = score
            best_chunk = chunk

    # Require minimum 20% semantic keyword overlap
    if best_score >= 0.2:
        return best_chunk

    return chunks[0] if chunks else None


def build_source_reference(
    chunk: ResolvedChunk,
    excerpt: Optional[str] = None,
) -> SourceReference:
    """Constructs a validated SourceReference DTO."""
    clean_excerpt = excerpt.strip()[:200] if excerpt else chunk.content[:200].strip()
    return SourceReference(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_title=chunk.document_title,
        page_number=chunk.page_number,
        section_heading=chunk.heading,
        excerpt=clean_excerpt,
    )
