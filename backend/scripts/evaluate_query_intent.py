"""Standalone Model Evaluation CLI for Knovera Query Intent (Phase 5 C5.5 / C5.6).

Evaluates any serialized query intent model artifact against dev or test splits
and outputs performance tables and classification reports.
"""

import argparse
from pathlib import Path
import time
from typing import Any, Dict

from backend.app.ml.query_intent.artifacts import load_model_artifact
from backend.app.ml.query_intent.metrics import (
    calculate_classification_metrics,
    format_classification_report_table,
)
from backend.app.ml.query_intent.taxonomy import TaxonomyRegistry
from backend.scripts.prepare_query_intent_dataset import load_jsonl


def evaluate_model(
    model_dir: Path,
    dataset_path: Path,
    split_name: str,
) -> Dict[str, Any]:
    print("=" * 70)
    print(f"EVALUATING MODEL ARTIFACT ON '{split_name.upper()}' SPLIT")
    print(f"Artifact Directory: {model_dir}")
    print(f"Dataset Path:       {dataset_path}")
    print("=" * 70)

    pipeline, manifest = load_model_artifact(model_dir)
    records = load_jsonl(dataset_path)

    X = [r["normalized_text"] for r in records]
    y = [r["intent"] for r in records]
    all_categories = sorted(TaxonomyRegistry.list_category_ids())

    start = time.perf_counter()
    y_pred = list(pipeline.predict(X))
    duration_ms = (time.perf_counter() - start) * 1000.0

    metrics = calculate_classification_metrics(y, y_pred, labels=all_categories)
    metrics["timing"] = {
        "predict_duration_ms": round(duration_ms, 2),
        "per_query_predict_ms": round(duration_ms / len(X), 3),
    }

    print(f"Model ID:     {manifest.get('model_id')}")
    print(f"Model Type:   {manifest.get('model_type')}")
    print(f"Total Queries: {len(X)}")
    print(f"Accuracy:     {metrics['accuracy']:.4f}")
    print(f"Macro F1:     {metrics['macro_f1']:.4f}")
    print(f"Macro P/R:    {metrics['macro_precision']:.4f} / {metrics['macro_recall']:.4f}")
    print(f"Weighted F1:  {metrics['weighted_f1']:.4f}")
    print(f"Latency:      {duration_ms:.2f} ms ({duration_ms / len(X):.3f} ms/query)\n")

    print(format_classification_report_table(metrics))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Query Intent Model Artifact")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("models/query_intent/selected_model"),
        help="Directory containing model.joblib and manifest.json",
    )
    parser.add_argument(
        "--split",
        type=str,
        choices=["dev", "test"],
        default="dev",
        help="Dataset split to evaluate",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("data/query_intent/splits"),
        help="Directory containing split jsonl files",
    )
    args = parser.parse_args()

    split_file = args.dataset_dir / f"{args.split}.jsonl"
    evaluate_model(
        model_dir=args.model_dir,
        dataset_path=split_file,
        split_name=args.split,
    )


if __name__ == "__main__":
    main()
