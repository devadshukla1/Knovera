"""Tests for Multi-Document Knovera Mind Map generation, merging, deduplication, deletion, and isolation."""

from datetime import datetime, timezone
import hashlib
import uuid
import pytest
from sqlalchemy.orm import Session

from backend.app.core.local_user import LOCAL_USER_ID
from backend.app.db.session import SessionLocal
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.workspace import Workspace
from backend.app.services.mind_map_service import (
    MindMapService,
    _are_concepts_equivalent,
)


def _add_ready_doc(
    db: Session,
    workspace_id: uuid.UUID,
    filename: str,
    sections: list[tuple[int, str]],
) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        uploaded_by_user_id=LOCAL_USER_ID,
        original_filename=filename,
        storage_key=f"test/{uuid.uuid4()}_{filename}",
        media_type="text/plain",
        file_extension="txt",
        file_size_bytes=1024,
        sha256=hashlib.sha256(f"{filename}:{sections}".encode()).hexdigest(),
        processing_status="ready",
    )
    db.add(doc)
    db.flush()

    for idx, (page, text) in enumerate(sections):
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            document_id=doc.id,
            chunk_index=idx,
            page_start=page,
            page_end=page,
            content=text,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            token_count=max(10, len(text) // 4),
            parser_version="test_v1",
            cleaning_version="test_v1",
            chunking_version="test_v1",
        )
        db.add(chunk)
    db.commit()
    return doc


def test_concept_deduplication_equivalence_rules():
    assert _are_concepts_equivalent("Tabu Search Memory Structures", "Memory Structures in Tabu Search")
    assert _are_concepts_equivalent("Cost Function (MSE)", "MSE Cost Function")
    # Distinct modifiers must NEVER be merged
    assert not _are_concepts_equivalent("Short-Term Memory", "Long-Term Memory")
    assert not _are_concepts_equivalent("Dense Retrieval", "Sparse Retrieval")
    assert not _are_concepts_equivalent("SVM Classifier", "Logistic Classifier")


