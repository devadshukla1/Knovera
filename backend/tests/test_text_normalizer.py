"""Unit tests for Text Normalisation and Cleaning (Phase 2 Chunk C2.4)."""

import uuid
import pytest

from backend.app.ingestion.cleaning.boilerplate import BoilerplateDetector
from backend.app.ingestion.cleaning.dehyphenation import conservative_dehyphenate
from backend.app.ingestion.cleaning.normalizer import TextNormalizer
from backend.app.ingestion.cleaning.unicode_norm import normalize_unicode
from backend.app.ingestion.cleaning.whitespace_norm import normalize_whitespace
from backend.app.ingestion.schemas.extracted_document import (
    ExtractedBlock,
    ExtractedDocument,
)


def test_unicode_nfc_and_control_char_removal():
    # Contains NUL byte (\x00), vertical tab (\x0b), bell (\x07), accented e decomposed (e + \u0301)
    raw = "Knovera\x00 Platform\x07: Re\u0301sume\u0301\x0b and nai\u0308ve text."
    clean, ctrl_count, uni_changes = normalize_unicode(raw)

    assert "\x00" not in clean
    assert "\x07" not in clean
    assert "\x0b" not in clean
    assert ctrl_count == 3
    # Composed NFC Résumé
    assert "Résumé and naïve text." in clean


def test_unicode_preserves_math_greek_and_currency():
    raw = "Equation: ∑_{i=1}^n x_i ≤ ∞, ∫ f(x)dx ≠ 0, α = 0.05, β = 2.5, Cost: €250, $300, ¥5000."
    clean, ctrl_count, _ = normalize_unicode(raw)

    assert ctrl_count == 0
    assert "∑_{i=1}^n" in clean
    assert "≤" in clean
    assert "≠" in clean
    assert "α = 0.05" in clean
    assert "€250" in clean
    assert "$300" in clean


def test_whitespace_and_newline_normalization():
    raw = "Line 1   with    extra    spaces.\r\n\r\n\r\n\r\nLine 2 after quadruple blank lines.\rLine 3."
    clean, diff = normalize_whitespace(raw)

    assert "Line 1 with extra spaces." in clean
    # Maximum 2 newlines (1 blank line between paragraphs)
    assert "\n\n\n" not in clean
    assert "\r" not in clean
    assert "Line 2 after quadruple blank lines.\nLine 3." in clean


def test_whitespace_preserves_table_pipes():
    raw = "Col A | Col B | Col C\n--- | --- | ---\nVal 1 | Val 2 | Val 3"
    clean, _ = normalize_whitespace(raw)
    assert "Col A | Col B | Col C" in clean
    assert "Val 1 | Val 2 | Val 3" in clean


def test_conservative_dehyphenation():
    # Should rejoin split word across newline
    raw = "This is an infor-\nmation retrieval and deep learn-\ning pipeline."
    clean, count = conservative_dehyphenate(raw)

    assert count == 2
    assert "information retrieval" in clean
    assert "deep learning pipeline" in clean


def test_conservative_dehyphenation_preserves_compound_terms():
    # Should keep legitimate hyphenated prefixes
    raw = "A self-\nsupervised and multi-\ndocument model for state-of-the-art results on x-axis."
    clean, count = conservative_dehyphenate(raw)

    assert count == 2
    assert "self-supervised" in clean
    assert "multi-document" in clean
    assert "state-of-the-art" in clean
    assert "x-axis" in clean


def test_preserves_technical_information_and_stops_stemming():
    raw = "The quick brown fox jumps over the lazy dogs. def process_tokens(data: List[int]) -> bool:"
    normalizer = TextNormalizer()
    clean, _, _, _, _ = normalizer.normalize_text(raw)

    # Must NOT remove stop-words (The, over, the)
    assert "The" in clean
    assert "over" in clean
    # Must NOT stem or lowercase
    assert "dogs" in clean
    assert "def process_tokens" in clean
    assert "List[int]" in clean


def test_repeated_boilerplate_detection_and_filtering():
    blocks = [
        ExtractedBlock(
            block_index=i,
            block_type="paragraph",
            text=f"CONFIDENTIAL DRAFT - DO NOT DISTRIBUTE\nPage substantive content for topic {i}.\nFooter copyright 2026",
            source_type="pdf_page",
            page_number=i + 1,
        )
        for i in range(4)
    ]

    detector = BoilerplateDetector(min_repetitions=3, enabled=True)
    repeated = detector.detect_repeated_lines(blocks)
    assert "CONFIDENTIAL DRAFT - DO NOT DISTRIBUTE" in repeated
    assert "Footer copyright 2026" in repeated

    filtered_blocks, removed_count = detector.filter_boilerplate(blocks)
    assert removed_count == 8  # 2 lines across 4 pages
    for b in filtered_blocks:
        assert "CONFIDENTIAL" not in b.text
        assert "Footer copyright" not in b.text
        assert "Page substantive content" in b.text


def test_normalize_document_end_to_end_telemetry():
    raw_doc = ExtractedDocument(
        document_id=uuid.uuid4(),
        filename="test.docx",
        file_type=".docx",
        total_pages=None,
        total_slides=None,
        blocks=[
            ExtractedBlock(
                block_index=0,
                block_type="heading",
                text="  1. Introduction to Machine Learn-\ning  \r\n\r\n",
                source_type="docx_paragraph",
                section_title="Introduction",
            ),
            ExtractedBlock(
                block_index=1,
                block_type="paragraph",
                text="Machine learning uses statistical algo-\nrithms with parameter α ≤ 0.05.\x00",
                source_type="docx_paragraph",
                section_title="Introduction",
            ),
        ],
        parser_name="python-docx",
        parser_version="1.2.0",
        total_characters=150,
    )

    normalizer = TextNormalizer()
    norm_doc = normalizer.normalize_document(raw_doc)

    assert len(norm_doc.blocks) == 2
    assert "Machine Learning" in norm_doc.blocks[0].text
    assert "statistical algorithms" in norm_doc.blocks[1].text
    assert "α ≤ 0.05." in norm_doc.blocks[1].text
    assert "\x00" not in norm_doc.blocks[1].text

    meta = norm_doc.cleaning_metadata
    assert meta.removed_control_characters == 1
    assert meta.dehyphenation_count == 2
    assert meta.original_character_count > meta.normalised_character_count
    assert meta.cleaning_version == "v1.0"
