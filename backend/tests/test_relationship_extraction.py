"""Unit tests for Knovera Relationship Extraction Service (Phase 7 C7.3)."""

from unittest.mock import MagicMock
import pytest

from backend.app.ml.knowledge_graph.ontology import ConceptType, EntityType
from backend.app.ml.knowledge_graph.relationship_extraction import RelationshipExtractionService
from backend.app.ml.knowledge_graph.relationships import (
    RelationPredicate,
    get_inverse_predicate,
    is_symmetric_predicate,
    is_valid_predicate,
)
from backend.app.ml.knowledge_graph.schemas import (
    Modality,
    NormalizedNode,
)
from backend.app.ml.knowledge_graph.validation import verify_span


class TestRelationshipOntology:
    """Tests for relation predicate taxonomy, directionality, and symmetry."""

    def test_predicate_validation(self):
        assert is_valid_predicate("uses")
        assert is_valid_predicate("is_a")
        assert is_valid_predicate("proposed_by")
        assert not is_valid_predicate("invalid_predicate_xyz")

    def test_inverse_predicate_mapping(self):
        assert get_inverse_predicate("part_of") == "contains"
        assert get_inverse_predicate("contains") == "part_of"
        assert get_inverse_predicate("proposed_by") == "proposed"

    def test_symmetric_predicates(self):
        assert is_symmetric_predicate("compared_with")
        assert not is_symmetric_predicate("uses")


class TestRelationshipExtractionService:
    """Tests for deterministic extraction, co-occurrence rejection, negation, and modality."""

    @pytest.fixture
    def service(self):
        return RelationshipExtractionService()

    @pytest.fixture
    def sample_nodes(self):
        return [
            NormalizedNode(
                name="BERT",
                normalized_name="bert",
                category=EntityType.MODEL.value,
                aliases=["BERT"],
            ),
            NormalizedNode(
                name="Multi-Head Attention",
                normalized_name="multi head attention",
                category=ConceptType.TECHNICAL_CONCEPT.value,
                aliases=["Multi-Head Attention", "Attention"],
            ),
            NormalizedNode(
                name="ImageNet",
                normalized_name="imagenet",
                category=EntityType.DATASET.value,
                aliases=["ImageNet"],
            ),
            NormalizedNode(
                name="BM25",
                normalized_name="bm25",
                category=ConceptType.ALGORITHM.value,
                aliases=["BM25"],
            ),
            NormalizedNode(
                name="Neural Embeddings",
                normalized_name="neural embeddings",
                category=ConceptType.TECHNICAL_CONCEPT.value,
                aliases=["Neural Embeddings"],
            ),
        ]

    def test_extract_explicit_functional_relationship(self, service, sample_nodes):
        text = "BERT uses Multi-Head Attention for contextual representations."
        chunks = [{"id": "c-1", "content": text}]

        rels = service.extract_relationships(chunks=chunks, nodes=sample_nodes)
        assert len(rels) >= 1
        rel = next(r for r in rels if r.predicate == RelationPredicate.USES.value)
        assert rel.source_node_name == "BERT"
        assert rel.target_node_name == "Multi-Head Attention"
        assert not rel.is_negated
        assert rel.modality == Modality.CERTAIN.value

        # Verify evidence span exact match
        assert len(rel.evidence) >= 1
        ev = rel.evidence[0]
        assert verify_span(text, ev.start_offset, ev.end_offset, ev.evidence_text)

    def test_strict_co_occurrence_rejection(self, service, sample_nodes):
        # Two entities appear together without relational predicate
        text = "During the conference, researchers discussed both BERT and ImageNet in room 101."
        chunks = [{"id": "c-2", "content": text}]

        rels = service.extract_relationships(chunks=chunks, nodes=sample_nodes)
        # Should NOT form a relationship simply because both entities appeared
        assert len(rels) == 0

    def test_negation_detection(self, service, sample_nodes):
        text = "BM25 does not use Neural Embeddings for document scoring."
        chunks = [{"id": "c-3", "content": text}]

        rels = service.extract_relationships(chunks=chunks, nodes=sample_nodes)
        assert len(rels) >= 1
        rel = next(r for r in rels if r.source_node_name == "BM25")
        assert rel.predicate == RelationPredicate.USES.value
        assert rel.is_negated is True

    def test_epistemic_modality(self, service, sample_nodes):
        text = "If BERT uses Multi-Head Attention, performance might improve."
        chunks = [{"id": "c-4", "content": text}]

        rels = service.extract_relationships(chunks=chunks, nodes=sample_nodes)
        assert len(rels) >= 1
        rel = rels[0]
        assert rel.modality == Modality.HYPOTHETICAL.value

    def test_multi_chunk_consolidation(self, service, sample_nodes):
        chunk1 = {"id": "c-10", "content": "BERT uses Multi-Head Attention."}
        chunk2 = {"id": "c-11", "content": "BERT utilizes Multi-Head Attention for transformers."}

        rels = service.extract_relationships(chunks=[chunk1, chunk2], nodes=sample_nodes)
        assert len(rels) == 1
        rel = rels[0]
        # Evidence should be aggregated from both chunks
        assert len(rel.evidence) == 2
        chunk_ids = {e.chunk_id for e in rel.evidence}
        assert chunk_ids == {"c-10", "c-11"}

    def test_llm_assisted_relationship_extraction(self, service, sample_nodes):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = """[
            {
                "source": "BERT",
                "target": "Multi-Head Attention",
                "predicate": "uses",
                "is_negated": false,
                "modality": "certain",
                "evidence_quote": "BERT leverages Multi-Head Attention"
            }
        ]"""
        service.llm_manager = mock_llm

        text = "In this architecture, BERT leverages Multi-Head Attention throughout its layers."
        chunks = [{"id": "c-20", "content": text}]

        rels = service.extract_relationships(chunks=chunks, nodes=sample_nodes, use_llm=True)
        assert len(rels) >= 1
        rel = rels[0]
        assert rel.source_node_name == "BERT"
        assert rel.target_node_name == "Multi-Head Attention"