def test_incremental_multi_doc_merge_deletion_and_isolation(monkeypatch):
    db: Session = SessionLocal()
    ws_a_id = uuid.uuid4()
    ws_b_id = uuid.uuid4()

    try:
        ws_a = Workspace(id=ws_a_id, owner_user_id=LOCAL_USER_ID, name="KG Merge Test WS A")
        ws_b = Workspace(id=ws_b_id, owner_user_id=LOCAL_USER_ID, name="KG Merge Test WS B")
        db.add_all([ws_a, ws_b])
        db.commit()

        service = MindMapService()
        # Force deterministic multi-document extractor for fast, repeatable unit testing
        monkeypatch.setattr(service, "_generate_with_llm", lambda *args, **kwargs: None)

        # Test A: 1 document (Doc A)
        doc_a = _add_ready_doc(
            db,
            ws_a_id,
            "doc_a_tabu.txt",
            [
                (1, "Tabu Search Memory Structures\nTabu Search uses short-term memory called a Tabu List to avoid cycling back to recent solutions."),
                (2, "Short-Term Memory\nThe recency-based Tabu List forbids reversing recent moves for a fixed tenure."),
            ],
        )
        tree_1 = service.build_mind_map(ws_a_id, db, user_id=LOCAL_USER_ID)
        assert tree_1.version == 1
        assert tree_1.source_document_count == 1
        assert tree_1.source_document_names == ["doc_a_tabu.txt"]
        assert tree_1.is_out_of_date is False
        labels_1 = [n.label for n in tree_1.nodes]
        assert any("Tabu Search Memory Structures" in l for l in labels_1)

        # Mark one concept as learned to verify preservation across rebuilds
        target_node = next(n for n in tree_1.nodes if "Tabu Search Memory Structures" in n.label)
        service.update_node_status(ws_a_id, target_node.id, "learned", db, LOCAL_USER_ID)

        # Test B: Add Document B (with shared equivalent concept + unique concept)
        doc_b = _add_ready_doc(
            db,
            ws_a_id,
            "doc_b_aspiration.txt",
            [
                (4, "Memory Structures in Tabu Search\nLong-term memory tracks frequency across the entire search trajectory."),
                (5, "Aspiration Criteria\nAspiration criteria override tabu restrictions when a move yields a new global best solution."),
            ],
        )

        # Out-of-date detection before rebuild
        stale_view = service.get_mind_map(ws_a_id, db, user_id=LOCAL_USER_ID)
        assert stale_view.is_out_of_date is True
        assert "New document available" in (stale_view.out_of_date_reason or "")

        # Rebuild -> A + B unified
        tree_2 = service.build_mind_map(ws_a_id, db, user_id=LOCAL_USER_ID)
        assert tree_2.version == 2
        assert tree_2.source_document_count == 2
        assert set(tree_2.source_document_names) == {"doc_a_tabu.txt", "doc_b_aspiration.txt"}
        assert tree_2.is_out_of_date is False

        # Shared concept deduplicated + preserves BOTH source references + preserves 'learned' status
        merged_nodes = [n for n in tree_2.nodes if "Memory Structures" in n.label and n.level == 2]
        assert len(merged_nodes) == 1, f"Expected 1 deduplicated node, got {[n.label for n in merged_nodes]}"
        assert merged_nodes[0].is_shared_across_documents is True
        assert set(merged_nodes[0].source_documents or []) >= {"doc_a_tabu.txt", "doc_b_aspiration.txt"}
        assert merged_nodes[0].learning_status == "learned"
        assert any("Aspiration Criteria" in n.label for n in tree_2.nodes)

        # Test C: Add Document C -> A + B + C unified
        doc_c = _add_ready_doc(
            db,
            ws_a_id,
            "doc_c_intensification.txt",
            [
                (3, "Intensification and Diversification\nIntensification focuses search near elite solutions while diversification explores new regions."),
            ],
        )
        tree_3 = service.build_mind_map(ws_a_id, db, user_id=LOCAL_USER_ID)
        assert tree_3.version == 3
        assert tree_3.source_document_count == 3
        assert set(tree_3.source_document_names) == {
            "doc_a_tabu.txt",
            "doc_b_aspiration.txt",
            "doc_c_intensification.txt",
        }
        assert any("Intensification" in n.label for n in tree_3.nodes)

        # Test F: Delete Document B -> rebuild excludes Document B
        doc_b.deleted_at = datetime.now(timezone.utc)
        db.commit()
        stale_after_del = service.get_mind_map(ws_a_id, db, user_id=LOCAL_USER_ID)
        assert stale_after_del.is_out_of_date is True

        tree_4 = service.build_mind_map(ws_a_id, db, user_id=LOCAL_USER_ID)
        assert tree_4.version == 4
        assert tree_4.source_document_count == 2
        assert "doc_b_aspiration.txt" not in tree_4.source_document_names
        assert not any("Aspiration Criteria" in n.label for n in tree_4.nodes)

        # Test H: Failure recovery preserves previous valid graph
        def _boom(*args, **kwargs):
            raise RuntimeError("Simulated graph failure")

        monkeypatch.setattr(service, "_assemble_tree", _boom)
        with pytest.raises(RuntimeError):
            service.build_mind_map(ws_a_id, db, user_id=LOCAL_USER_ID)
        monkeypatch.undo()

        preserved = service.get_mind_map(ws_a_id, db, user_id=LOCAL_USER_ID)
        assert preserved.version == 4
        assert preserved.source_document_count == 2

        # Test I: Workspace Isolation (WS B only sees WS B's doc)
        _add_ready_doc(
            db,
            ws_b_id,
            "ws_b_genetics.txt",
            [(1, "Genetic Algorithms\nCrossover and mutation operators evolve candidate populations.")],
        )
        tree_b = service.build_mind_map(ws_b_id, db, user_id=LOCAL_USER_ID)
        assert tree_b.source_document_count == 1
        assert tree_b.source_document_names == ["ws_b_genetics.txt"]
        assert not any("Tabu" in n.label for n in tree_b.nodes)

    finally:
        # Clean up isolated test workspaces
        for wid in (ws_a_id, ws_b_id):
            ws = db.query(Workspace).filter(Workspace.id == wid).first()
            if ws:
                db.delete(ws)
        db.commit()
        db.close()
