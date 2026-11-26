"""End-to-End tests for Knovera Knowledge Extraction Pipeline (Phase 7 C7.1 - C7.3)."""

import uuid
import pytest

from backend.app.ml.knowledge_graph.orchestrator import KnowledgeExtractionOrchestrator
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.workspace import Workspace
from backend.app.repositories.knowledge_graph_repository import KnowledgeGraphRepository


@pytest.fixture
def multi_chunk_corpus(db_session):
    user_id = uuid.uuid4()
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user_id,
        name="AI Research Workspace",
    )
    db_session.add(ws)
    db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user_id,
        original_filename="information_retrieval.pdf",
        storage_key=f"ir_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=5000,
        sha256="i" * 64,
        processing_status="completed",
    )
    db_session.add(doc)
    db_session.flush()

    c1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc.id,
        chunk_index=0,
        content=(
            "Natural Language Processing (NLP) has advanced significantly. "
            "BERT uses Multi-Head Attention for contextual representations."
        ),
        token_count=20,
        content_hash="c1" + "0" * 62,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    c2 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc.id,
        chunk_index=1,
        content=(
            "Reciprocal Rank Fusion is defined as an algorithm that combines rankings from BM25 and dense embeddings. "
            "BM25 does not use Neural Embeddings for keyword matching."
        ),
        token_count=28,
        content_hash="c2" + "0" * 62,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    c3 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc.id,
        chunk_index=2,
        content=(
            "We evaluated BERT on the ImageNet benchmark using Python and PyTorch. "
            "The model achieves high Recall@10 and nDCG scores."
        ),
        token_count=22,
        content_hash="c3" + "0" * 62,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    db_session.add_all([c1, c2, c3])
    db_session.commit()

    return ws, [c1, c2, c3]


class TestEndToEndKnowledgeExtraction:
    """Tests the full pipeline from raw chunks to normalized graph persistence."""

    def test_run_pipeline_in_memory(self, multi_chunk_corpus):
        ws, chunks = multi_chunk_corpus
        orchestrator = KnowledgeExtractionOrchestrator()

        chunk_dicts = [{"id": str(c.id), "content": c.content} for c in chunks]

        result = orchestrator.run_pipeline(
            workspace_id=str(ws.id),
            chunks=chunk_dicts,
            use_llm=False,
            session=None,
        )

        assert result.workspace_id == str(ws.id)
        assert result.total_chunks_processed == 3
        assert result.total_nodes_extracted > 0
        assert result.total_relationships_extracted > 0
        assert result.duration_ms > 0

        # Check canonical nodes
        node_names = {n.name.lower() for n in result.nodes}
        assert "bert" in node_names
        assert "multi-head attention" in node_names
        assert "bm25" in node_names
        assert "reciprocal rank fusion" in node_names

        # Check relationship verification
        bert_uses = next(
            (r for r in result.relationships if r.source_node_name.lower() == "bert" and r.predicate == "uses"),
            None,
        )
        assert bert_uses is not None
        assert bert_uses.target_node_name.lower() == "multi-head attention"
        assert len(bert_uses.evidence) >= 1

        # Check negation detection
        bm25_rel = next(
            (r for r in result.relationships if r.source_node_name.lower() == "bm25"),
            None,
        )
        assert bm25_rel is not None
        assert bm25_rel.is_negated is True

    def test_run_pipeline_with_database_persistence(self, db_session, multi_chunk_corpus):
        ws, chunks = multi_chunk_corpus
        orchestrator = KnowledgeExtractionOrchestrator()

        chunk_dicts = [{"id": str(c.id), "content": c.content} for c in chunks]

        result = orchestrator.run_pipeline(
            workspace_id=str(ws.id),
            chunks=chunk_dicts,
            use_llm=False,
            session=db_session,
        )

        assert result.run_id is not None

        # Verify database contents via repository
        repo = KnowledgeGraphRepository(db_session)
        latest_run = repo.get_latest_run(ws.id)
        assert latest_run is not None
        assert str(latest_run.id) == result.run_id

        persisted_nodes = repo.get_workspace_nodes(workspace_id=ws.id)
        assert len(persisted_nodes) == result.total_nodes_extracted

        persisted_rels = repo.get_workspace_relationships(workspace_id=ws.id)
        assert len(persisted_rels) == result.total_relationships_extracted

        # Verify evidence spans on persisted relationship
        for rel in persisted_rels:
            assert len(rel.evidence_records) >= 1
            for ev in rel.evidence_records:
                assert ev.evidence_text is not None
                assert ev.start_offset >= 0
                assert ev.end_offset > ev.start_offset

        # Verify active knowledge graph snapshot was persisted (C7.6)
        from backend.app.repositories.knowledge_graph_snapshot_repository import KnowledgeGraphSnapshotRepository
        snap_repo = KnowledgeGraphSnapshotRepository(db_session)
        active_snap = snap_repo.get_active_snapshot(ws.id)
        assert active_snap is not None
        assert active_snap.is_active is True
        assert active_snap.node_count == result.total_nodes_extracted
        assert active_snap.artifact_checksum is not None
