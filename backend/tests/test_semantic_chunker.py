"""Unit tests for Structure-Aware Semantic Chunking (Phase 2 Chunk C2.5)."""

from typing import List
import uuid
import pytest

from backend.app.ingestion.chunking.boundary_detector import SentenceBoundaryDetector
from backend.app.ingestion.chunking.semantic_chunker import SemanticChunker
from backend.app.ingestion.chunking.token_counter import EstimateTokenCounter
from backend.app.ingestion.cleaning.schemas import (
    CleaningMetadata,
    NormalisedBlock,
    NormalisedDocument,
)


def make_test_doc(
    blocks: List[NormalisedBlock],
    file_type: str = ".docx",
    doc_id: uuid.UUID | None = None,
) -> NormalisedDocument:
    """Helper to assemble a NormalisedDocument fixture."""
    return NormalisedDocument(
        document_id=doc_id or uuid.uuid4(),
        filename="sample" + file_type,
        file_type=file_type,
        total_pages=None,
        total_slides=None,
        blocks=blocks,
        cleaning_metadata=CleaningMetadata(
            original_character_count=1000,
            normalised_character_count=980,
            cleaning_version="v1.0",
        ),
        parser_name="test-parser",
        parser_version="1.0.0",
    )


def test_sentence_boundary_detector_abbreviations_and_decimals():
    detector = SentenceBoundaryDetector()
    text = (
        "In Section 3.14, Dr. Smith et al. presented an algorithm (e.g. SVM). "
        "The model achieved 98.5% accuracy. Next sentence starts here."
    )
    sentences = detector.split_sentences(text)

    # Must NOT split on "3.14", "Dr.", "et al.", "e.g."
    assert len(sentences) == 3
    assert sentences[0] == "In Section 3.14, Dr. Smith et al. presented an algorithm (e.g. SVM)."
    assert sentences[1] == "The model achieved 98.5% accuracy."
    assert sentences[2] == "Next sentence starts here."


def test_short_document_creates_single_chunk():
    block = NormalisedBlock(
        block_index=0,
        block_type="paragraph",
        raw_text="Knovera is an intelligent research platform.",
        text="Knovera is an intelligent research platform.",
        source_type="docx_paragraph",
        section_title="Intro",
        section_path=["Intro"],
    )
    doc = make_test_doc([block])
    workspace_id = uuid.uuid4()

    chunker = SemanticChunker(target_tokens=500, max_tokens=700)
    chunks, diag = chunker.chunk_document(doc, workspace_id=workspace_id)

    assert len(chunks) == 1
    assert chunks[0].content == "Knovera is an intelligent research platform."
    assert chunks[0].section_title == "Intro"
    assert chunks[0].chunk_index == 0
    assert diag.chunk_count == 1


def test_deterministic_chunk_ids():
    block = NormalisedBlock(
        block_index=0,
        block_type="paragraph",
        raw_text="Deterministic content hash check.",
        text="Deterministic content hash check.",
        source_type="docx_paragraph",
    )
    fixed_doc_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    doc = make_test_doc([block], doc_id=fixed_doc_id)

    chunker = SemanticChunker(chunking_version="semantic-v1")
    chunks_run1, _ = chunker.chunk_document(doc, workspace_id=workspace_id)
    chunks_run2, _ = chunker.chunk_document(doc, workspace_id=workspace_id)

    # Identical UUIDs on retry/reprocessing
    assert chunks_run1[0].id == chunks_run2[0].id
    assert chunks_run1[0].content_hash == chunks_run2[0].content_hash


def test_pptx_slide_boundaries_respected():
    # Blocks belonging to slide 1 and slide 2
    b1 = NormalisedBlock(
        block_index=0,
        block_type="slide_title",
        raw_text="Slide 1 Title",
        text="Slide 1 Title",
        source_type="pptx_shape",
        slide_number=1,
    )
    b2 = NormalisedBlock(
        block_index=1,
        block_type="shape_text",
        raw_text="Slide 1 bullet text",
        text="Slide 1 bullet text",
        source_type="pptx_shape",
        slide_number=1,
    )
    b3 = NormalisedBlock(
        block_index=2,
        block_type="slide_title",
        raw_text="Slide 2 Title",
        text="Slide 2 Title",
        source_type="pptx_shape",
        slide_number=2,
    )
    b4 = NormalisedBlock(
        block_index=3,
        block_type="shape_text",
        raw_text="Slide 2 bullet text",
        text="Slide 2 bullet text",
        source_type="pptx_shape",
        slide_number=2,
    )

    doc = make_test_doc([b1, b2, b3, b4], file_type=".pptx")
    workspace_id = uuid.uuid4()

    chunker = SemanticChunker(target_tokens=500, max_tokens=700)
    chunks, _ = chunker.chunk_document(doc, workspace_id=workspace_id)

    # Slide 1 and Slide 2 should NOT be mashed together into one chunk
    assert len(chunks) == 2
    assert chunks[0].slide_number == 1
    assert "Slide 1 Title" in chunks[0].content
    assert chunks[1].slide_number == 2
    assert "Slide 2 Title" in chunks[1].content


