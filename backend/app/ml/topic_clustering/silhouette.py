"""Detailed Silhouette Analysis for Knovera Topic Discovery (Phase 6 C6.4).

Provides:
- Euclidean and Cosine silhouette scores.
- Sample-level silhouette analysis.
- Per-cluster cohesion, overlap, and negative silhouette diagnostics.
- Deterministic stratified/cluster-preserving sampling for large datasets.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.metrics import silhouette_samples, silhouette_score

from backend.app.core.logging import get_logger
from backend.app.ml.topic_clustering.schemas import (
    PerClusterSilhouetteStats,
    SilhouetteAnalysisResult,
)

logger = get_logger("knovera.ml.topic_clustering.silhouette")


def compute_silhouette_analysis(
    X: np.ndarray,
    labels: np.ndarray,
    metric: str = "cosine",
    sample_size: Optional[int] = 2000,
    random_state: int = 42,
) -> Optional[SilhouetteAnalysisResult]:
    """Computes comprehensive overall and per-cluster silhouette diagnostics.

    Args:
        X: (N, D) normalized feature matrix.
        labels: (N,) integer cluster assignments.
        metric: 'euclidean' or 'cosine'.
        sample_size: Maximum samples to compute pairwise distances for (if None or N <= sample_size, computes on all).
        random_state: Seed for deterministic sampling.

    Returns:
        SilhouetteAnalysisResult or None if evaluation is invalid (e.g. single cluster or N < 2).
    """
    N = X.shape[0]
    unique_labels = np.unique(labels)
    K = len(unique_labels)

    if K < 2 or N <= K:
        logger.warning(
            "Silhouette analysis requires 2 <= K < N (got K=%d, N=%d)", K, N
        )
        return None

    # Step 1: Sampling for large datasets if needed
    is_sampled = False
    effective_sample_size = N
    eval_X = X
    eval_labels = labels

    if sample_size is not None and N > sample_size and sample_size >= K * 2:
        is_sampled = True
        effective_sample_size = sample_size
        rng = np.random.RandomState(random_state)

        # Stratified deterministic sample: guarantee at least 2 samples per cluster
        sampled_indices: List[int] = []
        cluster_indices_map = {c: np.where(labels == c)[0] for c in unique_labels}

        # First pass: take min(2, len(cluster)) from each cluster
        for c, c_idx in cluster_indices_map.items():
            if len(c_idx) > 0:
                pick_count = min(len(c_idx), 2)
                picked = rng.choice(c_idx, size=pick_count, replace=False)
                sampled_indices.extend(picked.tolist())

        # Second pass: fill remaining quota proportionally
        remaining_quota = sample_size - len(sampled_indices)
        if remaining_quota > 0:
            remaining_pool = np.array(
                [i for i in range(N) if i not in set(sampled_indices)]
            )
            if len(remaining_pool) > 0:
                extra_picked = rng.choice(
                    remaining_pool,
                    size=min(len(remaining_pool), remaining_quota),
                    replace=False,
                )
                sampled_indices.extend(extra_picked.tolist())

        sampled_indices = sorted(sampled_indices)
        eval_X = X[sampled_indices]
        eval_labels = labels[sampled_indices]

    try:
        # Sample-level silhouette values
        sample_scores = silhouette_samples(eval_X, eval_labels, metric=metric)
    except Exception as exc:
        logger.warning("Failed computing silhouette_samples (%s): %s", metric, exc)
        return None

    overall_mean = float(np.mean(sample_scores))
    overall_median = float(np.median(sample_scores))
    overall_min = float(np.min(sample_scores))
    overall_max = float(np.max(sample_scores))
    neg_mask = sample_scores < 0
    negative_count = int(np.sum(neg_mask))
    negative_pct = float(negative_count / len(sample_scores) * 100.0)

    # Per-cluster diagnostics
    per_cluster: Dict[int, PerClusterSilhouetteStats] = {}
    for c in unique_labels:
        c_mask = eval_labels == c
        c_scores = sample_scores[c_mask]
        c_count = int(len(c_scores))

        if c_count == 0:
            continue

        c_mean = float(np.mean(c_scores))
        c_median = float(np.median(c_scores))
        c_min = float(np.min(c_scores))
        c_max = float(np.max(c_scores))
        c_neg = int(np.sum(c_scores < 0))
        c_neg_pct = float(c_neg / c_count * 100.0)
        is_singleton = c_count == 1

        per_cluster[int(c)] = PerClusterSilhouetteStats(
            cluster_id=int(c),
            count=c_count,
            mean_silhouette=round(c_mean, 4),
            median_silhouette=round(c_median, 4),
            min_silhouette=round(c_min, 4),
            max_silhouette=round(c_max, 4),
            negative_count=c_neg,
            negative_percentage=round(c_neg_pct, 2),
            is_singleton=is_singleton,
        )

    return SilhouetteAnalysisResult(
        metric=metric,
        overall_mean=round(overall_mean, 4),
        overall_median=round(overall_median, 4),
        overall_min=round(overall_min, 4),
        overall_max=round(overall_max, 4),
        negative_count=negative_count,
        negative_percentage=round(negative_pct, 2),
        is_sampled=is_sampled,
        sample_size=effective_sample_size,
        per_cluster=per_cluster,
    )
