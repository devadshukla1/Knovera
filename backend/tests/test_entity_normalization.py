"""Unit tests for Knovera Entity Normalisation Service (Phase 7 C7.2)."""

import pytest

from backend.app.ml.knowledge_graph.normalization import (
    EntityNormalizationService,
    PROTECTED_TERMS,
)
from backend.app.ml.knowledge_graph.ontology import ConceptType, EntityType
from backend.app.ml.knowledge_graph.schemas import ExtractedConcept, ExtractedMention


class TestEntityNormalizationService:
    """Tests for entity deduplication, alias mapping, homonym disambiguation, and protected terms."""

    @pytest.fixture
    def service(self):
        return EntityNormalizationService()

    def test_preserves_protected_punctuation(self, service):
        # Must preserve C++, C#, Node.js, TF-IDF, .NET
        terms = ["C++", "c++", "C#", "Node.js", "node.js", "TF-IDF", "tf-idf", ".NET", "BM25"]
        for term in terms:
            canonical = service.normalize_term_string(term)
            assert canonical in PROTECTED_TERMS.values()

    def test_domain_alias_table_resolution(self, service):
        aliases = {
            "ml": "Machine Learning",
            "NLP": "Natural Language Processing",
            "svm": "Support Vector Machine",
            "RRF": "Reciprocal Rank Fusion",
            "bkt": "Bayesian Knowledge Tracing",
            "sgd": "Stochastic Gradient Descent",
            "knn": "K-Nearest Neighbors",
            "pca": "Principal Component Analysis",
        }
        for alias, expected in aliases.items():
            assert service.normalize_term_string(alias) == expected

    def test_normalize_and_deduplicate_merges_aliases(self, service):
        mention1 = ExtractedMention(
            surface_form="SVM",
            start_offset=0,
            end_offset=3,
            chunk_id="chunk-1",
        )
        concept1 = ExtractedConcept(
            name="SVM",
            normalized_name="svm",
            category=ConceptType.ALGORITHM.value,
            mentions=[mention1],
            aliases=["SVM"],
        )

        mention2 = ExtractedMention(
            surface_form="Support Vector Machine",
            start_offset=10,
            end_offset=32,
            chunk_id="chunk-2",
        )
        concept2 = ExtractedConcept(
            name="Support Vector Machine",
            normalized_name="support vector machine",
            category=ConceptType.ALGORITHM.value,
            mentions=[mention2],
            aliases=["Support Vector Machine"],
        )

        nodes = service.normalize_and_deduplicate([concept1, concept2], workspace_id="ws-1")
        assert len(nodes) == 1
        node = nodes[0]
        assert node.name == "Support Vector Machine"
        assert len(node.mentions) == 2
        assert "SVM" in node.aliases or "svm" in [a.lower() for a in node.aliases]

    def test_plural_and_variant_merging(self, service):
        concept1 = ExtractedConcept(
            name="Transformer",
            normalized_name="transformer",
            category=EntityType.MODEL.value,
            mentions=[ExtractedMention(surface_form="Transformer", start_offset=0, end_offset=11, chunk_id="c-1")],
        )
        concept2 = ExtractedConcept(
            name="Transformers",
            normalized_name="transformers",
            category=EntityType.MODEL.value,
            mentions=[ExtractedMention(surface_form="Transformers", start_offset=0, end_offset=12, chunk_id="c-2")],
        )

        nodes = service.normalize_and_deduplicate([concept1, concept2], workspace_id="ws-1")
        assert len(nodes) == 1
        assert nodes[0].name in {"Transformer", "Transformers"}
        assert len(nodes[0].mentions) == 2

    def test_prevent_unsafe_merges(self, service):
        # "C" and "C++" should never be merged
        c_concept = ExtractedConcept(
            name="C",
            normalized_name="c",
            category=EntityType.TECHNOLOGY.value,
            mentions=[ExtractedMention(surface_form="C", start_offset=0, end_offset=1, chunk_id="c-1")],
        )
        cpp_concept = ExtractedConcept(
            name="C++",
            normalized_name="c++",
            category=EntityType.TECHNOLOGY.value,
            mentions=[ExtractedMention(surface_form="C++", start_offset=0, end_offset=3, chunk_id="c-2")],
        )

        nodes = service.normalize_and_deduplicate([c_concept, cpp_concept], workspace_id="ws-1")
        assert len(nodes) == 2

    def test_homonym_disambiguation_by_context(self, service):
        # Apple as company vs apple as fruit
        canonical_comp, cat_comp = service.disambiguate_homonym(
            surface_term="Apple",
            context_text="Apple announced a new iPhone and Mac operating system.",
        )
        assert "Apple Inc." in canonical_comp
        assert cat_comp == EntityType.ORGANIZATION.value

        canonical_fruit, cat_fruit = service.disambiguate_homonym(
            surface_term="Apple",
            context_text="The orchard grows delicious fruit and cider apples.",
        )
        assert "fruit" in canonical_fruit.lower()