def test_pdf_page_range_tracking():
    # Blocks spanning page 1, 2, and 3
    blocks = [
        NormalisedBlock(
            block_index=i,
            block_type="paragraph",
            raw_text=f"Paragraph {i} on page {page}. Detailed explanation of concepts.",
            text=f"Paragraph {i} on page {page}. Detailed explanation of concepts.",
            source_type="pdf_page",
            page_number=page,
        )
        for i, page in enumerate([1, 1, 2, 2, 3])
    ]
    doc = make_test_doc(blocks, file_type=".pdf")
    workspace_id = uuid.uuid4()

    chunker = SemanticChunker(target_tokens=50, max_tokens=80)
    chunks, _ = chunker.chunk_document(doc, workspace_id=workspace_id)

    assert len(chunks) > 1
    for c in chunks:
        assert c.page_start is not None
        assert c.page_end is not None
        assert c.page_start <= c.page_end


def test_oversized_table_split_at_rows_with_repeated_header():
    # A table with header and 10 large data rows
    table_lines = ["Table 1: Benchmark Results", "Model | Metric A | Metric B", "--- | --- | ---"]
    for i in range(10):
        table_lines.append(f"Model_{i} | Score_{i}_A_value_large_column_text | Score_{i}_B_value_large_column_text")

    table_block = NormalisedBlock(
        block_index=0,
        block_type="table",
        raw_text="\n".join(table_lines),
        text="\n".join(table_lines),
        source_type="docx_table",
        table_index=1,
    )
    doc = make_test_doc([table_block])
    workspace_id = uuid.uuid4()

    # Small max_tokens to force table row splitting
    chunker = SemanticChunker(target_tokens=40, max_tokens=60)
    chunks, _ = chunker.chunk_document(doc, workspace_id=workspace_id)

    assert len(chunks) >= 2
    # Check that each split table chunk preserves header
    for c in chunks:
        assert "Model | Metric A | Metric B" in c.content


def test_sentence_level_splitting_for_huge_paragraph():
    huge_sentences = [
        f"This is detailed sentence number {i} containing comprehensive domain knowledge."
        for i in range(25)
    ]
    huge_paragraph = " ".join(huge_sentences)

    block = NormalisedBlock(
        block_index=0,
        block_type="paragraph",
        raw_text=huge_paragraph,
        text=huge_paragraph,
        source_type="docx_paragraph",
    )
    doc = make_test_doc([block])
    workspace_id = uuid.uuid4()

    chunker = SemanticChunker(target_tokens=60, max_tokens=100)
    chunks, diag = chunker.chunk_document(doc, workspace_id=workspace_id)

    assert len(chunks) > 1
    for c in chunks:
        # Every chunk respects upper bound
        assert c.token_count <= 110  # within reasonable margin
        assert c.content_hash is not None
        assert len(c.source_segments) > 0


def test_overlap_reset_across_unrelated_sections():
    b1 = NormalisedBlock(
        block_index=0,
        block_type="paragraph",
        raw_text="First section discussion. Concluding thoughts on first topic.",
        text="First section discussion. Concluding thoughts on first topic.",
        source_type="docx_paragraph",
        section_title="Chapter 1",
    )
    b2 = NormalisedBlock(
        block_index=1,
        block_type="heading",
        raw_text="Chapter 2: Completely New Area",
        text="Chapter 2: Completely New Area",
        source_type="docx_paragraph",
        section_title="Chapter 2",
    )
    b3 = NormalisedBlock(
        block_index=2,
        block_type="paragraph",
        raw_text="Here begins a totally different subject without overlap.",
        text="Here begins a totally different subject without overlap.",
        source_type="docx_paragraph",
        section_title="Chapter 2",
    )
    doc = make_test_doc([b1, b2, b3])
    workspace_id = uuid.uuid4()

    # Budget that forces flush at heading
    chunker = SemanticChunker(target_tokens=20, max_tokens=40, min_tokens=10, overlap_tokens=15)
    chunks, _ = chunker.chunk_document(doc, workspace_id=workspace_id)

    # Chunk 2 should NOT contain "Concluding thoughts on first topic" because section changed!
    assert len(chunks) >= 2
    assert "Concluding thoughts on first topic" not in chunks[1].content
