"""Cluster Selection Service and Multi-Criteria Quality Analysis for Knovera (Phase 6 C6.4)."""

import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.ml.topic_clustering.dataset import ClusteringDatasetManager
from backend.app.ml.topic_clustering.schemas import (
    CandidateKEvaluation,
    ClusterSizeDiagnostics,
    KSelectionReport,
)
from backend.app.ml.topic_clustering.silhouette import compute_silhouette_analysis
from backend.app.ml.topic_clustering.stability import compute_clustering_stability

logger = get_logger("knovera.ml.topic_clustering.selection")


class ClusterSelectionService:
    """Service evaluating candidate K values across mathematical clustering metrics."""

    def __init__(
        self,
        dataset_manager: Optional[ClusteringDatasetManager] = None,
        eval_output_dir: Optional[Path] = None,
    ) -> None:
        self.settings = get_settings()
        self.dataset_manager = dataset_manager or ClusteringDatasetManager()
        self.eval_output_dir = eval_output_dir or Path("eval/topic_clustering")

    def parse_candidate_k_list(self, raw_candidates: Optional[str] = None) -> List[int]:
        """Parses comma-separated candidate K configuration into sorted integer list."""
        val = raw_candidates or self.settings.TOPIC_K_CANDIDATE_VALUES
        candidates = []
        for part in val.split(","):
            part_str = part.strip()
            if part_str:
                try:
                    candidates.append(int(part_str))
                except ValueError:
                    continue
        return sorted(list(set(candidates)))

    def evaluate_snapshot(
        self,
        snapshot_dir: Path,
        candidate_k_list: Optional[List[int]] = None,
        sample_size: Optional[int] = None,
    ) -> KSelectionReport:
        """Evaluates candidate K values for a validated clustering dataset snapshot."""
        manifest, records, embeddings = self.dataset_manager.load_snapshot(
            snapshot_dir, validate=True
        )
        return self.evaluate_embeddings(
            embeddings=embeddings,
            snapshot_id=manifest.snapshot_id,
            corpus_hash=manifest.corpus_hash,
            embedding_model=manifest.embedding_model,
            embedding_dim=manifest.embedding_dimension,
            candidate_k_list=candidate_k_list,
            sample_size=sample_size,
        )

    def evaluate_embeddings(
        self,
        embeddings: np.ndarray,
        snapshot_id: str,
        corpus_hash: str,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_dim: int = 384,
        candidate_k_list: Optional[List[int]] = None,
        sample_size: Optional[int] = None,
    ) -> KSelectionReport:
        """Evaluates multiple candidate K values on an embedding matrix."""
        N = embeddings.shape[0]
        configured_candidates = candidate_k_list or self.parse_candidate_k_list()
        effective_sample_size = (
            sample_size
            if sample_size is not None
            else self.settings.TOPIC_SILHOUETTE_METRIC_SAMPLE_SIZE
        )

        valid_candidates: List[int] = []
        invalid_candidates: Dict[str, str] = {}
        warnings: List[str] = []

        if N < 3:
            return KSelectionReport(
                snapshot_id=snapshot_id,
                corpus_snapshot_hash=corpus_hash,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dim,
                normalization="l2",
                candidate_k_values=configured_candidates,
                candidates=[],
                invalid_candidates={"all": f"Corpus has only N={N} chunks (requires at least 3)."},
                recommended_k=None,
                selection_status="inconclusive",
                selection_rationale=f"Insufficient sample count (N={N}) for multi-cluster evaluation.",
                warnings=["Insufficient data for clustering."],
            )

        # Validate candidates: 2 <= K < N
        for k in configured_candidates:
            if k < 2:
                invalid_candidates[str(k)] = f"K={k} is less than minimum allowed K=2."
            elif k >= N:
                invalid_candidates[str(k)] = (
                    f"K={k} is greater than or equal to sample count N={N}."
                )
            else:
                valid_candidates.append(k)

        if not valid_candidates:
            return KSelectionReport(
                snapshot_id=snapshot_id,
                corpus_snapshot_hash=corpus_hash,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dim,
                normalization="l2",
                candidate_k_values=configured_candidates,
                candidates=[],
                invalid_candidates=invalid_candidates,
                recommended_k=None,
                selection_status="inconclusive",
                selection_rationale="No candidate K met validity constraints (2 <= K < N).",
                warnings=["No valid K candidates to evaluate."],
            )

        candidate_evaluations: List[CandidateKEvaluation] = []
        prev_inertia: Optional[float] = None

        stability_seeds = [
            int(s.strip())
            for s in self.settings.TOPIC_STABILITY_RANDOM_SEEDS.split(",")
            if s.strip()
        ]

        for k in valid_candidates:
            start_time = time.perf_counter()
            model = KMeans(
                n_clusters=k,
                init="k-means++",
                n_init=20,
                max_iter=300,
                random_state=self.settings.TOPIC_SILHOUETTE_RANDOM_STATE,
                algorithm="lloyd",
            )
            model.fit(embeddings)
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

            labels = model.labels_
            inertia = float(model.inertia_)

            # Inertia reduction
            inertia_drop = None
            rel_drop = None
            if prev_inertia is not None and prev_inertia > 0:
                inertia_drop = round(prev_inertia - inertia, 2)
                rel_drop = round((prev_inertia - inertia) / prev_inertia, 4)
            prev_inertia = inertia

            # Silhouette analysis
            euc_sil = compute_silhouette_analysis(
                embeddings,
                labels,
                metric="euclidean",
                sample_size=effective_sample_size,
                random_state=self.settings.TOPIC_SILHOUETTE_RANDOM_STATE,
            )
            cos_sil = compute_silhouette_analysis(
                embeddings,
                labels,
                metric="cosine",
                sample_size=effective_sample_size,
                random_state=self.settings.TOPIC_SILHOUETTE_RANDOM_STATE,
            )

            # Additional metrics
            try:
                db_score = round(float(davies_bouldin_score(embeddings, labels)), 4)
            except Exception:
                db_score = None

            try:
                ch_score = round(float(calinski_harabasz_score(embeddings, labels)), 2)
            except Exception:
                ch_score = None

            # Stability
            stability = compute_clustering_stability(
                X=embeddings,
                k=k,
                random_seeds=stability_seeds,
            )

            # Size diagnostics
            unique, counts = np.unique(labels, return_counts=True)
            min_size = int(np.min(counts))
            max_size = int(np.max(counts))
            mean_size = float(np.mean(counts))
            median_size = float(np.median(counts))
            std_size = float(np.std(counts))
            max_prop = float(max_size / N)
            singletons = int(np.sum(counts == 1))
            small_clusters = int(np.sum(counts <= 2))

            size_diag = ClusterSizeDiagnostics(
                total_chunks=N,
                min_size=min_size,
                max_size=max_size,
                mean_size=round(mean_size, 2),
                median_size=round(median_size, 2),
                std_size=round(std_size, 2),
                max_cluster_proportion=round(max_prop, 4),
                singleton_count=singletons,
                very_small_cluster_count=small_clusters,
            )

            if max_prop > 0.70:
                warnings.append(
                    f"K={k}: Largest cluster contains {max_prop * 100:.1f}% of all chunks (high imbalance)."
                )
            if singletons > 0:
                warnings.append(f"K={k}: Contains {singletons} singleton cluster(s).")

            candidate_evaluations.append(
                CandidateKEvaluation(
                    k=k,
                    inertia=round(inertia, 2),
                    inertia_drop=inertia_drop,
                    relative_inertia_drop=rel_drop,
                    duration_ms=duration_ms,
                    euclidean_silhouette=euc_sil,
                    cosine_silhouette=cos_sil,
                    davies_bouldin=db_score,
                    calinski_harabasz=ch_score,
                    stability=stability,
                    size_diagnostics=size_diag,
                )
            )

        # Multi-criteria decision
        recommended_k, status, rationale = self._recommend_k(candidate_evaluations)

        report = KSelectionReport(
            snapshot_id=snapshot_id,
            corpus_snapshot_hash=corpus_hash,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dim,
            normalization="l2",
            candidate_k_values=configured_candidates,
            candidates=candidate_evaluations,
            invalid_candidates=invalid_candidates,
            recommended_k=recommended_k,
            selection_status=status,
            selection_rationale=rationale,
            warnings=list(set(warnings)),
        )

        # Save report JSON
        self.save_report(report)
        return report

    def _recommend_k(
        self,
        candidates: List[CandidateKEvaluation],
    ) -> Tuple[Optional[int], str, str]:
        """Synthesizes multiple criteria to recommend optimal K."""
        if not candidates:
            return None, "inconclusive", "No evaluated candidates available."

        # Filter candidates with valid silhouette
        scored = [
            c
            for c in candidates
            if c.cosine_silhouette is not None
            and c.euclidean_silhouette is not None
            and c.davies_bouldin is not None
            and c.calinski_harabasz is not None
        ]

        if not scored:
            # Fallback to candidate with first non-null
            first_k = candidates[0].k
            return (
                first_k,
                "requires_review",
                f"Metrics were incomplete across candidates; selected candidate K={first_k}.",
            )

        num = len(scored)
        k_values = [c.k for c in scored]

        # 1. Cosine silhouette rank (higher is better)
        cos_sil = [c.cosine_silhouette.overall_mean for c in scored]  # type: ignore
        cos_ranks = np.argsort(np.argsort(cos_sil)) + 1

        # 2. Euclidean silhouette rank (higher is better)
        euc_sil = [c.euclidean_silhouette.overall_mean for c in scored]  # type: ignore
        euc_ranks = np.argsort(np.argsort(euc_sil)) + 1

        # 3. Davies-Bouldin rank (lower is better)
        db = [-c.davies_bouldin for c in scored]  # type: ignore
        db_ranks = np.argsort(np.argsort(db)) + 1

        # 4. Calinski-Harabasz rank (higher is better)
        ch = [c.calinski_harabasz for c in scored]  # type: ignore
        ch_ranks = np.argsort(np.argsort(ch)) + 1

        # 5. Stability rank
        stab = [
            c.stability.stability_score if c.stability else 0.5 for c in scored
        ]
        stab_ranks = np.argsort(np.argsort(stab)) + 1

        # 6. Size balance penalty: penalize excessive max_cluster_proportion and singletons
        balance_scores = []
        for c in scored:
            b = 1.0 - c.size_diagnostics.max_cluster_proportion
            if c.size_diagnostics.singleton_count > 0:
                b -= 0.2 * c.size_diagnostics.singleton_count
            balance_scores.append(b)
        balance_ranks = np.argsort(np.argsort(balance_scores)) + 1

        composite = (
            cos_ranks * 0.30
            + euc_ranks * 0.20
            + db_ranks * 0.20
            + ch_ranks * 0.15
            + stab_ranks * 0.10
            + balance_ranks * 0.05
        )

        best_idx = int(np.argmax(composite))
        best_k = k_values[best_idx]
        best_cand = scored[best_idx]

        status = "conclusive"
        rationale_parts = [
            f"Candidate K={best_k} achieved the highest composite ranking across evaluated criteria.",
            f"Cosine Silhouette: {best_cand.cosine_silhouette.overall_mean:.4f} (Euclidean: {best_cand.euclidean_silhouette.overall_mean:.4f}).",  # type: ignore
            f"Davies-Bouldin: {best_cand.davies_bouldin:.4f}, Calinski-Harabasz: {best_cand.calinski_harabasz:.2f}.",  # type: ignore
        ]
        if best_cand.stability:
            rationale_parts.append(
                f"Cluster partition stability: mean ARI={best_cand.stability.mean_ari:.4f}."
            )

        # Flag requires_review if silhouette is near zero or negative
        if best_cand.cosine_silhouette.overall_mean < 0.05:  # type: ignore
            status = "requires_review"
            rationale_parts.append(
                "Warning: Overall silhouette cohesion is low (< 0.05), indicating semantic overlap."
            )

        return best_k, status, " ".join(rationale_parts)

    def save_report(self, report: KSelectionReport) -> Path:
        """Serializes KSelectionReport to eval/topic_clustering/k_selection_<snapshot_id>.json."""
        self.eval_output_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.eval_output_dir / f"k_selection_{report.snapshot_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2) + "\n")
        logger.info("Saved K selection report to %s", out_path)
        return out_path
