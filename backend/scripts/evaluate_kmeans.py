"""CLI script to evaluate candidate K values across clustering metrics on a dataset snapshot."""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.ml.topic_clustering import (
    ClusteringDatasetManager,
    KMeansTopicClusterer,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate candidate K values on a Knovera clustering dataset snapshot."
    )
    parser.add_argument(
        "--snapshot-dir",
        type=str,
        required=True,
        help="Path to snapshot directory containing embeddings.npy, records.jsonl, and manifest.json",
    )
    parser.add_argument(
        "--candidate-k",
        type=str,
        default="2,3,4,5,6,7,8,10",
        help="Comma-separated candidate K values to evaluate (default: 2,3,4,5,6,7,8,10)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Optional path to save evaluation results as JSON.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for KMeans initialization (default: 42)",
    )

    args = parser.parse_args()

    snapshot_path = Path(args.snapshot_dir)
    if not snapshot_path.exists():
        print(f"Error: Snapshot directory '{snapshot_path}' not found.", file=sys.stderr)
        return 1

    try:
        candidate_k_list = [int(k.strip()) for k in args.candidate_k.split(",") if k.strip()]
    except ValueError:
        print(f"Error: Invalid candidate-k list '{args.candidate_k}'", file=sys.stderr)
        return 1

    try:
        manager = ClusteringDatasetManager()
        manifest, records, embeddings = manager.load_snapshot(snapshot_path, validate=True)

        print(f"\nLoaded snapshot '{manifest.snapshot_id}' with {len(records)} chunks.")
        print(f"Evaluating candidate K: {candidate_k_list} ...\n")

        clusterer = KMeansTopicClusterer(random_state=args.random_state)
        eval_result = clusterer.evaluate_candidate_k(embeddings, candidate_k=candidate_k_list)

        # Print Markdown Table
        print("| K | Inertia | Silhouette (Euclidean) | Silhouette (Cosine) | Davies-Bouldin | Calinski-Harabasz |")
        print("|---|---|---|---|---|---|")
        for m in eval_result.candidate_k_evaluations:
            sil_euc = f"{m.silhouette_euclidean:.4f}" if m.silhouette_euclidean is not None else "N/A"
            sil_cos = f"{m.silhouette_cosine:.4f}" if m.silhouette_cosine is not None else "N/A"
            db = f"{m.davies_bouldin:.4f}" if m.davies_bouldin is not None else "N/A"
            ch = f"{m.calinski_harabasz:.2f}" if m.calinski_harabasz is not None else "N/A"
            print(f"| {m.k} | {m.inertia:.2f} | {sil_euc} | {sil_cos} | {db} | {ch} |")

        print(f"\nRecommended K: {eval_result.recommended_k}")
        print(f"Selection Strategy: {eval_result.evaluation_summary.get('selection_strategy')}")

        if args.output_json:
            out_file = Path(args.output_json)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(eval_result.model_dump_json(indent=2) + "\n")
            print(f"Saved evaluation results to {out_file}")

        return 0

    except Exception as exc:
        print(f"Error during K-Means evaluation: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
