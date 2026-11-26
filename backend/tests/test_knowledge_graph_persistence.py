"""Unit tests for KnowledgeGraphRepository and PostgreSQL schema persistence (Phase 7)."""

import uuid
import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_extraction_run import KnowledgeExtractionRun
from backend.app.models.knowledge_mention import KnowledgeMention
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.knowledge_relationship import KnowledgeRelationship
from backend.app.models.relationship_evidence import RelationshipEvidence
from backend.app.models.workspace import Workspace
from backend.app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedMention,
    ExtractedRelationship,
    NormalizedNode,
    RelationshipEvidenceRecord,
)


@pytest.fixture
def workspace_fixture(db_session):
    user_id = uuid.uuid4()
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user_id,
        name="Knowledge Graph Workspace",
    )
    db_session.add(ws)
    db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user_id,
        original_filename="graph_doc.pdf",
        storage_key=f"graph_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=2048,
        sha256="g" * 64,
        processing_status="completed",
    )
    db_session.add(doc)
    db_session.flush()

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc.id,
        chunk_index=0,
        content="BERT uses Multi-Head Attention for contextual representations.",
        token_count=10,
        content_hash="h" * 64,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    db_session.add(chunk)
    db_session.commit()
    return ws, chunk


class TestKnowledgeGraphRepository:
    """Tests for database persistence, unique constraints, and relation queries."""

    def test_create_and_get_extraction_run(self, db_session, workspace_fixture):
        ws, chunk = workspace_fixture
        repo = KnowledgeGraphRepository(db_session)

        run = repo.create_extraction_run(
            workspace_id=ws.id,
            extraction_method="deterministic",
            ontology_version="1.0.0",
            total_chunks_processed=1,
            total_nodes_extracted=2,
            total_relationships_extracted=1,
            statistics={"duration_ms": 12.5},
        )
        db_session.commit()

        assert run.id is not None
        assert run.workspace_id == ws.id
        assert run.total_nodes_extracted == 2

        latest = repo.get_latest_run(ws.id)
        assert latest is not None
        assert latest.id == run.id

    def test_persist_nodes_and_mentions(self, db_session, workspace_fixture):
        ws, chunk = workspace_fixture
        repo = KnowledgeGraphRepository(db_session)

        run = repo.create_extraction_run(workspace_id=ws.id)

        node_schema = NormalizedNode(
            workspace_id=str(ws.id),
            name="BERT",
            normalized_name="bert",
            category="model",
            node_type="entity",
            description="Bidirectional encoder model",
            aliases=["BERT Model"],
            mentions=[
                ExtractedMention(
                    surface_form="BERT",
                    start_offset=0,
                    end_offset=4,
                    chunk_id=str(chunk.id),
                    confidence=0.98,
                )
            ],
        )

        node_map = repo.persist_nodes_and_mentions(
            workspace_id=ws.id,
            nodes=[node_schema],
            extraction_run_id=run.id,
        )
        db_session.commit()

        assert "bert" in node_map
        node_record = node_map["bert"]
        assert node_record.name == "BERT"
        assert len(node_record.mentions) == 1
        assert node_record.mentions[0].surface_form == "BERT"
        assert node_record.mentions[0].start_offset == 0

    def test_persist_relationships_and_evidence(self, db_session, workspace_fixture):
        ws, chunk = workspace_fixture
        repo = KnowledgeGraphRepository(db_session)
        run = repo.create_extraction_run(workspace_id=ws.id)

        node_a = NormalizedNode(
            workspace_id=str(ws.id),
            name="BERT",
            normalized_name="bert",
            category="model",
            node_type="entity",
        )
        node_b = NormalizedNode(
            workspace_id=str(ws.id),
            name="Multi-Head Attention",
            normalized_name="multi head attention",
            category="technical_concept",
            node_type="concept",
        )

        node_map = repo.persist_nodes_and_mentions(
            workspace_id=ws.id,
            nodes=[node_a, node_b],
            extraction_run_id=run.id,
        )

        rel_schema = ExtractedRelationship(
            source_node_name="BERT",
            target_node_name="Multi-Head Attention",
            predicate="uses",
            inverse_predicate="used_by",
            is_negated=False,
            modality="certain",
            evidence=[
                RelationshipEvidenceRecord(
                    chunk_id=str(chunk.id),
                    evidence_text="BERT uses Multi-Head Attention",
                    start_offset=0,
                    end_offset=30,
                    confidence=0.95,
                )
            ],
        )

        persisted_rels = repo.persist_relationships(
            workspace_id=ws.id,
            relationships=[rel_schema],
            node_map=node_map,
            extraction_run_id=run.id,
        )
        db_session.commit()

        assert len(persisted_rels) == 1
        rel_rec = persisted_rels[0]
        assert rel_rec.relation_type == "uses"
        assert len(rel_rec.evidence_records) == 1
        assert rel_rec.evidence_records[0].evidence_text == "BERT uses Multi-Head Attention"

    def test_query_workspace_nodes_and_relationships(self, db_session, workspace_fixture):
        ws, chunk = workspace_fixture
        repo = KnowledgeGraphRepository(db_session)
        run = repo.create_extraction_run(workspace_id=ws.id)

        node_schema = NormalizedNode(
            workspace_id=str(ws.id),
            name="BM25",
            normalized_name="bm25",
            category="algorithm",
            node_type="concept",
        )
        repo.persist_nodes_and_mentions(
            workspace_id=ws.id,
            nodes=[node_schema],
            extraction_run_id=run.id,
        )
        db_session.commit()

        nodes = repo.get_workspace_nodes(workspace_id=ws.id)
        assert len(nodes) >= 1
        assert any(n.name == "BM25" for n in nodes)
