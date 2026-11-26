"""Unit tests for ClusterSelectionService, Silhouette Analysis, and Stability (Phase 6 C6.4)."""

import json
from pathlib import Path
import numpy as np
import pytest
from sklearn.datasets import make_blobs

from backend.app.ml.topic_clustering.schemas import KSelectionReport
from backend.app.ml.topic_clustering.selection import ClusterSelectionService
from backend.app.ml.topic_clustering.silhouette import compute_silhouette_analysis
from backend.app.ml.topic_clustering.stability import compute_clustering_stability


@pytest.fixture
def synthetic_blob_matrix():
    # 60 samples, 3 well-separated clusters, 384 dimensions
    X_raw, y = make_blobs(n_samples=60, n_features=384, centers=3, cluster_std=1.2, random_state=42)
    # L2 normalize
    X = X_raw / np.linalg.norm(X_raw, axis=1, keepdims=True)
    return X.astype(np.float32), y


def test_silhouette_analysis_euclidean_and_cosine(synthetic_blob_matrix):
    X, y = synthetic_blob_matrix
    euc_res = compute_silhouette_analysis(X, y, metric="euclidean")
    cos_res = compute_silhouette_analysis(X, y, metric="cosine")

    assert euc_res is not None
    assert cos_res is not None
    assert euc_res.metric == "euclidean"
    assert cos_res.metric == "cosine"
    assert 0.0 < euc_res.overall_mean <= 1.0
    assert 0.0 < cos_res.overall_mean <= 1.0
    assert len(euc_res.per_cluster) == 3
    assert len(cos_res.per_cluster) == 3

    for cid, stats in cos_res.per_cluster.items():
        assert stats.count == 20
        assert not stats.is_singleton
        assert stats.min_silhouette <= stats.mean_silhouette <= stats.max_silhouette


def test_silhouette_analysis_sampling_deterministic(synthetic_blob_matrix):
    X, y = synthetic_blob_matrix
    # Evaluate with sample_size=30 (which is smaller than N=60)
    res = compute_silhouette_analysis(X, y, metric="cosine", sample_size=30, random_state=42)

    assert res is not None
    assert res.is_sampled is True
    assert res.sample_size == 30
    assert len(res.per_cluster) == 3


def test_silhouette_analysis_invalid_conditions():
    # Only 1 cluster
    X = np.random.randn(10, 384).astype(np.float32)
    labels = np.zeros(10, dtype=int)
    assert compute_silhouette_analysis(X, labels) is None

    # N <= K
    labels_too_many = np.arange(10)
    assert compute_silhouette_analysis(X, labels_too_many) is None


def test_clustering_stability_ari(synthetic_blob_matrix):
    X, y = synthetic_blob_matrix
    stab = compute_clustering_stability(X, k=3, random_seeds=[42, 43, 44])

    assert stab is not None
    assert stab.random_seeds == [42, 43, 44]
    assert len(stab.pairwise_ari) == 3
    # Well separated blobs should have high ARI stability across seeds
    assert stab.mean_ari > 0.80
    assert 0.0 <= stab.stability_score <= 1.0


def test_cluster_selection_service_insufficient_samples():
    service = ClusterSelectionService()
    tiny_X = np.random.randn(2, 384).astype(np.float32)
    report = service.evaluate_embeddings(
        embeddings=tiny_X,
        snapshot_id="snap_tiny",
        corpus_hash="hash000",
        candidate_k_list=[2, 3],
    )

    assert report.recommended_k is None
    assert report.selection_status == "inconclusive"
    assert "Insufficient sample count" in report.selection_rationale


def test_cluster_selection_service_filters_invalid_candidates(synthetic_blob_matrix):
    X, _ = synthetic_blob_matrix
    service = ClusterSelectionService()
    # 1 is < 2; 100 is >= N (60)
    report = service.evaluate_embeddings(
        embeddings=X,
        snapshot_id="snap_test",
        corpus_hash="hash123",
        candidate_k_list=[1, 2, 3, 4, 100],
    )

    assert "1" in report.invalid_candidates
    assert "100" in report.invalid_candidates
    assert len(report.candidates) == 3  # K=2, 3, 4
    assert report.candidates[0].k == 2
    assert report.candidates[1].k == 3
    assert report.candidates[2].k == 4

    # For 3 blobs, recommended K should be 3
    assert report.recommended_k == 3
    assert report.selection_status == "conclusive"
    assert "Candidate K=3 achieved the highest composite ranking" in report.selection_rationale


def test_cluster_selection_service_report_serialization(tmp_path, synthetic_blob_matrix):
    X, _ = synthetic_blob_matrix
    service = ClusterSelectionService(eval_output_dir=tmp_path)
    report = service.evaluate_embeddings(
        embeddings=X,
        snapshot_id="snap_eval_01",
        corpus_hash="hash_serial",
        candidate_k_list=[2, 3],
    )

    saved_file = tmp_path / "k_selection_snap_eval_01.json"
    assert saved_file.exists()

    with open(saved_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    loaded_report = KSelectionReport(**data)
    assert loaded_report.snapshot_id == "snap_eval_01"
    assert loaded_report.recommended_k == report.recommended_k
