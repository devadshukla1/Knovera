"""Tests for Topic Discovery & Explorer REST APIs (Phase 6 C6.7)."""

from datetime import datetime, timezone
import uuid
import pytest
from starlette.testclient import TestClient

from backend.app.core.auth import create_access_token
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.topic import Topic
from backend.app.models.topic_assignment import TopicAssignment
from backend.app.models.topic_clustering_run import TopicClusteringRun
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


@pytest.fixture
def topic_test_fixture(db_session):
    """Sets up a complete workspace with documents, chunks, clustering runs, topics, and assignments."""
    now = datetime.now(timezone.utc)

    # 1. User & Workspaces
    owner = User(
        id=uuid.uuid4(),
        email=f"owner_{uuid.uuid4().hex[:8]}@knovera.test",
        password_hash="hashed_test_password",
        display_name="Test Owner",
        status="active",
    )
    foreign_user = User(
        id=uuid.uuid4(),
        email=f"foreign_{uuid.uuid4().hex[:8]}@knovera.test",
        password_hash="hashed_test_password",
        display_name="Foreign User",
        status="active",
    )
    db_session.add_all([owner, foreign_user])
    db_session.flush()

    ws = Workspace(
        id=uuid.uuid4(),
        name="Topic Discovery Lab",
        owner_user_id=owner.id,
        created_at=now,
    )
    foreign_ws = Workspace(
        id=uuid.uuid4(),
        name="Foreign Space",
        owner_user_id=foreign_user.id,
        created_at=now,
    )
    db_session.add_all([ws, foreign_ws])
    db_session.flush()

    # 2. Documents
    doc1 = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=owner.id,
        original_filename="IR_Deep_Dive.pdf",
        storage_key=f"storage_{uuid.uuid4().hex}",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=10240,
        sha256="doc1_hash_abc",
        processing_status="completed",
        chunk_count=3,
        created_at=now,
    )
    doc2 = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=owner.id,
        original_filename="Neural_Reranking.pdf",
        storage_key=f"storage_{uuid.uuid4().hex}",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=8192,
        sha256="doc2_hash_def",
        processing_status="completed",
        chunk_count=2,
        created_at=now,
    )
    # Soft-deleted document
    doc_deleted = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=owner.id,
        original_filename="Old_Obsolete.pdf",
        storage_key=f"storage_{uuid.uuid4().hex}",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=4096,
        sha256="doc3_hash_del",
        processing_status="completed",
        chunk_count=1,
        deleted_at=now,
        created_at=now,
    )
    db_session.add_all([doc1, doc2, doc_deleted])
    db_session.flush()

    # 3. Document Chunks
    c1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc1.id,
        chunk_index=0,
        content="BM25 is a probabilistic lexical ranking algorithm evaluating term frequency and inverse document frequency.",
        content_hash="hash_c1",
        page_start=1,
        page_end=1,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    c2 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc1.id,
        chunk_index=1,
        content="TF-IDF constructs sparse vector spaces for text queries with cosine similarity matching.",
        content_hash="hash_c2",
        page_start=2,
        page_end=2,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    c3 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc2.id,
        chunk_index=0,
        content="Cross-encoder models perform full attention between query and candidate passages to score relevance.",
        content_hash="hash_c3",
        page_start=1,
        page_end=1,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    c_deleted = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc_deleted.id,
        chunk_index=0,
        content="This obsolete chunk belongs to a soft-deleted document and must never leak.",
        content_hash="hash_del",
        page_start=1,
        page_end=1,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    db_session.add_all([c1, c2, c3, c_deleted])
    db_session.flush()

    # 4. Clustering Runs (Old Inactive Run + New Active Run)
    old_run = TopicClusteringRun(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        snapshot_id="snap_20261101_v1",
        status="completed",
        algorithm="kmeans",
        model_version="kmeans_v1_k2",
        embedding_model_id="all-MiniLM-L6-v2",
        embedding_dimension=384,
        k=2,
        configuration={"n_init": 10},
        evaluation_metrics={"silhouette": 0.45},
        selection_metadata={"rationale": "initial"},
        corpus_snapshot_hash="hash_old_run",
        created_at=now,
        completed_at=now,
        is_active=False,
    )
    active_run = TopicClusteringRun(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        snapshot_id="snap_20261107_v2",
        status="completed",
        algorithm="kmeans",
        model_version="kmeans_v1_k2",
        embedding_model_id="all-MiniLM-L6-v2",
        embedding_dimension=384,
        k=2,
        configuration={"n_init": 20, "random_state": 42},
        evaluation_metrics={"silhouette": 0.68, "calinski_harabasz": 142.5},
        selection_metadata={"status": "conclusive", "rationale": "High silhouette separation"},
        corpus_snapshot_hash="hash_active_run",
        created_at=now,
        completed_at=now,
        is_active=True,
    )
    db_session.add_all([old_run, active_run])
    db_session.flush()

    # 5. Topics for Active Run
    topic_lexical = Topic(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        clustering_run_id=active_run.id,
        cluster_key="cluster_0",
        label="Lexical Retrieval & Indexing",
        description="Techniques covering BM25 ranking and TF-IDF weighting schemes.",
        label_source="keyword_based",
        label_status="approved",
        keywords=[
            {"term": "bm25", "score": 0.85},
            {"term": "tf-idf", "score": 0.72},
            {"term": "probabilistic", "score": 0.54},
        ],
        representative_chunk_ids=[str(c1.id)],
        cluster_statistics={"size": 2, "mean_distance": 0.28},
        created_at=now,
        updated_at=now,
    )
    topic_neural = Topic(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        clustering_run_id=active_run.id,
        cluster_key="cluster_1",
        label="Neural Reranking & Cross-Encoders",
        description="Transformer-based scoring of query-candidate pairs with full cross-attention.",
        label_source="llm_assisted",
        label_status="suggested",
        keywords=[
            {"term": "cross-encoder", "score": 0.91},
            {"term": "transformer", "score": 0.78},
            {"term": "reranking", "score": 0.65},
        ],
        representative_chunk_ids=[str(c3.id)],
        cluster_statistics={"size": 1, "mean_distance": 0.15},
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([topic_lexical, topic_neural])
    db_session.flush()

    # 6. Topic Assignments
    a1 = TopicAssignment(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        clustering_run_id=active_run.id,
        topic_id=topic_lexical.id,
        chunk_id=c1.id,
        document_id=doc1.id,
        distance_to_centroid=0.12,
        is_representative=True,
        assigned_at=now,
    )
    a2 = TopicAssignment(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        clustering_run_id=active_run.id,
        topic_id=topic_lexical.id,
        chunk_id=c2.id,
        document_id=doc1.id,
        distance_to_centroid=0.34,
        is_representative=False,
        assigned_at=now,
    )
    a3 = TopicAssignment(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        clustering_run_id=active_run.id,
        topic_id=topic_neural.id,
        chunk_id=c3.id,
        document_id=doc2.id,
        distance_to_centroid=0.15,
        is_representative=True,
        assigned_at=now,
    )
    # Assignment on soft-deleted document
    a_del = TopicAssignment(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        clustering_run_id=active_run.id,
        topic_id=topic_lexical.id,
        chunk_id=c_deleted.id,
        document_id=doc_deleted.id,
        distance_to_centroid=0.88,
        is_representative=False,
        assigned_at=now,
    )
    db_session.add_all([a1, a2, a3, a_del])
    db_session.commit()

    return {
        "owner": owner,
        "foreign_user": foreign_user,
        "workspace": ws,
        "foreign_workspace": foreign_ws,
        "doc1": doc1,
        "doc2": doc2,
        "doc_deleted": doc_deleted,
        "active_run": active_run,
        "old_run": old_run,
        "topic_lexical": topic_lexical,
        "topic_neural": topic_neural,
        "chunk1": c1,
        "chunk2": c2,
        "chunk3": c3,
    }


def test_get_topics_paginated_with_active_run(test_client: TestClient, topic_test_fixture):
    """Verifies GET /api/v1/workspaces/{id}/topics with pagination and active run metadata."""
    data = topic_test_fixture
    token = create_access_token(data["owner"].id)
    headers = {"Authorization": f"Bearer {token}"}

    resp = test_client.get(
        f"/api/v1/workspaces/{data['workspace'].id}/topics?page=1&page_size=10",
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()

    assert res_data["total"] == 2
    assert res_data["page"] == 1
    assert res_data["page_size"] == 10
    assert res_data["total_pages"] == 1
    assert res_data["run"] is not None
    assert res_data["run"]["id"] == str(data["active_run"].id)
    assert res_data["run"]["is_active"] is True

    items = res_data["items"]
    assert len(items) == 2

    # Verify topic stats: soft deleted document chunks must not be counted!
    lexical_topic = next(t for t in items if t["cluster_key"] == "cluster_0")
    assert lexical_topic["chunk_count"] == 2  # c1 and c2; c_deleted excluded!
    assert lexical_topic["document_count"] == 1
    assert lexical_topic["label"] == "Lexical Retrieval & Indexing"
    assert len(lexical_topic["keywords"]) == 3


def test_get_topics_search_and_sort(test_client: TestClient, topic_test_fixture):
    """Verifies topic search and sorting criteria."""
    data = topic_test_fixture
    token = create_access_token(data["owner"].id)
    headers = {"Authorization": f"Bearer {token}"}

    # Search matching "cross-encoder" (in keywords/label)
    resp = test_client.get(
        f"/api/v1/workspaces/{data['workspace'].id}/topics?search=cross-encoder&paginate=true",
        headers=headers,
    )
    assert resp.status_code == 200
    res = resp.json()
    assert res["total"] == 1
    assert res["items"][0]["label"] == "Neural Reranking & Cross-Encoders"

    # Search returning empty results
    resp_empty = test_client.get(
        f"/api/v1/workspaces/{data['workspace'].id}/topics?search=quantum_teleportation_xyz&paginate=true",
        headers=headers,
    )
    assert resp_empty.status_code == 200
    assert resp_empty.json()["total"] == 0
    assert len(resp_empty.json()["items"]) == 0

    # Sort by chunk_count ascending
    resp_sort_asc = test_client.get(
        f"/api/v1/workspaces/{data['workspace'].id}/topics?sort_by=chunk_count&sort_order=asc&paginate=true",
        headers=headers,
    )
    assert resp_sort_asc.status_code == 200
    items_asc = resp_sort_asc.json()["items"]
    assert items_asc[0]["chunk_count"] <= items_asc[1]["chunk_count"]


def test_get_topic_runs_paginated_and_run_detail(test_client: TestClient, topic_test_fixture):
    """Verifies GET /api/v1/workspaces/{id}/topic-runs and GET .../{run_id}."""
    data = topic_test_fixture
    token = create_access_token(data["owner"].id)
    headers = {"Authorization": f"Bearer {token}"}

    # Paginated runs list
    resp = test_client.get(
        f"/api/v1/workspaces/{data['workspace'].id}/topic-runs?page=1&page_size=5",
        headers=headers,
    )
    assert resp.status_code == 200
    runs_res = resp.json()
    assert runs_res["total"] == 2
    assert len(runs_res["items"]) == 2

    # Active run detail
    active_id = str(data["active_run"].id)
    resp_detail = test_client.get(
        f"/api/v1/workspaces/{data['workspace'].id}/topic-runs/{active_id}",
        headers=headers,
    )
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["id"] == active_id
    assert detail["algorithm"] == "kmeans"
    assert detail["topic_count"] == 2
    assert detail["total_assignments"] == 4  # total raw assignments in run
    assert detail["is_active"] is True
    assert "silhouette" in detail["evaluation_metrics"]

    # 404 on non-existent run
    resp_404 = test_client.get(
        f"/api/v1/workspaces/{data['workspace'].id}/topic-runs/{uuid.uuid4()}",
        headers=headers,
    )
    assert resp_404.status_code == 404


def test_get_single_topic_detail(test_client: TestClient, topic_test_fixture):
    """Verifies GET /api/v1/workspaces/{id}/topics/{topic_id}."""
    data = topic_test_fixture
    token = create_access_token(data["owner"].id)
    headers = {"Authorization": f"Bearer {token}"}

    topic_id = str(data["topic_lexical"].id)
    resp = test_client.get(
        f"/api/v1/workspaces/{data['workspace'].id}/topics/{topic_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    topic_res = resp.json()
    assert topic_res["id"] == topic_id
    assert topic_res["label"] == "Lexical Retrieval & Indexing"
    assert topic_res["chunk_count"] == 2
    assert topic_res["document_count"] == 1
    assert topic_res["run_summary"] is not None
    assert topic_res["run_summary"]["id"] == str(data["active_run"].id)

    # 404 on missing topic
    resp_404 = test_client.get(
        f"/api/v1/workspaces/{data['workspace'].id}/topics/{uuid.uuid4()}",
        headers=headers,
    )
    assert resp_404.status_code == 404


def test_get_topic_chunks_and_soft_delete_exclusion(test_client: TestClient, topic_test_fixture):
    """Verifies GET /api/v1/workspaces/{id}/topics/{topic_id}/chunks with document title and soft-delete filtering."""
    data = topic_test_fixture
    token = create_access_token(data["owner"].id)
    headers = {"Authorization": f"Bearer {token}"}

    topic_id = str(data["topic_lexical"].id)
    resp = test_client.get(
        f"/api/v1/workspaces/{data['workspace'].id}/topics/{topic_id}/chunks?page=1&page_size=10",
        headers=headers,
    )
    assert resp.status_code == 200
    chunk_res = resp.json()
    assert chunk_res["total"] == 2  # Soft deleted document chunk excluded
    assert len(chunk_res["items"]) == 2

    first_item = chunk_res["items"][0]
    assert first_item["document_title"] == "IR_Deep_Dive.pdf"
    assert "content_preview" in first_item
    assert first_item["distance_to_centroid"] is not None
    assert first_item["is_representative"] is True

    # Test representative_only=true
    resp_rep = test_client.get(
        f"/api/v1/workspaces/{data['workspace'].id}/topics/{topic_id}/chunks?representative_only=true",
        headers=headers,
    )
    assert resp_rep.status_code == 200
    rep_items = resp_rep.json()["items"]
    assert len(rep_items) == 1
    assert rep_items[0]["is_representative"] is True


def test_multitenant_workspace_isolation(test_client: TestClient, topic_test_fixture):
    """Verifies that users cannot access topic data across workspace boundaries."""
    data = topic_test_fixture
    foreign_token = create_access_token(data["foreign_user"].id)
    foreign_headers = {"Authorization": f"Bearer {foreign_token}"}

    # Attempting to access owner's workspace with foreign user credentials
    ws_id = data["workspace"].id
    topic_id = data["topic_lexical"].id
    run_id = data["active_run"].id

    resp_topics = test_client.get(f"/api/v1/workspaces/{ws_id}/topics", headers=foreign_headers)
    assert resp_topics.status_code in (401, 403, 404)

    resp_runs = test_client.get(f"/api/v1/workspaces/{ws_id}/topic-runs", headers=foreign_headers)
    assert resp_runs.status_code in (401, 403, 404)

    resp_run = test_client.get(f"/api/v1/workspaces/{ws_id}/topic-runs/{run_id}", headers=foreign_headers)
    assert resp_run.status_code in (401, 403, 404)

    resp_topic = test_client.get(f"/api/v1/workspaces/{ws_id}/topics/{topic_id}", headers=foreign_headers)
    assert resp_topic.status_code in (401, 403, 404)

    resp_chunks = test_client.get(f"/api/v1/workspaces/{ws_id}/topics/{topic_id}/chunks", headers=foreign_headers)
    assert resp_chunks.status_code in (401, 403, 404)
