"""Comprehensive End-to-End Test for Topic Discovery Pipeline (Phase 6 C6.1–C6.6)."""

import uuid
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.core.auth import create_access_token
from backend.app.main import app
from backend.app.ml.topic_clustering import (
    ChunkEmbeddingService,
    ClusteringDatasetManager,
    ClusterSelectionService,
    KMeansTopicClusterer,
    TopicPersistenceService,
)
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.rag.embeddings.fake_provider import DeterministicFakeEmbeddingProvider


def test_full_topic_discovery_end_to_end_journey(db_session, tmp_path, test_client):
    # 1. Setup User and Workspace
    user = User(
        id=uuid.uuid4(),
        email=f"researcher_{uuid.uuid4().hex[:6]}@knovera.ai",
        password_hash="hashed_pw",
        display_name="Dr. Jane Doe",
        status="active",
    )
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name="Biophysics and Quantum Computing",
    )
    db_session.add_all([user, ws])
    db_session.flush()

    # 2. Add Documents and Chunks across 2 thematic categories
    doc1 = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="quantum_algorithms.pdf",
        storage_key=f"doc_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=4000,
        sha256="1" * 64,
        processing_status="completed",
    )
    doc2 = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="molecular_biophysics.pdf",
        storage_key=f"doc_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=4000,
        sha256="2" * 64,
        processing_status="completed",
    )
    db_session.add_all([doc1, doc2])
    db_session.flush()

    quantum_texts = [
        "Shor's quantum algorithm for prime factorization of large integers.",
        "Grover's search algorithm provides quadratic speedup for unstructured databases.",
        "Quantum error correction using surface codes and fault-tolerant qubits.",
        "Quantum phase estimation and Hamiltonian simulation algorithms.",
        "Variational quantum eigensolver for ground state energy estimation.",
        "Quantum supremacy demonstration with random circuit sampling.",
        "Quantum teleportation protocol using Einstein Podolsky Rosen pairs.",
        "Decoherence mitigation in superconducting transmon qubits.",
        "Quantum key distribution and BB84 cryptography protocol.",
        "Adiabatic quantum computation and quantum annealing architectures.",
    ]
    bio_texts = [
        "Protein folding kinetics and free energy landscape theory.",
        "AlphaFold deep learning architecture for protein structure prediction.",
        "Cryo-electron microscopy single particle reconstruction of ribosomes.",
        "Molecular dynamics simulation of lipid bilayer membrane transport.",
        "Enzyme catalysis mechanisms and transition state stabilization.",
        "Allosteric regulation of hemoglobin oxygen binding cooperativity.",
        "Fluorescence resonance energy transfer for single molecule dynamics.",
        "X-ray crystallography diffraction phasing and electron density maps.",
        "Intrinsically disordered proteins and phase separation in organelles.",
        "Thermodynamics of ligand binding affinities and isothermal titration.",
    ]

    chunks = []
    for idx, text in enumerate(quantum_texts):
        chunks.append(
            DocumentChunk(
                id=uuid.uuid4(),
                workspace_id=ws.id,
                document_id=doc1.id,
                chunk_index=idx,
                content=text,
                content_hash=f"q_{idx:062x}",
                parser_version="v1",
                cleaning_version="v1",
                chunking_version="v1",
            )
        )
    for idx, text in enumerate(bio_texts):
        chunks.append(
            DocumentChunk(
                id=uuid.uuid4(),
                workspace_id=ws.id,
                document_id=doc2.id,
                chunk_index=idx,
                content=text,
                content_hash=f"b_{idx:062x}",
                parser_version="v1",
                cleaning_version="v1",
                chunking_version="v1",
            )
        )

    db_session.add_all(chunks)
    db_session.commit()

    # 3. C6.1: Chunk Extraction & Normalized Embeddings
    fake_provider = DeterministicFakeEmbeddingProvider(dimension=384)
    embedding_service = ChunkEmbeddingService(embedding_provider=fake_provider)

    extracted = embedding_service.extract_workspace_chunks(db_session, ws.id)
    assert len(extracted) == 20

    records, embeddings = embedding_service.generate_chunk_embeddings(extracted, reuse_chroma=False)
    assert embeddings.shape == (20, 384)
    assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-4)

    # 4. C6.2: Snapshot Creation & Validation
    snap_mgr = ClusteringDatasetManager(base_dir=tmp_path / "snapshots")
    snap_dir = snap_mgr.create_snapshot(
        workspace_id=ws.id,
        records=records,
        embeddings=embeddings,
        snapshot_id="snap_e2e_full",
    )

    # 5. C6.4: K Selection & Silhouette Analysis
    sel_service = ClusterSelectionService(
        dataset_manager=snap_mgr,
        eval_output_dir=tmp_path / "eval",
    )
    report = sel_service.evaluate_snapshot(snap_dir, candidate_k_list=[2, 3, 4, 5])
    assert report.recommended_k in [2, 3, 4, 5]
    assert report.selection_status in ("conclusive", "requires_review")

    # 6. Fit Final Model with Recommended K
    chosen_k = report.recommended_k or 2
    clusterer = KMeansTopicClusterer(random_state=42)
    model = clusterer.fit_kmeans(embeddings, k=chosen_k)
    assignments, stats_map = clusterer.extract_cluster_details(model, embeddings, records)

    eval_k = clusterer.evaluate_candidate_k(embeddings, candidate_k=[chosen_k])
    model_dir = clusterer.save_model(
        model=model,
        snapshot_id=report.snapshot_id,
        workspace_id=ws.id,
        output_dir=tmp_path / "models",
        assignments=assignments,
        stats_map=stats_map,
        metrics=eval_k.candidate_k_evaluations[0],
        model_version=f"kmeans_final_k{chosen_k}",
    )

    # 7. C6.5 & C6.6: Label Clusters and Persist to PostgreSQL
    persist_service = TopicPersistenceService(dataset_manager=snap_mgr)
    run = persist_service.persist_clustering_results(
        session=db_session,
        workspace_id=ws.id,
        snapshot_dir=snap_dir,
        model_dir=model_dir,
        created_by_user_id=user.id,
        activate=True,
    )

    assert run.is_active is True
    assert run.status == "completed"

    # 8. Test Authenticated Read API Endpoints
    token = create_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    client = test_client
    # GET /api/v1/workspaces/{id}/topics
    resp_topics = client.get(f"/api/v1/workspaces/{ws.id}/topics", headers=headers)
    assert resp_topics.status_code == 200
    topics_json = resp_topics.json()
    assert len(topics_json) == chosen_k

    first_topic = topics_json[0]
    assert "id" in first_topic
    assert "label" in first_topic
    assert len(first_topic["label"]) > 0
    assert first_topic["label_source"] == "keyword_based"
    assert first_topic["chunk_count"] > 0

    # GET /api/v1/workspaces/{id}/topic-runs
    resp_runs = client.get(f"/api/v1/workspaces/{ws.id}/topic-runs", headers=headers)
    assert resp_runs.status_code == 200
    runs_json = resp_runs.json()
    assert len(runs_json) == 1
    assert runs_json[0]["id"] == str(run.id)
    assert runs_json[0]["is_active"] is True

    # GET /api/v1/workspaces/{id}/topics/{topic_id}/chunks
    topic_id = first_topic["id"]
    resp_chunks = client.get(
        f"/api/v1/workspaces/{ws.id}/topics/{topic_id}/chunks?page=1&page_size=10",
        headers=headers,
    )
    assert resp_chunks.status_code == 200
    chunks_json = resp_chunks.json()
    assert chunks_json["total"] > 0
    assert len(chunks_json["items"]) > 0
    assert "content_preview" in chunks_json["items"][0]
    assert "distance_to_centroid" in chunks_json["items"][0]

    # Workspace Multi-Tenant Security Check: Foreign user gets 401 or 404
    foreign_user_id = uuid.uuid4()
    foreign_token = create_access_token(foreign_user_id)
    resp_foreign = client.get(
        f"/api/v1/workspaces/{ws.id}/topics",
        headers={"Authorization": f"Bearer {foreign_token}"},
    )
    assert resp_foreign.status_code in (401, 404)
