"""Unit tests for Knovera NetworkX Graph Builder and Statistics Service (Phase 7 C7.5)."""

import uuid
import networkx as nx
import pytest

from backend.app.ml.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from backend.app.ml.knowledge_graph.graph_statistics import GraphStatisticsService
from backend.app.ml.knowledge_graph.ontology import ConceptType, EntityType
from backend.app.ml.knowledge_graph.relationships import RelationPredicate
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedRelationship,
    NormalizedNode,
    RelationshipEvidenceRecord,
    RelationshipValidationStatus,
)


class TestNetworkXGraphBuilder:
    """Comprehensive tests for C7.5 NetworkX MultiDiGraph construction and metrics."""

    @pytest.fixture
    def builder(self):
        return KnowledgeGraphBuilder(builder_version="1.0.0")

    @pytest.fixture
    def workspace_id(self):
        return str(uuid.uuid4())

    @pytest.fixture
    def sample_nodes(self, workspace_id):
        n1 = NormalizedNode(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            name="Python",
            normalized_name="python",
            category=EntityType.PROGRAMMING_LANGUAGE.value,
            node_type=EntityType.PROGRAMMING_LANGUAGE.value,
            aliases=["Python 3"],
        )
        n2 = NormalizedNode(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            name="Machine Learning",
            normalized_name="machine learning",
            category=ConceptType.TECHNICAL_CONCEPT.value,
            node_type=ConceptType.TECHNICAL_CONCEPT.value,
            aliases=["ML"],
        )
        n3 = NormalizedNode(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            name="IsolatedConcept",
            normalized_name="isolatedconcept",
            category=ConceptType.THEORY.value,
            node_type=ConceptType.THEORY.value,
        )
        return [n1, n2, n3]

    def test_build_graph_basic(self, builder, workspace_id, sample_nodes):
        n1, n2, n3 = sample_nodes
        rel = ExtractedRelationship(
            id="rel-1",
            source_node_id=n1.id,
            target_node_id=n2.id,
            source_node_name=n1.name,
            target_node_name=n2.name,
            predicate=RelationPredicate.APPLIED_TO.value,
            validation_status=RelationshipValidationStatus.VALIDATED.value,
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id="c-1",
                    evidence_text="Python is applied to Machine Learning",
                    start_offset=0,
                    end_offset=37,
                )
            ],
        )

        graph, stats = builder.build_graph(
            workspace_id=workspace_id,
            nodes=sample_nodes,
            relationships=[rel],
        )

        assert isinstance(graph, nx.MultiDiGraph)
        assert graph.number_of_nodes() == 3
        assert graph.number_of_edges() == 1

        # Check node data
        node_data = graph.nodes[n1.id]
        assert node_data["label"] == "Python"
        assert node_data["node_kind"] == "entity"
        assert "Python 3" in node_data["aliases"]

        # Check edge data
        assert graph.has_edge(n1.id, n2.id, key="rel-1")
        edge_data = graph.edges[n1.id, n2.id, "rel-1"]
        assert edge_data["predicate"] == RelationPredicate.APPLIED_TO.value
        assert edge_data["relationship_id"] == "rel-1"
        assert edge_data["source_chunk_ids"] == ["c-1"]

        # Check statistics
        assert stats.total_nodes == 3
        assert stats.total_edges == 1
        assert stats.isolated_node_count == 1  # n3 is isolated
        assert stats.concept_count == 2
        assert stats.entity_count == 1

    def test_parallel_edges_preservation(self, builder, workspace_id, sample_nodes):
        """Demonstrates that multiple distinct predicates connecting the same pair are preserved."""
        n1, n2, _ = sample_nodes

        rel1 = ExtractedRelationship(
            id="rel-p1",
            source_node_id=n1.id,
            target_node_id=n2.id,
            source_node_name=n1.name,
            target_node_name=n2.name,
            predicate=RelationPredicate.APPLIED_TO.value,
            validation_status=RelationshipValidationStatus.VALIDATED.value,
        )
        rel2 = ExtractedRelationship(
            id="rel-p2",
            source_node_id=n1.id,
            target_node_id=n2.id,
            source_node_name=n1.name,
            target_node_name=n2.name,
            predicate=RelationPredicate.SUPPORTS.value,
            validation_status=RelationshipValidationStatus.VALIDATED.value,
        )

        graph, stats = builder.build_graph(
            workspace_id=workspace_id,
            nodes=[n1, n2],
            relationships=[rel1, rel2],
        )

        assert graph.number_of_edges() == 2
        assert graph.has_edge(n1.id, n2.id, key="rel-p1")
        assert graph.has_edge(n1.id, n2.id, key="rel-p2")
        assert stats.parallel_edge_count == 1

    def test_excludes_rejected_relationships(self, builder, workspace_id, sample_nodes):
        n1, n2, _ = sample_nodes

        rel_valid = ExtractedRelationship(
            id="rel-v",
            source_node_id=n1.id,
            target_node_id=n2.id,
            source_node_name=n1.name,
            target_node_name=n2.name,
            predicate=RelationPredicate.APPLIED_TO.value,
            validation_status=RelationshipValidationStatus.VALIDATED.value,
        )
        rel_rejected = ExtractedRelationship(
            id="rel-r",
            source_node_id=n1.id,
            target_node_id=n2.id,
            source_node_name=n1.name,
            target_node_name=n2.name,
            predicate=RelationPredicate.CONTAINS.value,
            validation_status=RelationshipValidationStatus.REJECTED.value,
        )

        graph, stats = builder.build_graph(
            workspace_id=workspace_id,
            nodes=[n1, n2],
            relationships=[rel_valid, rel_rejected],
        )

        assert graph.number_of_edges() == 1
        assert not graph.has_edge(n1.id, n2.id, key="rel-r")

    def test_diagnostic_mode_includes_needs_review(self, builder, workspace_id, sample_nodes):
        n1, n2, _ = sample_nodes

        rel_review = ExtractedRelationship(
            id="rel-nr",
            source_node_id=n1.id,
            target_node_id=n2.id,
            source_node_name=n1.name,
            target_node_name=n2.name,
            predicate=RelationPredicate.SUPPORTS.value,
            validation_status=RelationshipValidationStatus.NEEDS_REVIEW.value,
        )

        # Normal mode -> excluded
        graph_normal, _ = builder.build_graph(
            workspace_id=workspace_id,
            nodes=[n1, n2],
            relationships=[rel_review],
            include_needs_review=False,
        )
        assert graph_normal.number_of_edges() == 0

        # Diagnostic mode -> included
        graph_diag, _ = builder.build_graph(
            workspace_id=workspace_id,
            nodes=[n1, n2],
            relationships=[rel_review],
            include_needs_review=True,
        )
        assert graph_diag.number_of_edges() == 1

    def test_deterministic_construction(self, builder, workspace_id, sample_nodes):
        n1, n2, _ = sample_nodes
        rels = [
            ExtractedRelationship(
                id=f"r-{i}",
                source_node_id=n1.id,
                target_node_id=n2.id,
                source_node_name=n1.name,
                target_node_name=n2.name,
                predicate=RelationPredicate.USES.value,
                validation_status=RelationshipValidationStatus.VALIDATED.value,
            )
            for i in range(5)
        ]

        g1, s1 = builder.build_graph(workspace_id, sample_nodes, rels)
        g2, s2 = builder.build_graph(workspace_id, list(reversed(sample_nodes)), list(reversed(rels)))

        assert list(g1.nodes()) == list(g2.nodes())
        assert list(g1.edges(keys=True)) == list(g2.edges(keys=True))
        assert s1.total_nodes == s2.total_nodes
        assert s1.total_edges == s2.total_edges
