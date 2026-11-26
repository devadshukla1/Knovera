"""Clustering Stability Analysis using Adjusted Rand Index (Phase 6 C6.4)."""

from typing import Dict, List, Optional
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score

from backend.app.core.logging import get_logger
from backend.app.ml.topic_clustering.schemas import StabilityResult

logger = get_logger("knovera.ml.topic_clustering.stability")


def compute_clustering_stability(
    X: np.ndarray,
    k: int,
    random_seeds: Optional[List[int]] = None,
    n_init: int = 20,
    max_iter: int = 300,
    algorithm: str = "lloyd",
) -> Optional[StabilityResult]:
    """Evaluates partition stability across multiple random seeds using Adjusted Rand Index (ARI).

    ARI is label-invariant: it accounts for arbitrary permutations of cluster IDs between runs.
    """
    seeds = random_seeds or [42, 43, 44]
    if len(seeds) < 2:
        return None

    if X.shape[0] < k or k < 2:
        return None

    run_labels: List[np.ndarray] = []
    for s in seeds:
        model = KMeans(
            n_clusters=k,
            init="k-means++",
            n_init=n_init,
            max_iter=max_iter,
            random_state=s,
            algorithm=algorithm,
        )
        model.fit(X)
        run_labels.append(model.labels_)

    pairwise_ari: Dict[str, float] = {}
    ari_values: List[float] = []

    for i in range(len(seeds)):
        for j in range(i + 1, len(seeds)):
            pair_key = f"{seeds[i]}_vs_{seeds[j]}"
            ari = float(adjusted_rand_score(run_labels[i], run_labels[j]))
            pairwise_ari[pair_key] = round(ari, 4)
            ari_values.append(ari)

    mean_ari = float(np.mean(ari_values))
    min_ari = float(np.min(ari_values))

    # Normalized stability score: bounded [0.0, 1.0]
    stability_score = max(0.0, min(1.0, mean_ari))

    return StabilityResult(
        random_seeds=seeds,
        pairwise_ari=pairwise_ari,
        mean_ari=round(mean_ari, 4),
        min_ari=round(min_ari, 4),
        stability_score=round(stability_score, 4),
    )
