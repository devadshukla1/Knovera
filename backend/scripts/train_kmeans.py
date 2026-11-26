"""CLI script to train and persist a K-Means topic model on a dataset snapshot."""

import argparse
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.ml.topic_clustering import (
    ClusteringDatasetManager,
    KMeansTopicClusterer,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train and serialize a K-Means topic clustering model on a dataset snapshot."
    )
    parser.add_argument(
        "--snapshot-dir",
        type=str,
        required=True,
        help="Path to snapshot directory containing embeddings.npy, records.jsonl, and manifest.json",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="Number of clusters K to train. If omitted, runs evaluation grid and picks recommended K.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models/topic_clustering",
        help="Output directory to save model artifacts.",
    )
    parser.add_argument(
        "--model-version",
        type=str,
        default=None,
        help="Custom version name for saved model directory.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for KMeans initialization (default: 42)",
    )
    parser.add_argument(
        "--n-init",
        type=int,
        default=20,
        help="Number of KMeans initializations (default: 20)",
    )

    args = parser.parse_args()

    snapshot_path = Path(args.snapshot_dir)
    if not snapshot_path.exists():
        print(f"Error: Snapshot directory '{snapshot_path}' not found.", file=sys.stderr)
        return 1

    try:
        manager = ClusteringDatasetManager()
        manifest, records, embeddings = manager.load_snapshot(snapshot_path, validate=True)
        ws_id = uuid.UUID(manifest.workspace_id)

        clusterer = KMeansTopicClusterer(
            random_state=args.random_state,
            n_init=args.n_init,
        )

        chosen_k = args.k
        if chosen_k is None:
            print("No --k provided; running candidate K evaluation...")
            eval_result = clusterer.evaluate_candidate_k(embeddings)
            chosen_k = eval_result.recommended_k
            if chosen_k is None:
                raise ValueError("Could not determine recommended K from candidate evaluation.")
            print(f"Selected recommended K={chosen_k}")

        print(f"Fitting KMeans(k={chosen_k}, n_init={args.n_init}, random_state={args.random_state})...")
        model = clusterer.fit_kmeans(embeddings, k=chosen_k)

        # Compute metrics for chosen K
        eval_result = clusterer.evaluate_candidate_k(embeddings, candidate_k=[chosen_k])
        metrics = eval_result.candidate_k_evaluations[0]

        assignments, stats_map = clusterer.extract_cluster_details(
            model=model,
            X=embeddings,
            records=records,
            top_n_representative=5,
        )

        saved_path = clusterer.save_model(
            model=model,
            snapshot_id=manifest.snapshot_id,
            workspace_id=ws_id,
            output_dir=Path(args.output_dir) / manifest.snapshot_id,
            assignments=assignments,
            stats_map=stats_map,
            metrics=metrics,
            model_version=args.model_version,
        )

        print("\n=== K-Means Model Trained and Persisted ===")
        print(f"Saved Path       : {saved_path}")
        print(f"Clusters (K)     : {chosen_k}")
        print(f"Inertia (WCSS)   : {metrics.inertia:.2f}")
        if metrics.silhouette_euclidean is not None:
            print(f"Silhouette (Euc) : {metrics.silhouette_euclidean:.4f}")
        if metrics.davies_bouldin is not None:
            print(f"Davies-Bouldin   : {metrics.davies_bouldin:.4f}")
        if metrics.calinski_harabasz is not None:
            print(f"Calinski-Harabasz: {metrics.calinski_harabasz:.2f}")

        print("\nCluster Breakdown:")
        for c, s in stats_map.items():
            print(f"  Cluster {c}: {s.size} chunks ({s.proportion * 100:.1f}%), mean dist: {s.mean_distance:.4f}, representative: {len(s.representative_chunk_ids)}")

        return 0

    except Exception as exc:
        print(f"Error during K-Means training: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
