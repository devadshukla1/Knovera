"""Unit tests for TopicClusteringRepository and TopicPersistenceService (Phase 6 C6.6)."""

import uuid
import numpy as np
import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.ml.topic_clustering import (
    ClusteringChunkRecord,
    ClusteringDatasetManager,
    KMeansTopicClusterer,
    TopicPersistenceError,
    TopicPersistenceService,
)
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.topic import Topic
from backend.app.models.topic_assignment import TopicAssignment
from backend.app.models.topic_clustering_run import TopicClusteringRun
from backend.app.models.workspace import Workspace
from backend.app.repositories.topic_clustering_repository import TopicClusteringRepository


@pytest.fixture
def workspace_with_chunks(db_session):
    user_id = uuid.uuid4()
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user_id,
        name="Persistence Test Workspace",
    )
    db_session.add(ws)
    db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user_id,
        original_filename="test_doc.pdf",
        storage_key=f"test_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=2000,
        sha256="s" * 64,
        processing_status="completed",
    )
    db_session.add(doc)
    db_session.flush()

    chunks = []
    for i in range(10):
        c = DocumentChunk(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            document_id=doc.id,
            chunk_index=i,
            content=f"Sample text chunk content number {i} discussing topic concepts.",
            content_hash=f"{i:064x}",
            parser_version="v1",
            cleaning_version="v1",
            chunking_version="v1",
        )
        chunks.append(c)
    db_session.add_all(chunks)
    db_session.commit()

    return ws, doc, chunks


def test_repository_run_lifecycle_and_active_switching(db_session, workspace_with_chunks):
    ws, _, _ = workspace_with_chunks
    repo = TopicClusteringRepository(db_session)

    # 1. Create Run 1
    run1 = repo.create_clustering_run(
        workspace_id=ws.id,
        snapshot_id="snap_01",
        model_version="kmeans_v1",
        embedding_model_id="test-embed-384",
        embedding_dimension=384,
        k=2,
        corpus_snapshot_hash="hash_01",
    )
    assert run1.is_active is False
    assert run1.status == "running"

    # Activate Run 1
    repo.activate_run(run1.id, ws.id)
    db_session.commit()

    active = repo.get_active_run(ws.id)
    assert active is not None
    assert active.id == run1.id
    assert active.is_active is True

    # 2. Create Run 2
    run2 = repo.create_clustering_run(
        workspace_id=ws.id,
        snapshot_id="snap_02",
        model_version="kmeans_v2",
        embedding_model_id="test-embed-384",
        embedding_dimension=384,
        k=3,
        corpus_snapshot_hash="hash_02",
    )
    # Activate Run 2 -> Run 1 must become inactive!
    repo.activate_run(run2.id, ws.id)
    db_session.commit()

    # Re-fetch Run 1 and Run 2
    db_session.refresh(run1)
    db_session.refresh(run2)

    assert run1.is_active is False
    assert run2.is_active is True

    # Historical runs preserved
    runs = repo.list_runs(ws.id)
    assert len(runs) == 2


def test_repository_unique_constraints(db_session, workspace_with_chunks):
    ws, doc, chunks = workspace_with_chunks
    repo = TopicClusteringRepository(db_session)

    run = repo.create_clustering_run(
        workspace_id=ws.id,
        snapshot_id="snap_uc",
        model_version="kmeans_uc",
        embedding_model_id="test-embed",
        embedding_dimension=384,
        k=2,
        corpus_snapshot_hash="h_uc",
    )

    t1 = Topic(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        clustering_run_id=run.id,
        cluster_key="cluster_0",
        label="First Topic",
    )
    db_session.add(t1)
    db_session.commit()

    # Attempting duplicate cluster_key in same run should fail UniqueConstraint
    t2_dup = Topic(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        clustering_run_id=run.id,
        cluster_key="cluster_0",  # Duplicate key!
        label="Duplicate Topic",
    )
    db_session.add(t2_dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_persistence_service_end_to_end(db_session, workspace_with_chunks, tmp_path):
    ws, doc, chunks = workspace_with_chunks

    # Prepare snapshot
    records = [
        ClusteringChunkRecord(
            chunk_id=str(c.id),
            document_id=str(c.document_id),
            workspace_id=str(ws.id),
            chunk_index=c.chunk_index,
            content_hash=c.content_hash,
            text_preview=c.content[:50],
        )
        for c in chunks
    ]
    raw = np.random.RandomState(42).randn(len(chunks), 384).astype(np.float32)
    embeddings = raw / np.linalg.norm(raw, axis=1, keepdims=True)

    dataset_mgr = ClusteringDatasetManager(base_dir=tmp_path / "snapshots")
    snap_dir = dataset_mgr.create_snapshot(
        workspace_id=ws.id,
        records=records,
        embeddings=embeddings.astype(np.float32),
        snapshot_id="snap_persist_01",
    )

    # Train KMeans
    clusterer = KMeansTopicClusterer(random_state=42)
    model = clusterer.fit_kmeans(embeddings, k=2)
    assignments, stats_map = clusterer.extract_cluster_details(model, embeddings, records)
    eval_res = clusterer.evaluate_candidate_k(embeddings, candidate_k=[2])

    model_dir = clusterer.save_model(
        model=model,
        snapshot_id="snap_persist_01",
        workspace_id=ws.id,
        output_dir=tmp_path / "models",
        assignments=assignments,
        stats_map=stats_map,
        metrics=eval_res.candidate_k_evaluations[0],
        model_version="kmeans_k2_v1",
    )

    # Persist via Service
    service = TopicPersistenceService(dataset_manager=dataset_mgr)
    run = service.persist_clustering_results(
        session=db_session,
        workspace_id=ws.id,
        snapshot_dir=snap_dir,
        model_dir=model_dir,
        activate=True,
    )

    assert run is not None
    assert run.is_active is True
    assert run.status == "completed"

    repo = TopicClusteringRepository(db_session)
    active_topics = repo.get_active_topics(ws.id)
    assert len(active_topics) == 2

    # Verify assignments
    for t in active_topics:
        t_chunks, total = repo.get_topic_chunks(ws.id, t.id)
        assert total > 0
        assert len(t_chunks) == total

    # Test Idempotency: Re-running persistence on same model returns existing run without duplication
    run_again = service.persist_clustering_results(
        session=db_session,
        workspace_id=ws.id,
        snapshot_dir=snap_dir,
        model_dir=model_dir,
        activate=True,
    )
    assert run_again.id == run.id
    topics_after = repo.get_active_topics(ws.id)
    assert len(topics_after) == 2
