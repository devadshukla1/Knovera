"""Unit tests for TXTExtractor (Text Study Notes)."""

from pathlib import Path
import pytest

from backend.app.ingestion.extractors.txt_extractor import TXTExtractor
from backend.app.ingestion.extractors.exceptions import (
    NoExtractableTextError,
)


def test_txt_extractor_utf8(tmp_path: Path):
    file_path = tmp_path / "sample.txt"
    content = (
        "# Tabu Search\n\n"
        "Tabu search is a metaheuristic optimization technique.\n\n"
        "## Key Ideas\n\n"
        "- Tabu List: memory of recently visited states.\n"
        "- Aspiration criteria: overrides tabu restrictions.\n"
    )
    file_path.write_text(content, encoding="utf-8")

    extractor = TXTExtractor()
    doc = extractor.extract(str(file_path))

    assert doc.total_characters > 0
    assert len(doc.blocks) >= 3
    headings = [b for b in doc.blocks if b.block_type == "heading"]
    assert len(headings) >= 2
    assert "Tabu Search" in headings[0].text
    assert doc.file_type == ".txt"


def test_txt_extractor_utf8_bom(tmp_path: Path):
    file_path = tmp_path / "bom.txt"
    content = "# Notes with BOM\n\nSome study notes encoded with UTF-8 BOM."
    file_path.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))

    extractor = TXTExtractor()
    doc = extractor.extract(str(file_path))

    assert doc.total_characters > 0
    assert not doc.blocks[0].text.startswith("\ufeff")
    assert "Notes with BOM" in doc.blocks[0].text


def test_txt_extractor_latin1(tmp_path: Path):
    file_path = tmp_path / "latin1.txt"
    content = "ADVANCED OPTIMIZATION\n\nResumé of techniques including naïve bayes & tabu search."
    file_path.write_bytes(content.encode("latin-1"))

    extractor = TXTExtractor()
    doc = extractor.extract(str(file_path))

    assert doc.total_characters > 0
    assert len(doc.blocks) >= 2


def test_txt_extractor_empty_raises(tmp_path: Path):
    file_path = tmp_path / "empty.txt"
    file_path.write_text("   \n\n  \t  ", encoding="utf-8")

    extractor = TXTExtractor()
    with pytest.raises(NoExtractableTextError):
        extractor.extract(str(file_path))
