"""Unit tests for Knovera Knowledge Graph Persistence Service, Serialization, and Recovery (Phase 7 C7.6)."""

import json
from pathlib import Path
import tempfile
import uuid
import networkx as nx
import pytest

from backend.app.ml.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from backend.app.ml.knowledge_graph.graph_loader import GraphLoader
from backend.app.ml.knowledge_graph.graph_persistence import GraphPersistenceService
from backend.app.ml.knowledge_graph.graph_serializer import GraphSerializer
from backend.app.ml.knowledge_graph.ontology import ConceptType, EntityType
from backend.app.ml.knowledge_graph.relationships import RelationPredicate
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedRelationship,
    NormalizedNode,
    RelationshipEvidenceRecord,
    RelationshipValidationStatus,
)
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_extraction_run import KnowledgeExtractionRun
from backend.app.models.knowledge_graph_snapshot import KnowledgeGraphSnapshot
from backend.app.models.workspace import Workspace
from backend.app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from backend.app.repositories.knowledge_graph_snapshot_repository import (
    KnowledgeGraphSnapshotRepository,
)


@pytest.fixture
def temp_storage_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def workspace_with_graph_records(db_session):
    user_id = uuid.uuid4()
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user_id,
        name="Graph Persistence Workspace",
    )
    db_session.add(ws)
    db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user_id,
        original_filename="graph_doc.pdf",
        storage_key=f"gdoc_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=3000,
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
        content="BERT uses Multi-Head Attention.",
        token_count=5,
        content_hash="h" * 64,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    db_session.add(chunk)
    db_session.flush()

    # Create extraction run
    kg_repo = KnowledgeGraphRepository(db_session)
    run = kg_repo.create_extraction_run(
        workspace_id=ws.id,
        extraction_method="deterministic",
        ontology_version="1.0.0",
    )

    # Persist nodes
    n1 = NormalizedNode(
        id=str(uuid.uuid4()),
        workspace_id=str(ws.id),
        name="BERT",
        normalized_name="bert",
        category=EntityType.MODEL.value,
        node_type="entity",
        aliases=["BERT"],
    )
    n2 = NormalizedNode(
        id=str(uuid.uuid4()),
        workspace_id=str(ws.id),
        name="Multi-Head Attention",
        normalized_name="multi head attention",
        category=ConceptType.TECHNICAL_CONCEPT.value,
        node_type="concept",
        aliases=["Attention"],
    )
    node_map = kg_repo.persist_nodes_and_mentions(
        workspace_id=ws.id,
        nodes=[n1, n2],
        extraction_run_id=run.id,
    )

    # Persist relationship
    rel = ExtractedRelationship(
        source_node_name="BERT",
        target_node_name="Multi-Head Attention",
        predicate=RelationPredicate.USES.value,
        validation_status=RelationshipValidationStatus.VALIDATED.value,
        evidence=[
            RelationshipEvidenceRecord(
                chunk_id=str(chunk.id),
                evidence_text="BERT uses Multi-Head Attention",
                start_offset=0,
                end_offset=30,
            )
        ],
    )
    kg_repo.persist_relationships(
        workspace_id=ws.id,
        relationships=[rel],
        node_map=node_map,
        extraction_run_id=run.id,
    )
    db_session.commit()

    return ws, run, [n1, n2], [rel]


class TestGraphSerializationAndLoading:
    """Tests for deterministic JSON serialization, checksums, and MultiDiGraph reconstruction."""

    def test_serializer_and_loader_roundtrip(self):
        builder = KnowledgeGraphBuilder()
        ws_id = str(uuid.uuid4())
        n1 = NormalizedNode(id="n-1", workspace_id=ws_id, name="BERT", normalized_name="bert", category="model")
        n2 = NormalizedNode(id="n-2", workspace_id=ws_id, name="Attention", normalized_name="attention", category="technical_concept")
        rel = ExtractedRelationship(
            id="r-1",
            source_node_id="n-1",
            target_node_id="n-2",
            source_node_name="BERT",
            target_node_name="Attention",
            predicate="uses",
            validation_status=RelationshipValidationStatus.VALIDATED.value,
        )

        graph, stats = builder.build_graph(ws_id, [n1, n2], [rel])

        # Serialize
        json_str, checksum, manifest = GraphSerializer.serialize_graph(graph, stats)
        assert checksum is not None
        assert len(checksum) == 64
        assert manifest.artifact_checksum == checksum

        # Load back
        loaded_graph = GraphLoader.load_from_json(json_str, expected_checksum=checksum)
        assert loaded_graph.number_of_nodes() == 2
        assert loaded_graph.number_of_edges() == 1
        assert loaded_graph.has_edge("n-1", "n-2", key="r-1")

    def test_loader_detects_checksum_mismatch(self):
        builder = KnowledgeGraphBuilder()
        ws_id = str(uuid.uuid4())
        n1 = NormalizedNode(id="n-1", workspace_id=ws_id, name="BERT", normalized_name="bert", category="model")
        graph, stats = builder.build_graph(ws_id, [n1], [])

        json_str, checksum, _ = GraphSerializer.serialize_graph(graph, stats)

        # Corrupt one character
        corrupted_json = json_str.replace("BERT", "XERT")

        with pytest.raises(ValueError, match="checksum mismatch"):
            GraphLoader.load_from_json(corrupted_json, expected_checksum=checksum)


