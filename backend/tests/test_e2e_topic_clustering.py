"""End-to-end integration test for Knovera Topic Discovery (Phase 6 C6.1, C6.2, C6.3)."""

from datetime import datetime, timezone
from pathlib import Path
import uuid
import numpy as np
import pytest

from backend.app.ml.topic_clustering import (
    ChunkEmbeddingService,
    ClusteringDatasetManager,
    KMeansTopicClusterer,
)
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.workspace import Workspace
from backend.app.rag.embeddings.fake_provider import DeterministicFakeEmbeddingProvider


def test_e2e_topic_clustering_workflow(db_session, tmp_path):
    # 1. Setup Database Workspace & Documents
    user_id = uuid.uuid4()
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user_id,
        name="Topic Discovery Test Workspace",
    )
    db_session.add(ws)
    db_session.flush()

    doc1 = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user_id,
        original_filename="machine_learning.pdf",
        storage_key=f"ml_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=5000,
        sha256="1" * 64,
        processing_status="completed",
    )
    doc2 = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user_id,
        original_filename="quantum_physics.pdf",
        storage_key=f"qp_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=5000,
        sha256="2" * 64,
        processing_status="completed",
    )
    db_session.add_all([doc1, doc2])
    db_session.flush()

    # Create 20 chunks (10 per topic)
    chunks = []
    ml_topics = [
        "Supervised learning algorithms and linear regression",
        "Logistic regression for binary classification",
        "Support vector machines with margin maximization",
        "Decision trees and random forests ensemble methods",
        "Gradient boosting and XGBoost implementations",
        "Neural network backpropagation and gradient descent",
        "Convolutional neural networks for computer vision",
        "Transformer architecture and self-attention mechanism",
        "Recurrent neural networks and LSTM networks",
        "Clustering algorithms including K-Means and DBSCAN",
    ]
    qp_topics = [
        "Quantum superposition and wave function collapse",
        "Schrodinger equation in one dimensional potential well",
        "Quantum entanglement and Einstein Podolsky Rosen paradox",
        "Bell inequalities and non-locality experiments",
        "Heisenberg uncertainty principle in momentum and position",
        "Quantum harmonic oscillator and ladder operators",
        "Pauli exclusion principle and spin angular momentum",
        "Quantum teleportation and quantum state transfer",
        "Quantum computing qubits and quantum gate operations",
        "Decoherence and quantum measurement problem",
    ]

    for idx, text in enumerate(ml_topics):
        chunks.append(
            DocumentChunk(
                id=uuid.uuid4(),
                workspace_id=ws.id,
                document_id=doc1.id,
                chunk_index=idx,
                content=text,
                content_hash=f"ml_{idx:060x}",
                parser_version="v1",
                cleaning_version="v1",
                chunking_version="v1",
            )
        )

    for idx, text in enumerate(qp_topics):
        chunks.append(
            DocumentChunk(
                id=uuid.uuid4(),
                workspace_id=ws.id,
                document_id=doc2.id,
                chunk_index=idx,
                content=text,
                content_hash=f"qp_{idx:060x}",
                parser_version="v1",
                cleaning_version="v1",
                chunking_version="v1",
            )
        )

    db_session.add_all(chunks)
    db_session.commit()

    # 2. C6.1: Extract chunks and generate embeddings
    fake_provider = DeterministicFakeEmbeddingProvider(dimension=384)
    service = ChunkEmbeddingService(embedding_provider=fake_provider)

    extracted_chunks = service.extract_workspace_chunks(db_session, ws.id)
    assert len(extracted_chunks) == 20

    records, embeddings = service.generate_chunk_embeddings(
        chunks=extracted_chunks,
        reuse_chroma=False,
    )
    assert len(records) == 20
    assert embeddings.shape == (20, 384)
    assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-4)

    # 3. C6.2: Create and validate Dataset Snapshot
    snapshot_base = tmp_path / "snapshots"
    manager = ClusteringDatasetManager(base_dir=snapshot_base)
    snapshot_dir = manager.create_snapshot(
        workspace_id=ws.id,
        records=records,
        embeddings=embeddings,
        embedding_model="fake-minilm-384",
        snapshot_id="snap_e2e_001",
    )

    manifest, loaded_records, loaded_embeddings = manager.load_snapshot(
        snapshot_dir, validate=True
    )
    assert manifest.snapshot_id == "snap_e2e_001"
    assert manifest.chunk_count == 20
    assert len(loaded_records) == 20
    assert loaded_embeddings.shape == (20, 384)

    # 4. C6.3: Candidate K Evaluation
    clusterer = KMeansTopicClusterer(random_state=42)
    eval_result = clusterer.evaluate_candidate_k(loaded_embeddings, candidate_k=[2, 3, 4, 5])

    assert len(eval_result.candidate_k_evaluations) == 4
    assert eval_result.recommended_k in [2, 3, 4, 5]
    for m in eval_result.candidate_k_evaluations:
        assert m.inertia > 0
        assert m.silhouette_euclidean is not None

    # 5. C6.3: Train, Extract Details and Save Model
    chosen_k = eval_result.recommended_k
    model = clusterer.fit_kmeans(loaded_embeddings, k=chosen_k)
    assignments, stats_map = clusterer.extract_cluster_details(
        model=model,
        X=loaded_embeddings,
        records=loaded_records,
        top_n_representative=5,
    )

    assert len(assignments) == 20
    assert len(stats_map) == chosen_k

    eval_chosen = clusterer.evaluate_candidate_k(loaded_embeddings, candidate_k=[chosen_k])
    chosen_metrics = eval_chosen.candidate_k_evaluations[0]

    model_base = tmp_path / "models"
    saved_model_dir = clusterer.save_model(
        model=model,
        snapshot_id=manifest.snapshot_id,
        workspace_id=ws.id,
        output_dir=model_base,
        assignments=assignments,
        stats_map=stats_map,
        metrics=chosen_metrics,
        model_version=f"kmeans_e2e_k{chosen_k}",
    )

    # 6. Verify Artifacts on Disk
    reloaded_model, reloaded_manifest, centroids, reloaded_stats, reloaded_assigns = (
        KMeansTopicClusterer.load_model(saved_model_dir)
    )

    assert reloaded_manifest.model_version == f"kmeans_e2e_k{chosen_k}"
    assert reloaded_manifest.k == chosen_k
    assert centroids.shape == (chosen_k, 384)
    assert len(reloaded_assigns) == 20
    assert len(reloaded_stats) == chosen_k
