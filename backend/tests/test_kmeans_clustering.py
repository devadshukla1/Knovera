"""Unit tests for KMeansTopicClusterer (Phase 6 C6.3)."""

import uuid
from pathlib import Path
import numpy as np
import pytest
from sklearn.datasets import make_blobs

from backend.app.ml.topic_clustering.kmeans import KMeansTopicClusterer
from backend.app.ml.topic_clustering.schemas import (
    ClusteringChunkRecord,
    KMeansMetrics,
)


@pytest.fixture
def synthetic_clusters():
    # Create 3 well-separated isotropic Gaussian blobs in 384 dimensions
    X_raw, y_true = make_blobs(
        n_samples=60,
        n_features=384,
        centers=3,
        cluster_std=1.5,
        random_state=42,
    )
    # L2 normalize
    X = X_raw / np.linalg.norm(X_raw, axis=1, keepdims=True)
    X = X.astype(np.float32)

    ws_id = str(uuid.uuid4())
    records = []
    for i in range(60):
        records.append(
            ClusteringChunkRecord(
                chunk_id=str(uuid.uuid4()),
                document_id=str(uuid.uuid4()),
                workspace_id=ws_id,
                chunk_index=i,
                page_number=1,
                token_count=100,
                content_hash=f"{i:064x}",
                text_preview=f"Blob sample {i} true cluster {y_true[i]}",
            )
        )
    return ws_id, records, X, y_true


def test_kmeans_deterministic_reproducibility(synthetic_clusters):
    ws_id, records, X, _ = synthetic_clusters
    clusterer1 = KMeansTopicClusterer(random_state=42)
    clusterer2 = KMeansTopicClusterer(random_state=42)

    model1 = clusterer1.fit_kmeans(X, k=3)
    model2 = clusterer2.fit_kmeans(X, k=3)

    assert np.array_equal(model1.labels_, model2.labels_)
    assert np.allclose(model1.cluster_centers_, model2.cluster_centers_)
    assert model1.inertia_ == model2.inertia_


def test_kmeans_evaluate_candidate_k(synthetic_clusters):
    ws_id, records, X, _ = synthetic_clusters
    clusterer = KMeansTopicClusterer(random_state=42)

    result = clusterer.evaluate_candidate_k(X, candidate_k=[2, 3, 4, 5])

    assert len(result.candidate_k_evaluations) == 4
    for ev in result.candidate_k_evaluations:
        assert ev.inertia > 0
        assert ev.silhouette_euclidean is not None
        assert -1.0 <= ev.silhouette_euclidean <= 1.0
        assert ev.silhouette_cosine is not None
        assert -1.0 <= ev.silhouette_cosine <= 1.0
        assert ev.davies_bouldin is not None
        assert ev.davies_bouldin >= 0.0
        assert ev.calinski_harabasz is not None
        assert ev.calinski_harabasz > 0.0

    # For 3 well-separated blobs, recommended K should select K=3
    assert result.recommended_k == 3
    assert "selection_strategy" in result.evaluation_summary


def test_kmeans_extract_cluster_details(synthetic_clusters):
    ws_id, records, X, _ = synthetic_clusters
    clusterer = KMeansTopicClusterer(random_state=42)
    model = clusterer.fit_kmeans(X, k=3)

    assignments, stats_map = clusterer.extract_cluster_details(
        model=model,
        X=X,
        records=records,
        top_n_representative=5,
    )

    assert len(assignments) == 60
    assert len(stats_map) == 3

    # Check stats for each cluster
    total_size = sum(s.size for s in stats_map.values())
    assert total_size == 60

    total_prop = sum(s.proportion for s in stats_map.values())
    assert pytest.approx(total_prop, rel=1e-2) == 1.0

    representative_count = sum(1 for a in assignments if a.is_representative)
    # 3 clusters * 5 representative chunks = 15
    assert representative_count == 15

    for c in range(3):
        s = stats_map[c]
        assert len(s.representative_chunk_ids) == 5
        assert s.min_distance <= s.mean_distance <= s.max_distance


def test_kmeans_model_save_and_load(tmp_path, synthetic_clusters):
    ws_id, records, X, _ = synthetic_clusters
    clusterer = KMeansTopicClusterer(random_state=42)
    model = clusterer.fit_kmeans(X, k=3)

    assignments, stats_map = clusterer.extract_cluster_details(
        model=model,
        X=X,
        records=records,
        top_n_representative=5,
    )

    metrics = KMeansMetrics(
        k=3,
        inertia=float(model.inertia_),
        silhouette_euclidean=0.65,
        silhouette_cosine=0.62,
        davies_bouldin=0.55,
        calinski_harabasz=145.2,
    )

    saved_dir = clusterer.save_model(
        model=model,
        snapshot_id="snap_test_01",
        workspace_id=uuid.UUID(ws_id),
        output_dir=tmp_path,
        assignments=assignments,
        stats_map=stats_map,
        metrics=metrics,
        model_version="kmeans_k3_test",
    )

    assert (saved_dir / "kmeans_model.joblib").exists()
    assert (saved_dir / "centroids.npy").exists()
    assert (saved_dir / "assignments.jsonl").exists()
    assert (saved_dir / "cluster_statistics.json").exists()
    assert (saved_dir / "manifest.json").exists()

    loaded_model, manifest, centroids, loaded_stats, loaded_assigns = (
        KMeansTopicClusterer.load_model(saved_dir)
    )

    assert manifest.k == 3
    assert manifest.model_version == "kmeans_k3_test"
    assert manifest.workspace_id == ws_id
    assert loaded_model.n_clusters == 3
    assert np.allclose(centroids, model.cluster_centers_)
    assert len(loaded_assigns) == len(assignments)
    assert len(loaded_stats) == 3
