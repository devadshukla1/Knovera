"""Unit tests for PPTXExtractor (Phase 2 Chunk C2.3)."""

from pathlib import Path
import pptx
from pptx.util import Inches, Pt
import pytest

from backend.app.ingestion.extractors.exceptions import (
    ExtractionException,
    InvalidPPTXError,
    NoExtractableTextError,
    PPTXEncryptedError,
    SlideLimitExceededError,
)
from backend.app.ingestion.extractors.pptx_extractor import PPTXExtractor


def create_test_pptx(
    file_path: Path,
    slides_data: list[dict] | None = None,
) -> Path:
    """Helper to programmatically generate PPTX presentations for testing."""
    prs = pptx.Presentation()
    # Use blank slide layout (index 6 in default template)
    blank_layout = prs.slide_layouts[6]

    if slides_data:
        for s_data in slides_data:
            slide = prs.slides.add_slide(blank_layout)

            # Title
            title_text = s_data.get("title")
            if title_text:
                txBox = slide.shapes.add_textbox(Inches(1), Inches(0.5), Inches(8), Inches(1))
                tf = txBox.text_frame
                tf.text = title_text

            # Bullet points / Paragraphs
            bullets = s_data.get("bullets", [])
            if bullets:
                txBox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(4))
                tf = txBox.text_frame
                for i, b_text in enumerate(bullets):
                    p = tf.add_paragraph() if i > 0 else tf.paragraphs[0]
                    p.text = b_text
                    p.level = 1 if b_text.startswith("  ") else 0

            # Table
            table_data = s_data.get("table")
            if table_data:
                rows = len(table_data)
                cols = len(table_data[0]) if rows > 0 else 0
                table_shape = slide.shapes.add_table(rows, cols, Inches(1), Inches(3), Inches(8), Inches(2))
                for r_idx, row in enumerate(table_data):
                    for c_idx, val in enumerate(row):
                        table_shape.table.cell(r_idx, c_idx).text = val

    prs.save(str(file_path))
    return file_path


def test_pptx_single_slide_with_title_and_bullets(tmp_path: Path):
    file_path = create_test_pptx(
        tmp_path / "single.pptx",
        slides_data=[
            {
                "title": "Introduction to Knovera",
                "bullets": ["Knowledge Intelligence", "Grounded Citations", "Adaptive Learning"],
            }
        ],
    )

    extractor = PPTXExtractor()
    result = extractor.extract_document(file_path)

    assert result.file_type == ".pptx"
    assert result.total_slides == 1
    assert result.total_pages is None
    assert len(result.blocks) >= 2

    # Check slide number provenance (1-based)
    for b in result.blocks:
        assert b.slide_number == 1
        assert b.source_type == "pptx_shape"

    text_concat = " ".join(b.text for b in result.blocks)
    assert "Introduction to Knovera" in text_concat
    assert "Grounded Citations" in text_concat


def test_pptx_multiple_slides_preserves_slide_order(tmp_path: Path):
    file_path = create_test_pptx(
        tmp_path / "multi.pptx",
        slides_data=[
            {"title": "Slide 1 Overview", "bullets": ["First point"]},
            {"title": "Slide 2 Deep Dive", "bullets": ["Second point"]},
            {"title": "Slide 3 Conclusion", "bullets": ["Final takeaways"]},
        ],
    )

    extractor = PPTXExtractor()
    result = extractor.extract_document(file_path)

    assert result.total_slides == 3
    slide_numbers = [b.slide_number for b in result.blocks]
    assert 1 in slide_numbers
    assert 2 in slide_numbers
    assert 3 in slide_numbers
    # Check monotonicity
    assert slide_numbers == sorted(slide_numbers)


def test_pptx_table_extraction(tmp_path: Path):
    table = [
        ["Phase", "Component", "Accuracy"],
        ["Phase 1", "IAM Shell", "100%"],
        ["Phase 2", "Ingestion", "100%"],
    ]
    file_path = create_test_pptx(
        tmp_path / "table.pptx",
        slides_data=[{"title": "Architecture Roadmap", "table": table}],
    )

    extractor = PPTXExtractor()
    result = extractor.extract_document(file_path)

    table_blocks = [b for b in result.blocks if b.block_type == "table"]
    assert len(table_blocks) == 1
    assert "Phase | Component | Accuracy" in table_blocks[0].text
    assert table_blocks[0].slide_number == 1
    assert table_blocks[0].source_type == "pptx_table"


def test_pptx_unicode_symbols(tmp_path: Path):
    file_path = create_test_pptx(
        tmp_path / "unicode.pptx",
        slides_data=[
            {
                "title": "Quantum Mechanics & Math",
                "bullets": ["Schrödinger: iħ ∂ψ/∂t = Ĥψ", "Summation: ∑ x_i ≥ 0", "Angle: θ = π / 2"],
            }
        ],
    )

    extractor = PPTXExtractor()
    result = extractor.extract_document(file_path)

    text_concat = " ".join(b.text for b in result.blocks)
    assert "∂ψ/∂t" in text_concat
    assert "∑" in text_concat
    assert "π" in text_concat


def test_pptx_empty_presentation_raises_no_text(tmp_path: Path):
    file_path = create_test_pptx(tmp_path / "empty.pptx", slides_data=[])
    extractor = PPTXExtractor()

    with pytest.raises(InvalidPPTXError):
        extractor.extract_document(file_path)


def test_pptx_slide_limit_exceeded(tmp_path: Path):
    slides = [{"title": f"Slide {i}", "bullets": [f"Point {i}"]} for i in range(15)]
    file_path = create_test_pptx(tmp_path / "oversized.pptx", slides_data=slides)

    extractor = PPTXExtractor(max_slides=10)
    with pytest.raises(SlideLimitExceededError):
        extractor.extract_document(file_path)


def test_pptx_corrupted_file_raises_invalid(tmp_path: Path):
    corrupt_path = tmp_path / "corrupt.pptx"
    corrupt_path.write_bytes(b"PK\x03\x04 not a valid presentation zip container")

    extractor = PPTXExtractor()
    with pytest.raises(InvalidPPTXError):
        extractor.extract_document(corrupt_path)
