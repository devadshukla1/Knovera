"""K-Means Topic Clustering Implementation and Evaluation for Knovera (Phase 6 C6.3).

Implements:
1. Deterministic KMeans with n_init=20, random_state=42, k-means++, lloyd.
2. Candidate K evaluation over candidate K in {2, 3, 4, 5, 6, 7, 8, 10} evaluating
   Inertia, Silhouette (Euclidean & Cosine), Davies-Bouldin, and Calinski-Harabasz.
3. Multi-criteria optimal K selection heuristic.
4. Cluster centroid extraction and top representative chunk identification.
5. Model serialization (kmeans_model.joblib, centroids.npy, assignments.jsonl,
   cluster_statistics.json, manifest.json) and artifact loading.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid
import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)

from backend.app.core.logging import get_logger
from backend.app.ml.topic_clustering.schemas import (
    ClusterAssignment,
    ClusterStats,
    ClusteringChunkRecord,
    KMeansEvaluationResult,
    KMeansMetrics,
    ModelManifest,
)

logger = get_logger("knovera.ml.topic_clustering.kmeans")


class KMeansTopicClusterer:
    """Topic clusterer wrapping scikit-learn KMeans with rigorous evaluation and artifact management."""

    def __init__(
        self,
        random_state: int = 42,
        n_init: int = 20,
        max_iter: int = 300,
        tol: float = 1e-4,
        algorithm: str = "lloyd",
    ) -> None:
        self.random_state = random_state
        self.n_init = n_init
        self.max_iter = max_iter
        self.tol = tol
        self.algorithm = algorithm

    def fit_kmeans(
        self,
        X: np.ndarray,
        k: int,
    ) -> KMeans:
        """Fits a KMeans model with deterministic parameters for a given K.

        Args:
            X: L2-normalized float32 embedding matrix of shape (N, D).
            k: Number of clusters to discover.

        Returns:
            Fitted sklearn.cluster.KMeans instance.
        """
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k}")
        if X.shape[0] < k:
            raise ValueError(
                f"Sample count N={X.shape[0]} is smaller than requested clusters k={k}"
            )

        model = KMeans(
            n_clusters=k,
            init="k-means++",
            n_init=self.n_init,
            max_iter=self.max_iter,
            tol=self.tol,
            random_state=self.random_state,
            algorithm=self.algorithm,
        )
        model.fit(X)
        return model

    def evaluate_candidate_k(
        self,
        X: np.ndarray,
        candidate_k: Optional[List[int]] = None,
    ) -> KMeansEvaluationResult:
        """Evaluates multiple candidate K values on embedding matrix X across clustering metrics.

        Standard evaluation grid: [2, 3, 4, 5, 6, 7, 8, 10] bounded by sample count N.
        """
        N = X.shape[0]
        if N < 3:
            raise ValueError(
                f"At least 3 samples are required to evaluate clustering metrics, got N={N}"
            )

        grid = candidate_k or [2, 3, 4, 5, 6, 7, 8, 10]
        # Filter valid K: 2 <= K <= N - 1 (silhouette requires at least 2 clusters and less than N samples)
        valid_k = sorted(list(set(k for k in grid if 2 <= k < N)))

        if not valid_k:
            raise ValueError(
                f"No eligible candidate K found for N={N} (requires 2 <= K < {N})"
            )

        evaluations: List[KMeansMetrics] = []

        for k in valid_k:
            model = self.fit_kmeans(X, k=k)
            labels = model.labels_
            inertia = float(model.inertia_)

            # Check if all clusters received at least one sample
            unique_labels = len(np.unique(labels))
            if unique_labels < 2:
                logger.warning("K=%d resulted in fewer than 2 distinct clusters", k)
                sil_euc = None
                sil_cos = None
                db_score = None
                ch_score = None
            else:
                try:
                    sil_euc = float(silhouette_score(X, labels, metric="euclidean"))
                except Exception as exc:
                    logger.warning("Failed computing Euclidean silhouette for K=%d: %s", k, exc)
                    sil_euc = None

                try:
                    sil_cos = float(silhouette_score(X, labels, metric="cosine"))
                except Exception as exc:
                    logger.warning("Failed computing Cosine silhouette for K=%d: %s", k, exc)
                    sil_cos = None

                try:
                    db_score = float(davies_bouldin_score(X, labels))
                except Exception as exc:
                    logger.warning("Failed computing Davies-Bouldin for K=%d: %s", k, exc)
                    db_score = None

                try:
                    ch_score = float(calinski_harabasz_score(X, labels))
                except Exception as exc:
                    logger.warning("Failed computing Calinski-Harabasz for K=%d: %s", k, exc)
                    ch_score = None

            evaluations.append(
                KMeansMetrics(
                    k=k,
                    inertia=inertia,
                    silhouette_euclidean=sil_euc,
                    silhouette_cosine=sil_cos,
                    davies_bouldin=db_score,
                    calinski_harabasz=ch_score,
                )
            )

        recommended_k, summary = self._select_recommended_k(evaluations)

        return KMeansEvaluationResult(
            candidate_k_evaluations=evaluations,
            recommended_k=recommended_k,
            evaluation_summary=summary,
        )

    def _select_recommended_k(
        self,
        evaluations: List[KMeansMetrics],
    ) -> Tuple[Optional[int], Dict[str, Any]]:
        """Multi-criteria ranking to recommend the optimal K value.

        Heuristic:
        Combines rank-based scores across valid metrics:
        - Higher Silhouette (Euclidean) -> higher rank
        - Lower Davies-Bouldin -> higher rank
        - Higher Calinski-Harabasz -> higher rank
        Ties are broken by highest Silhouette score.
        """
        if not evaluations:
            return None, {"reason": "No evaluations provided"}

        # Filter evaluations with complete metrics
        complete_evals = [
            e
            for e in evaluations
            if e.silhouette_euclidean is not None
            and e.davies_bouldin is not None
            and e.calinski_harabasz is not None
        ]

        if not complete_evals:
            # Fallback to candidate with best inertia drop or first candidate
            return evaluations[0].k, {"reason": "Metrics incomplete, selected first candidate"}

        num_candidates = len(complete_evals)
        k_list = [e.k for e in complete_evals]

        # Rank silhouette ascending (best gets highest rank: num_candidates)
        sil_vals = [e.silhouette_euclidean for e in complete_evals]  # type: ignore
        sil_ranks = np.argsort(np.argsort(sil_vals)) + 1

        # Rank Davies-Bouldin descending (lower is better, so smallest gets highest rank)
        db_vals = [-e.davies_bouldin for e in complete_evals]  # type: ignore
        db_ranks = np.argsort(np.argsort(db_vals)) + 1

        # Rank Calinski-Harabasz ascending (higher is better)
        ch_vals = [e.calinski_harabasz for e in complete_evals]  # type: ignore
        ch_ranks = np.argsort(np.argsort(ch_vals)) + 1

        composite_scores = sil_ranks * 0.40 + db_ranks * 0.35 + ch_ranks * 0.25
        best_idx = int(np.argmax(composite_scores))
        best_k = k_list[best_idx]

        details = {
            "selected_k": best_k,
            "best_silhouette": float(sil_vals[best_idx]),
            "best_davies_bouldin": float(-db_vals[best_idx]),
            "best_calinski_harabasz": float(ch_vals[best_idx]),
            "composite_scores": {k: float(score) for k, score in zip(k_list, composite_scores)},
            "selection_strategy": "multi_criteria_rank_weighted (40% silhouette, 35% davies_bouldin, 25% calinski_harabasz)",
        }
        return best_k, details

    def extract_cluster_details(
        self,
        model: KMeans,
        X: np.ndarray,
        records: List[ClusteringChunkRecord],
        top_n_representative: int = 5,
    ) -> Tuple[List[ClusterAssignment], Dict[int, ClusterStats]]:
        """Extracts cluster assignments, distance to centroid, statistics, and top representative chunks.

        Representative chunks are defined as the chunks located closest to the cluster
        centroid in Euclidean distance.
        """
        N = X.shape[0]
        K = model.n_clusters
        labels = model.labels_
        centroids = model.cluster_centers_  # shape (K, D)

        if len(records) != N:
            raise ValueError(f"Record count ({len(records)}) does not match X rows ({N})")

        # 1. Compute distances to assigned centroids
        distances = np.zeros(N, dtype=np.float32)
        for i in range(N):
            cluster_id = labels[i]
            centroid = centroids[cluster_id]
            distances[i] = np.linalg.norm(X[i] - centroid)

        # 2. For each cluster, find top representative chunks
        cluster_chunk_indices: Dict[int, List[int]] = {c: [] for c in range(K)}
        for idx, cid in enumerate(labels):
            cluster_chunk_indices[cid].append(idx)

        representative_chunk_ids_by_cluster: Dict[int, List[str]] = {}
        representative_set: set[str] = set()

        stats_map: Dict[int, ClusterStats] = {}

        for c in range(K):
            indices = cluster_chunk_indices[c]
            c_size = len(indices)
            proportion = (c_size / N) if N > 0 else 0.0

            if c_size > 0:
                c_dists = distances[indices]
                min_dist = float(np.min(c_dists))
                mean_dist = float(np.mean(c_dists))
                max_dist = float(np.max(c_dists))

                # Sort by distance ascending
                sorted_idx_in_cluster = np.argsort(c_dists)
                top_indices = [indices[si] for si in sorted_idx_in_cluster[:top_n_representative]]
                top_chunk_ids = [records[ti].chunk_id for ti in top_indices]
                representative_chunk_ids_by_cluster[c] = top_chunk_ids
                for r_cid in top_chunk_ids:
                    representative_set.add(r_cid)
            else:
                min_dist = 0.0
                mean_dist = 0.0
                max_dist = 0.0
                representative_chunk_ids_by_cluster[c] = []

            stats_map[c] = ClusterStats(
                cluster_id=c,
                size=c_size,
                proportion=round(proportion, 4),
                min_distance=round(min_dist, 4),
                mean_distance=round(mean_dist, 4),
                max_distance=round(max_dist, 4),
                representative_chunk_ids=representative_chunk_ids_by_cluster[c],
            )

        # 3. Build ClusterAssignment objects
        assignments: List[ClusterAssignment] = []
        for i in range(N):
            cid = int(labels[i])
            chunk_id = records[i].chunk_id
            assignments.append(
                ClusterAssignment(
                    chunk_id=chunk_id,
                    cluster_id=cid,
                    distance_to_centroid=round(float(distances[i]), 4),
                    is_representative=(chunk_id in representative_set),
                )
            )

        return assignments, stats_map

    def save_model(
        self,
        model: KMeans,
        snapshot_id: str,
        workspace_id: uuid.UUID,
        output_dir: Path,
        assignments: List[ClusterAssignment],
        stats_map: Dict[int, ClusterStats],
        metrics: KMeansMetrics,
        model_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Serializes fitted KMeans model, centroids, assignments, stats, and manifest."""
        k = model.n_clusters
        if model_version is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            model_version = f"kmeans_k{k}_{ts}"

        target_dir = Path(output_dir) / model_version
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. Save model joblib
        joblib_path = target_dir / "kmeans_model.joblib"
        joblib.dump(model, joblib_path)

        # 2. Save centroids.npy
        centroids_path = target_dir / "centroids.npy"
        np.save(centroids_path, model.cluster_centers_.astype(np.float32))

        # 3. Save assignments.jsonl
        assignments_path = target_dir / "assignments.jsonl"
        with open(assignments_path, "w", encoding="utf-8") as f:
            for a in assignments:
                f.write(a.model_dump_json() + "\n")

        # 4. Save cluster_statistics.json
        stats_path = target_dir / "cluster_statistics.json"
        with open(stats_path, "w", encoding="utf-8") as f:
            stats_dict = {str(c): s.model_dump() for c, s in stats_map.items()}
            json.dump(stats_dict, f, indent=2)

        # 5. Save manifest.json
        manifest = ModelManifest(
            model_version=model_version,
            snapshot_id=snapshot_id,
            workspace_id=str(workspace_id),
            k=k,
            random_state=self.random_state,
            n_init=self.n_init,
            max_iter=self.max_iter,
            algorithm=self.algorithm,
            metrics=metrics,
            total_chunks=len(assignments),
            metadata=metadata or {},
        )
        manifest_path = target_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(indent=2) + "\n")

        logger.info("Saved trained K-Means model '%s' to %s", model_version, target_dir)
        return target_dir

    @classmethod
    def load_model(
        cls,
        model_dir: Path,
    ) -> Tuple[KMeans, ModelManifest, np.ndarray, Dict[int, ClusterStats], List[ClusterAssignment]]:
        """Loads a persisted K-Means topic model and all associated artifacts from disk."""
        model_dir = Path(model_dir)
        joblib_path = model_dir / "kmeans_model.joblib"
        centroids_path = model_dir / "centroids.npy"
        assignments_path = model_dir / "assignments.jsonl"
        stats_path = model_dir / "cluster_statistics.json"
        manifest_path = model_dir / "manifest.json"

        for p in [joblib_path, centroids_path, assignments_path, stats_path, manifest_path]:
            if not p.exists():
                raise FileNotFoundError(f"Missing required artifact: {p}")

        model: KMeans = joblib.load(joblib_path)
        centroids = np.load(centroids_path)

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = ModelManifest(**json.load(f))

        stats_map: Dict[int, ClusterStats] = {}
        with open(stats_path, "r", encoding="utf-8") as f:
            stats_raw = json.load(f)
            for k_str, s_dict in stats_raw.items():
                stats_map[int(k_str)] = ClusterStats(**s_dict)

        assignments: List[ClusterAssignment] = []
        with open(assignments_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    assignments.append(ClusterAssignment(**json.loads(line_str)))

        logger.info(
            "Loaded K-Means model '%s' (K=%d, %d chunks) from %s",
            manifest.model_version,
            manifest.k,
            len(assignments),
            model_dir,
        )
        return model, manifest, centroids, stats_map, assignments
