"""Unit tests for Knovera Query Intent Taxonomy Registry (Phase 5 C5.1)."""

import pytest

from backend.app.ml.query_intent.taxonomy import (
    TAXONOMY_VERSION,
    AuxiliaryQueryAttributes,
    IntentCategory,
    IntentCategoryEnum,
    MULTI_INTENT_PRECEDENCE,
    OPERATIONAL_CATEGORIES,
    TaxonomyRegistry,
)


def test_taxonomy_version() -> None:
    """Verifies that the taxonomy version matches expected semver."""
    assert TaxonomyRegistry.get_version() == "1.0.0"
    assert TAXONOMY_VERSION == "1.0.0"


def test_all_13_categories_exist() -> None:
    """Verifies all 13 canonical categories exist with unique IDs."""
    expected_categories = {
        "factual_lookup",
        "definition",
        "explanation",
        "comparison",
        "summarization",
        "procedural_guidance",
        "analytical_reasoning",
        "information_extraction",
        "source_evidence",
        "recommendation",
        "general_conversation",
        "unsupported_action",
        "ambiguous",
    }
    all_categories = TaxonomyRegistry.list_categories()
    assert len(all_categories) == 13

    category_ids = set(TaxonomyRegistry.list_category_ids())
    assert category_ids == expected_categories
    assert len(category_ids) == 13


def test_category_schema_completeness() -> None:
    """Verifies every category has required descriptive and guidance fields."""
    for category in TaxonomyRegistry.list_categories():
        assert isinstance(category, IntentCategory)
        assert category.id
        assert category.name
        assert len(category.description) > 10
        assert len(category.inclusion_rules) >= 1
        assert len(category.exclusion_rules) >= 1
        assert len(category.positive_examples) >= 3
        assert len(category.borderline_examples) >= 1
        assert len(category.annotation_guidance) > 10


def test_get_category_valid_and_invalid() -> None:
    """Tests category retrieval and rejection of unknown categories."""
    cat = TaxonomyRegistry.get_category("factual_lookup")
    assert cat.id == "factual_lookup"
    assert cat.name == "Factual Lookup"
    assert TaxonomyRegistry.is_valid_category("factual_lookup") is True

    assert TaxonomyRegistry.is_valid_category("non_existent_category") is False
    with pytest.raises(KeyError, match="Unknown intent category"):
        TaxonomyRegistry.get_category("non_existent_category")


def test_multi_intent_precedence_resolution() -> None:
    """Verifies multi-intent precedence ranking and disambiguation logic."""
    # Precedence: source_evidence > comparison > summarization > recommendation > information_extraction >
    # procedural_guidance > analytical_reasoning > definition > explanation > factual_lookup

    # source_evidence vs comparison -> source_evidence wins
    assert (
        TaxonomyRegistry.resolve_multi_intent(["comparison", "source_evidence"])
        == "source_evidence"
    )

    # comparison vs explanation -> comparison wins
    assert (
        TaxonomyRegistry.resolve_multi_intent(["explanation", "comparison"])
        == "comparison"
    )

    # summarization vs factual_lookup -> summarization wins
    assert (
        TaxonomyRegistry.resolve_multi_intent(["factual_lookup", "summarization"])
        == "summarization"
    )

    # Empty candidate list falls back to ambiguous
    assert TaxonomyRegistry.resolve_multi_intent([]) == "ambiguous"

    # Invalid candidate list falls back to ambiguous
    assert TaxonomyRegistry.resolve_multi_intent(["invalid_1", "invalid_2"]) == "ambiguous"


def test_auxiliary_attributes_defaults_and_validation() -> None:
    """Verifies auxiliary query attributes schema and defaults."""
    attrs = AuxiliaryQueryAttributes()
    assert attrs.requires_conversation_context is False
    assert attrs.requires_multi_source_evidence is False
    assert attrs.requests_explicit_citations is False
    assert attrs.contains_ambiguous_reference is False

    custom_attrs = AuxiliaryQueryAttributes(
        requires_conversation_context=True,
        requests_explicit_citations=True,
    )
    assert custom_attrs.requires_conversation_context is True
    assert custom_attrs.requests_explicit_citations is True
    assert custom_attrs.requires_multi_source_evidence is False


def test_taxonomy_export_to_dict() -> None:
    """Verifies full taxonomy serialization to dict matching JSON export."""
    exported = TaxonomyRegistry.to_dict()
    assert exported["version"] == "1.0.0"
    assert exported["category_count"] == 13
    assert len(exported["categories"]) == 13
    assert exported["multi_intent_precedence"] == MULTI_INTENT_PRECEDENCE
    assert exported["operational_categories"] == OPERATIONAL_CATEGORIES
