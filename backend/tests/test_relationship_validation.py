"""Unit tests for Knovera Relationship Validation Service (Phase 7 C7.4)."""

import hashlib
import uuid
import pytest

from backend.app.ml.knowledge_graph.ontology import ConceptType, EntityType
from backend.app.ml.knowledge_graph.relationships import RelationPredicate
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedRelationship,
    Modality,
    NormalizedNode,
    RelationshipEvidenceRecord,
    RelationshipValidationStatus,
)
from backend.app.ml.knowledge_graph.validation import RelationshipValidationService


class TestRelationshipValidationService:
    """Comprehensive tests for C7.4 relationship validation."""

    @pytest.fixture
    def service(self):
        return RelationshipValidationService()

    @pytest.fixture
    def sample_workspace_id(self):
        return str(uuid.uuid4())

    @pytest.fixture
    def sample_nodes(self, sample_workspace_id):
        node_model = NormalizedNode(
            id=str(uuid.uuid4()),
            workspace_id=sample_workspace_id,
            name="BERT",
            normalized_name="bert",
            category=EntityType.MODEL.value,
            node_type=EntityType.MODEL.value,
        )
        node_concept = NormalizedNode(
            id=str(uuid.uuid4()),
            workspace_id=sample_workspace_id,
            name="Multi-Head Attention",
            normalized_name="multi head attention",
            category=ConceptType.TECHNICAL_CONCEPT.value,
            node_type=ConceptType.TECHNICAL_CONCEPT.value,
        )
        node_dataset = NormalizedNode(
            id=str(uuid.uuid4()),
            workspace_id=sample_workspace_id,
            name="ImageNet",
            normalized_name="imagenet",
            category=EntityType.DATASET.value,
            node_type=EntityType.DATASET.value,
        )
        node_person = NormalizedNode(
            id=str(uuid.uuid4()),
            workspace_id=sample_workspace_id,
            name="Vaswani",
            normalized_name="vaswani",
            category=EntityType.PERSON.value,
            node_type=EntityType.PERSON.value,
        )
        return [node_model, node_concept, node_dataset, node_person]

    @pytest.fixture
    def sample_chunks(self, sample_workspace_id):
        c1_text = "BERT uses Multi-Head Attention for contextual representations."
        c2_text = "BERT was trained on ImageNet for vision tasks."
        c3_text = "BERT was proposed by Vaswani in 2017."

        return [
            {
                "id": "c-1",
                "workspace_id": sample_workspace_id,
                "content": c1_text,
                "content_hash": hashlib.sha256(c1_text.encode("utf-8")).hexdigest(),
            },
            {
                "id": "c-2",
                "workspace_id": sample_workspace_id,
                "content": c2_text,
                "content_hash": hashlib.sha256(c2_text.encode("utf-8")).hexdigest(),
            },
            {
                "id": "c-3",
                "workspace_id": sample_workspace_id,
                "content": c3_text,
                "content_hash": hashlib.sha256(c3_text.encode("utf-8")).hexdigest(),
            },
        ]

    def test_validate_valid_relationship(self, service, sample_workspace_id, sample_nodes, sample_chunks):
        rel = ExtractedRelationship(
            source_node_name="BERT",
            target_node_name="Multi-Head Attention",
            predicate=RelationPredicate.USES.value,
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id="c-1",
                    evidence_text="BERT uses Multi-Head Attention",
                    start_offset=0,
                    end_offset=30,
                )
            ],
        )

        report = service.validate_relationships(
            workspace_id=sample_workspace_id,
            relationships=[rel],
            nodes=sample_nodes,
            chunks=sample_chunks,
        )

        assert report.candidate_count == 1
        assert report.validated_count == 1
        assert report.rejected_count == 0
        assert rel.validation_status == RelationshipValidationStatus.VALIDATED.value

    def test_reject_missing_endpoint(self, service, sample_workspace_id, sample_nodes, sample_chunks):
        rel = ExtractedRelationship(
            source_node_name="UnknownModelX",
            target_node_name="Multi-Head Attention",
            predicate=RelationPredicate.USES.value,
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id="c-1",
                    evidence_text="BERT uses Multi-Head Attention",
                    start_offset=0,
                    end_offset=30,
                )
            ],
        )

        report = service.validate_relationships(
            workspace_id=sample_workspace_id,
            relationships=[rel],
            nodes=sample_nodes,
            chunks=sample_chunks,
        )

        assert report.rejected_count == 1
        assert report.invalid_endpoint_count == 1
        assert rel.validation_status == RelationshipValidationStatus.REJECTED.value

    def test_reject_cross_workspace_endpoint(self, service, sample_workspace_id, sample_nodes, sample_chunks):
        alien_node = NormalizedNode(
            id=str(uuid.uuid4()),
            workspace_id=str(uuid.uuid4()),  # different workspace
            name="AlienConcept",
            normalized_name="alienconcept",
            category=ConceptType.TECHNICAL_CONCEPT.value,
        )
        nodes = sample_nodes + [alien_node]

        rel = ExtractedRelationship(
            source_node_name="BERT",
            target_node_name="AlienConcept",
            predicate=RelationPredicate.USES.value,
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id="c-1",
                    evidence_text="BERT uses Multi-Head Attention",
                    start_offset=0,
                    end_offset=30,
                )
            ],
        )

        report = service.validate_relationships(
            workspace_id=sample_workspace_id,
            relationships=[rel],
            nodes=nodes,
            chunks=sample_chunks,
        )

        assert report.rejected_count == 1
        assert report.workspace_integrity_failures >= 1

    def test_reject_invalid_self_loop(self, service, sample_workspace_id, sample_nodes, sample_chunks):
        rel = ExtractedRelationship(
            source_node_name="BERT",
            target_node_name="BERT",
            predicate=RelationPredicate.USES.value,
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id="c-1",
                    evidence_text="BERT uses Multi-Head Attention",
                    start_offset=0,
                    end_offset=30,
                )
            ],
        )

        report = service.validate_relationships(
            workspace_id=sample_workspace_id,
            relationships=[rel],
            nodes=sample_nodes,
            chunks=sample_chunks,
        )

        assert report.rejected_count == 1
        assert "Invalid self-loop" in report.results[0].reasons[0]

    def test_reject_domain_range_violation(self, service, sample_workspace_id, sample_nodes, sample_chunks):
        # "proposed_by" requires range to be person, organization, etc.
        # Here target is "Multi-Head Attention" (technical_concept) -> violation
        rel = ExtractedRelationship(
            source_node_name="BERT",
            target_node_name="Multi-Head Attention",
            predicate=RelationPredicate.PROPOSED_BY.value,
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id="c-1",
                    evidence_text="BERT uses Multi-Head Attention",
                    start_offset=0,
                    end_offset=30,
                )
            ],
        )

        report = service.validate_relationships(
            workspace_id=sample_workspace_id,
            relationships=[rel],
            nodes=sample_nodes,
            chunks=sample_chunks,
        )

        assert report.rejected_count == 1
        assert report.invalid_predicate_count == 1
        assert any("domain/range violation" in r for r in report.results[0].reasons)

    def test_reject_evidence_mismatch(self, service, sample_workspace_id, sample_nodes, sample_chunks):
        rel = ExtractedRelationship(
            source_node_name="BERT",
            target_node_name="Multi-Head Attention",
            predicate=RelationPredicate.USES.value,
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id="c-1",
                    evidence_text="Completely different fabricated sentence.",
                    start_offset=0,
                    end_offset=30,
                )
            ],
        )

        report = service.validate_relationships(
            workspace_id=sample_workspace_id,
            relationships=[rel],
            nodes=sample_nodes,
            chunks=sample_chunks,
        )

        assert report.rejected_count == 1
        assert report.invalid_evidence_count == 1

    def test_reject_stale_evidence_hash_mismatch(self, service, sample_workspace_id, sample_nodes, sample_chunks):
        stale_chunks = [
            {
                "id": "c-1",
                "workspace_id": sample_workspace_id,
                "content": "BERT uses Multi-Head Attention for contextual representations.",
                "content_hash": "stale_hash_that_does_not_match",
            }
        ]
        rel = ExtractedRelationship(
            source_node_name="BERT",
            target_node_name="Multi-Head Attention",
            predicate=RelationPredicate.USES.value,
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id="c-1",
                    evidence_text="BERT uses Multi-Head Attention",
                    start_offset=0,
                    end_offset=30,
                )
            ],
        )

        report = service.validate_relationships(
            workspace_id=sample_workspace_id,
            relationships=[rel],
            nodes=sample_nodes,
            chunks=stale_chunks,
        )

        assert report.rejected_count == 1
        assert report.stale_evidence_count >= 1

    def test_modality_flags_needs_review(self, service, sample_workspace_id, sample_nodes, sample_chunks):
        rel = ExtractedRelationship(
            source_node_name="BERT",
            target_node_name="Multi-Head Attention",
            predicate=RelationPredicate.USES.value,
            modality=Modality.HYPOTHETICAL.value,
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id="c-1",
                    evidence_text="BERT uses Multi-Head Attention",
                    start_offset=0,
                    end_offset=30,
                )
            ],
        )

        report = service.validate_relationships(
            workspace_id=sample_workspace_id,
            relationships=[rel],
            nodes=sample_nodes,
            chunks=sample_chunks,
        )

        assert report.needs_review_count == 1
        assert rel.validation_status == RelationshipValidationStatus.NEEDS_REVIEW.value
        assert report.modality_findings >= 1

    def test_contradiction_detection_in_batch(self, service, sample_workspace_id, sample_nodes, sample_chunks):
        rel_pos = ExtractedRelationship(
            source_node_name="BERT",
            target_node_name="Multi-Head Attention",
            predicate=RelationPredicate.USES.value,
            is_negated=False,
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id="c-1",
                    evidence_text="BERT uses Multi-Head Attention",
                    start_offset=0,
                    end_offset=30,
                )
            ],
        )
        rel_neg = ExtractedRelationship(
            source_node_name="BERT",
            target_node_name="Multi-Head Attention",
            predicate=RelationPredicate.USES.value,
            is_negated=True,
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id="c-1",
                    evidence_text="BERT uses Multi-Head Attention",
                    start_offset=0,
                    end_offset=30,
                )
            ],
        )

        report = service.validate_relationships(
            workspace_id=sample_workspace_id,
            relationships=[rel_pos, rel_neg],
            nodes=sample_nodes,
            chunks=sample_chunks,
        )

        assert report.contradiction_warnings >= 1
        assert report.needs_review_count >= 1
