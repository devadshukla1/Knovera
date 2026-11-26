"""Unit tests for PyMuPDFExtractor."""

from pathlib import Path
import pytest
import pymupdf

from backend.app.ingestion.extractors.exceptions import (
    InvalidPDFError,
    InvalidPDFSignatureError,
    NoExtractableTextError,
    PDFEncryptedError,
    PDFPageLimitExceededError,
    PDFTextLimitExceededError,
)
from backend.app.ingestion.extractors.pdf_extractor import PyMuPDFExtractor


def create_test_pdf(
    file_path: Path,
    pages_text: list[str],
    encrypt_password: str | None = None,
) -> Path:
    """Helper to generate PDFs programmatically for test cases."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page(width=595, height=842)
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)

    if encrypt_password:
        doc.save(
            str(file_path),
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw=encrypt_password,
            owner_pw=encrypt_password,
        )
    else:
        doc.save(str(file_path))
    doc.close()
    return file_path


def test_single_page_pdf_extraction(tmp_path: Path):
    pdf_path = create_test_pdf(
        tmp_path / "single.pdf",
        ["Hello Knovera Knowledge Intelligence Platform!"],
    )
    extractor = PyMuPDFExtractor()
    result = extractor.extract(pdf_path)

    assert result.page_count == 1
    assert result.extracted_pages == 1
    assert result.empty_pages == 0
    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1
    assert "Knovera Knowledge Intelligence" in result.pages[0].text
    assert result.pages[0].character_count > 0
    assert not result.pages[0].is_empty


def test_multi_page_pdf_with_provenance(tmp_path: Path):
    pdf_path = create_test_pdf(
        tmp_path / "multi.pdf",
        [
            "Page One: Introduction to RAG.",
            "Page Two: Multi-document retrieval with exact page citations.",
            "Page Three: Bayesian Knowledge Tracing.",
        ],
    )
    extractor = PyMuPDFExtractor()
    result = extractor.extract(pdf_path)

    assert result.page_count == 3
    assert result.extracted_pages == 3
    assert result.empty_pages == 0
    assert len(result.pages) == 3

    # Verify 1-based indexing
    assert result.pages[0].page_number == 1
    assert "Page One" in result.pages[0].text
    assert result.pages[1].page_number == 2
    assert "Page Two" in result.pages[1].text
    assert result.pages[2].page_number == 3
    assert "Page Three" in result.pages[2].text


def test_mixed_pdf_with_empty_pages(tmp_path: Path):
    pdf_path = create_test_pdf(
        tmp_path / "mixed.pdf",
        [
            "Page 1 has valid text.",
            "",  # Empty page 2
            "Page 3 has more research text.",
        ],
    )
    extractor = PyMuPDFExtractor()
    result = extractor.extract(pdf_path)

    assert result.page_count == 3
    assert result.extracted_pages == 2
    assert result.empty_pages == 1

    # Page 2 should be flagged as empty with warning
    assert result.pages[1].page_number == 2
    assert result.pages[1].is_empty is True
    assert len(result.pages[1].warnings) == 1
    assert result.pages[1].warnings[0].code == "empty_page"

    # Overall document warnings contains empty page warning
    assert any(w.page_number == 2 for w in result.warnings)


def test_scanned_or_completely_empty_pdf_rejection(tmp_path: Path):
    pdf_path = create_test_pdf(
        tmp_path / "empty.pdf",
        ["", ""],  # 2 blank pages
    )
    extractor = PyMuPDFExtractor()
    with pytest.raises(NoExtractableTextError) as exc_info:
        extractor.extract(pdf_path)
    assert exc_info.value.error_code == "no_extractable_text"


def test_encrypted_pdf_rejection(tmp_path: Path):
    pdf_path = create_test_pdf(
        tmp_path / "encrypted.pdf",
        ["Secret document contents."],
        encrypt_password="secretpassword123",
    )
    extractor = PyMuPDFExtractor()
    with pytest.raises(PDFEncryptedError) as exc_info:
        extractor.extract(pdf_path)
    assert exc_info.value.error_code == "pdf_encrypted"


def test_invalid_signature_rejection(tmp_path: Path):
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"This is just a text file with a .pdf extension.")

    extractor = PyMuPDFExtractor()
    with pytest.raises(InvalidPDFSignatureError) as exc_info:
        extractor.extract(fake_pdf)
    assert exc_info.value.error_code == "invalid_pdf_signature"


def test_corrupted_pdf_rejection(tmp_path: Path):
    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"%PDF-1.4\nCorrupted binary junk \xff\xfe\xaa")

    extractor = PyMuPDFExtractor()
    with pytest.raises(InvalidPDFError) as exc_info:
        extractor.extract(corrupt_pdf)
    assert exc_info.value.error_code == "invalid_pdf"


def test_page_limit_enforcement(tmp_path: Path):
    pdf_path = create_test_pdf(
        tmp_path / "toolarge.pdf",
        [f"Page {i}" for i in range(1, 10)],
    )
    # Configure extractor with max_pages = 5
    extractor = PyMuPDFExtractor(max_pages=5)
    with pytest.raises(PDFPageLimitExceededError) as exc_info:
        extractor.extract(pdf_path)
    assert exc_info.value.error_code == "pdf_page_limit_exceeded"


def test_character_limit_enforcement(tmp_path: Path):
    pdf_path = create_test_pdf(
        tmp_path / "toomanytext.pdf",
        ["A " * 100, "B " * 100],
    )
    # Configure extractor with max_text_chars = 100
    extractor = PyMuPDFExtractor(max_text_chars=100)
    with pytest.raises(PDFTextLimitExceededError) as exc_info:
        extractor.extract(pdf_path)
    assert exc_info.value.error_code == "pdf_text_limit_exceeded"
