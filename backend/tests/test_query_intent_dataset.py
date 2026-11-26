"""Unit tests for Query Intent Dataset Validator and Schema Invariants (Phase 5 C5.2)."""

import pytest

from backend.app.ml.query_intent.dataset_validator import (
    DatasetValidationReport,
    QueryIntentDatasetValidator,
)
from backend.app.ml.query_intent.taxonomy import TAXONOMY_VERSION


@pytest.fixture
def validator() -> QueryIntentDatasetValidator:
    return QueryIntentDatasetValidator()


@pytest.fixture
def valid_record() -> dict:
    return {
        "example_id": "qi_0001",
        "query_text": "What is BM25 ranking?",
        "intent": "definition",
        "attributes": {
            "requires_conversation_context": False,
            "requires_multi_source_evidence": False,
            "requests_explicit_citations": False,
            "contains_ambiguous_reference": False,
        },
        "source_type": "synthetic_seed",
        "annotation_status": "pending_human_review",
        "taxonomy_version": TAXONOMY_VERSION,
        "split": "train",
    }


def test_valid_record_passes(validator: QueryIntentDatasetValidator, valid_record: dict) -> None:
    """Verifies that a valid record passes validation."""
    report = validator.validate_records([valid_record], require_splits=True)
    assert report.is_valid is True
    assert report.total_examples == 1
    assert report.invalid_record_count == 0
    assert len(report.errors) == 0


def test_duplicate_example_id_detection(
    validator: QueryIntentDatasetValidator, valid_record: dict
) -> None:
    """Verifies that duplicate example_id triggers a validation error."""
    rec2 = dict(valid_record)
    rec2["query_text"] = "Different query text entirely."

    report = validator.validate_records([valid_record, rec2])
    assert report.is_valid is False
    assert any("Duplicate example_id" in err for err in report.errors)


def test_invalid_intent_detection(
    validator: QueryIntentDatasetValidator, valid_record: dict
) -> None:
    """Verifies that unknown intent categories are rejected."""
    bad_rec = dict(valid_record)
    bad_rec["intent"] = "non_existent_intent"

    report = validator.validate_records([bad_rec])
    assert report.is_valid is False
    assert any("invalid intent" in err for err in report.errors)


def test_missing_or_invalid_fields(
    validator: QueryIntentDatasetValidator, valid_record: dict
) -> None:
    """Verifies that missing query text or invalid attributes trigger errors."""
    # Empty query text
    bad_rec1 = dict(valid_record)
    bad_rec1["query_text"] = "   "

    report1 = validator.validate_records([bad_rec1])
    assert report1.is_valid is False
    assert any("missing non-empty 'query_text'" in err for err in report1.errors)

    # Invalid attributes type
    bad_rec2 = dict(valid_record)
    bad_rec2["attributes"] = "not_a_dict"

    report2 = validator.validate_records([bad_rec2])
    assert report2.is_valid is False
    assert any("must be a dictionary" in err for err in report2.errors)


def test_conflicting_labels_detection(validator: QueryIntentDatasetValidator) -> None:
    """Verifies that identical query text assigned different intents triggers a conflict error."""
    rec1 = {
        "example_id": "qi_0001",
        "query_text": "How does gradient descent work?",
        "intent": "explanation",
        "attributes": {
            "requires_conversation_context": False,
            "requires_multi_source_evidence": False,
            "requests_explicit_citations": False,
            "contains_ambiguous_reference": False,
        },
        "source_type": "synthetic_seed",
        "annotation_status": "pending_human_review",
        "taxonomy_version": TAXONOMY_VERSION,
    }
    rec2 = {
        "example_id": "qi_0002",
        "query_text": "how does gradient descent work?",  # case-insensitive match
        "intent": "factual_lookup",  # Conflicting intent!
        "attributes": {
            "requires_conversation_context": False,
            "requires_multi_source_evidence": False,
            "requests_explicit_citations": False,
            "contains_ambiguous_reference": False,
        },
        "source_type": "synthetic_seed",
        "annotation_status": "pending_human_review",
        "taxonomy_version": TAXONOMY_VERSION,
    }

    report = validator.validate_records([rec1, rec2])
    assert report.is_valid is False
    assert report.conflicting_labels_count == 1
    assert any("Conflicting intent labels" in err for err in report.errors)


def test_invalid_source_type_and_status(
    validator: QueryIntentDatasetValidator, valid_record: dict
) -> None:
    """Verifies that invalid source_type or annotation_status are rejected."""
    bad_source = dict(valid_record)
    bad_source["source_type"] = "unauthorized_scrape"
    report1 = validator.validate_records([bad_source])
    assert report1.is_valid is False
    assert any("invalid source_type" in err for err in report1.errors)

    bad_status = dict(valid_record)
    bad_status["annotation_status"] = "random_status"
    report2 = validator.validate_records([bad_status])
    assert report2.is_valid is False
    assert any("invalid annotation_status" in err for err in report2.errors)


def test_split_validation_requirement(
    validator: QueryIntentDatasetValidator, valid_record: dict
) -> None:
    """Verifies split validation rules when require_splits=True."""
    rec_no_split = dict(valid_record)
    del rec_no_split["split"]

    report = validator.validate_records([rec_no_split], require_splits=True)
    assert report.is_valid is False
    assert any("missing required 'split' field" in err for err in report.errors)

    rec_bad_split = dict(valid_record)
    rec_bad_split["split"] = "invalid_split_name"
    report2 = validator.validate_records([rec_bad_split], require_splits=True)
    assert report2.is_valid is False
    assert any("invalid split" in err for err in report2.errors)