class TestGraphPersistenceService:
    """Tests for atomic file writes, active snapshot switching, and PostgreSQL registration."""

    def test_persist_snapshot_atomic_and_db_registration(
        self,
        db_session,
        temp_storage_dir,
        workspace_with_graph_records,
    ):
        ws, run, nodes, rels = workspace_with_graph_records
        service = GraphPersistenceService(base_storage_dir=temp_storage_dir)

        builder = KnowledgeGraphBuilder()
        graph, stats = builder.build_graph(str(ws.id), nodes, rels, extraction_run_id=str(run.id))

        snapshot_rec, manifest = service.persist_snapshot(
            workspace_id=str(ws.id),
            graph=graph,
            statistics=stats,
            session=db_session,
            extraction_run_id=str(run.id),
            is_active=True,
        )
        db_session.commit()

        assert snapshot_rec.id is not None
        assert snapshot_rec.is_active is True
        assert snapshot_rec.node_count == 2
        assert snapshot_rec.edge_count == 1

        # Verify disk artifacts exist
        artifact_path = temp_storage_dir / snapshot_rec.artifact_uri
        assert artifact_path.exists()
        manifest_path = artifact_path.parent / "manifest.json"
        assert manifest_path.exists()

    def test_active_snapshot_switching(
        self,
        db_session,
        temp_storage_dir,
        workspace_with_graph_records,
    ):
        ws, run, nodes, rels = workspace_with_graph_records
        service = GraphPersistenceService(base_storage_dir=temp_storage_dir)
        builder = KnowledgeGraphBuilder()
        graph, stats = builder.build_graph(str(ws.id), nodes, rels, extraction_run_id=str(run.id))

        # First active snapshot
        snap1, _ = service.persist_snapshot(
            workspace_id=str(ws.id),
            graph=graph,
            statistics=stats,
            session=db_session,
            is_active=True,
        )
        db_session.commit()
        assert snap1.is_active is True

        # Second active snapshot
        snap2, _ = service.persist_snapshot(
            workspace_id=str(ws.id),
            graph=graph,
            statistics=stats,
            session=db_session,
            is_active=True,
        )
        db_session.commit()

        # Check repository: only snap2 should now be active
        snap_repo = KnowledgeGraphSnapshotRepository(db_session)
        active_snap = snap_repo.get_active_snapshot(ws.id)
        assert active_snap is not None
        assert active_snap.id == snap2.id

        # Verify snap1 is deactivated
        refreshed_snap1 = snap_repo.get_snapshot_by_id(snap1.id)
        assert refreshed_snap1.is_active is False

    def test_reconstruct_graph_from_db(
        self,
        db_session,
        temp_storage_dir,
        workspace_with_graph_records,
    ):
        """Demonstrates reconstruction from PostgreSQL when artifact is missing."""
        ws, run, nodes, rels = workspace_with_graph_records
        service = GraphPersistenceService(base_storage_dir=temp_storage_dir)

        # Reconstruct directly from DB
        reconstructed_graph, stats = service.reconstruct_from_db(
            workspace_id=ws.id,
            session=db_session,
            extraction_run_id=run.id,
        )

        assert isinstance(reconstructed_graph, nx.MultiDiGraph)
        assert reconstructed_graph.number_of_nodes() == 2
        assert reconstructed_graph.number_of_edges() == 1
        assert stats.total_nodes == 2
        assert stats.total_edges == 1
