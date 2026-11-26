"""Unit tests for DOCXExtractor (Phase 2 Chunk C2.3)."""

from pathlib import Path
import docx
import pytest

from backend.app.ingestion.extractors.docx_extractor import DOCXExtractor
from backend.app.ingestion.extractors.exceptions import (
    DOCXEncryptedError,
    ExtractionException,
    InvalidDOCXError,
    NoExtractableTextError,
    ParagraphLimitExceededError,
)


def create_test_docx(
    file_path: Path,
    headings: list[tuple[int, str]] | None = None,
    paragraphs: list[str] | None = None,
    table_data: list[list[str]] | None = None,
) -> Path:
    """Helper to programmatically generate DOCX files for testing."""
    doc = docx.Document()

    if headings:
        for level, text in headings:
            doc.add_heading(text, level=level)

    if paragraphs:
        for p in paragraphs:
            doc.add_paragraph(p)

    if table_data:
        rows = len(table_data)
        cols = len(table_data[0]) if rows > 0 else 0
        table = doc.add_table(rows=rows, cols=cols)
        for r_idx, row in enumerate(table_data):
            for c_idx, val in enumerate(row):
                table.cell(r_idx, c_idx).text = val

    doc.save(str(file_path))
    return file_path


def test_docx_single_paragraph(tmp_path: Path):
    docx_path = create_test_docx(
        tmp_path / "single.docx",
        paragraphs=["Knowledge intelligence platform with unified document understanding."],
    )
    extractor = DOCXExtractor()
    result = extractor.extract_document(docx_path)

    assert result.file_type == ".docx"
    assert result.total_pages is None
    assert result.total_slides is None
    assert len(result.blocks) == 1
    assert result.blocks[0].block_type == "paragraph"
    assert "Knowledge intelligence" in result.blocks[0].text
    assert result.blocks[0].source_type == "docx_paragraph"


def test_docx_heading_hierarchy_and_section_path(tmp_path: Path):
    doc = docx.Document()
    doc.add_heading("Machine Learning", level=1)
    doc.add_paragraph("Machine learning is a subset of artificial intelligence.")
    doc.add_heading("Supervised Learning", level=2)
    doc.add_paragraph("Supervised learning uses labelled pairs.")
    doc.add_heading("Classification", level=3)
    doc.add_paragraph("Classification predicts discrete class labels.")

    file_path = tmp_path / "hierarchy.docx"
    doc.save(str(file_path))

    extractor = DOCXExtractor()
    result = extractor.extract_document(file_path)

    assert len(result.blocks) == 6
    # Check heading levels and section paths
    p3 = [b for b in result.blocks if "discrete class labels" in b.text][0]
    assert p3.section_title == "Classification"
    assert p3.section_path == ["Machine Learning", "Supervised Learning", "Classification"]


def test_docx_table_extraction(tmp_path: Path):
    table = [
        ["Model", "Precision", "Recall"],
        ["SVM", "0.92", "0.89"],
        ["Random Forest", "0.95", "0.94"],
    ]
    file_path = create_test_docx(tmp_path / "table.docx", table_data=table)

    extractor = DOCXExtractor()
    result = extractor.extract_document(file_path)

    table_blocks = [b for b in result.blocks if b.block_type == "table"]
    assert len(table_blocks) == 1
    table_text = table_blocks[0].text
    assert "Model | Precision | Recall" in table_text
    assert "SVM | 0.92 | 0.89" in table_text
    assert "Random Forest | 0.95 | 0.94" in table_text


def test_docx_unicode_and_scientific_text(tmp_path: Path):
    text = "Résumés & naïve Bayes with parameters: α = 0.05, β ≤ 1.0, ∑ (x_i - μ)^2, and Price: €150 / $165."
    file_path = create_test_docx(tmp_path / "unicode.docx", paragraphs=[text])

    extractor = DOCXExtractor()
    result = extractor.extract_document(file_path)

    assert len(result.blocks) == 1
    assert "α = 0.05" in result.blocks[0].text
    assert "∑" in result.blocks[0].text
    assert "€150" in result.blocks[0].text


def test_docx_empty_file_raises_no_text(tmp_path: Path):
    doc = docx.Document()
    file_path = tmp_path / "empty.docx"
    doc.save(str(file_path))

    extractor = DOCXExtractor()
    with pytest.raises(NoExtractableTextError):
        extractor.extract_document(file_path)


def test_docx_corrupted_file_raises_invalid(tmp_path: Path):
    corrupt_path = tmp_path / "corrupt.docx"
    corrupt_path.write_bytes(b"PK\x03\x04 not a real docx zip structure at all")

    extractor = DOCXExtractor()
    with pytest.raises(InvalidDOCXError):
        extractor.extract_document(corrupt_path)


def test_docx_paragraph_limit_exceeded(tmp_path: Path):
    paragraphs = [f"Paragraph line {i}" for i in range(15)]
    file_path = create_test_docx(tmp_path / "limit.docx", paragraphs=paragraphs)

    extractor = DOCXExtractor(max_paragraphs=10)
    with pytest.raises(ParagraphLimitExceededError):
        extractor.extract_document(file_path)
