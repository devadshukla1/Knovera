"""Unit tests for retrieval dataset integrity validation (Phase 4 C4.7)."""

import pytest

from backend.app.rag.evaluation.validation import (
    DatasetValidationError,
    validate_dataset_integrity,
)


def test_validate_dataset_integrity_success():
    corpus = {
        "c1": {"content": "Authoritative valid chunk content about biology.", "document_filename": "bio.pdf"},
        "c2": {"content": "Second chunk about computer science protocols.", "document_filename": "cs.pdf"},
    }
    queries = [
        {"query_id": "q1", "split": "dev", "query": "What is biology?"},
        {"query_id": "q2", "split": "test", "query": "Explain computer protocols"},
    ]
    qrels = {
        "q1": {"c1": 3, "c2": 0},
        "q2": {"c2": 2},
    }

    report = validate_dataset_integrity(corpus, queries, qrels)
    assert report["valid"] is True
    assert report["corpus_count"] == 2
    assert report["queries_total"] == 2
    assert report["split_counts"] == {"dev": 1, "test": 1}
    assert report["total_judgments"] == 3


def test_validate_dataset_integrity_detects_duplicate_queries():
    corpus = {"c1": {"content": "Valid chunk content for testing."}}
    queries = [
        {"query_id": "q1", "split": "dev", "query": "Query one"},
        {"query_id": "q1", "split": "dev", "query": "Duplicate query one"},
    ]
    qrels = {"q1": {"c1": 3}}

    with pytest.raises(DatasetValidationError) as exc:
        validate_dataset_integrity(corpus, queries, qrels)
    assert "Duplicate query_id detected: 'q1'" in str(exc.value)


def test_validate_dataset_integrity_detects_missing_corpus_reference():
    corpus = {"c1": {"content": "Valid chunk content for testing."}}
    queries = [{"query_id": "q1", "split": "dev", "query": "Query one"}]
    # qrels references c_missing which does not exist in corpus
    qrels = {"q1": {"c_missing": 3}}

    with pytest.raises(DatasetValidationError) as exc:
        validate_dataset_integrity(corpus, queries, qrels)
    assert "references chunk_id 'c_missing' which does not exist in corpus.jsonl" in str(exc.value)


def test_validate_dataset_integrity_detects_invalid_grades_and_splits():
    corpus = {"c1": {"content": "Valid chunk content for testing."}}
    # Invalid split "validation"
    queries = [{"query_id": "q1", "split": "validation", "query": "Query one"}]
    # Invalid grade 5
    qrels = {"q1": {"c1": 5}}

    with pytest.raises(DatasetValidationError) as exc:
        validate_dataset_integrity(corpus, queries, qrels)
    assert "invalid split 'validation'" in str(exc.value)
