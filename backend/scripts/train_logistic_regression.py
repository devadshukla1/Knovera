"""Training and Hyperparameter Optimization CLI for Logistic Regression (Phase 5 C5.5).

Fits Logistic Regression on training data across a bounded grid of feature types and
regularization values, selects the best configuration on development Macro F1,
and serializes the winning pipeline to models/query_intent/logistic_regression/.
"""

import argparse
from pathlib import Path
import time
from typing import Any, Dict, List

from backend.app.ml.query_intent.artifacts import save_model_artifact
from backend.app.ml.query_intent.features import compute_feature_stats
from backend.app.ml.query_intent.logistic_model import build_logistic_pipeline
from backend.app.ml.query_intent.metrics import (
    calculate_classification_metrics,
    format_classification_report_table,
)
from backend.app.ml.query_intent.taxonomy import TaxonomyRegistry
from backend.scripts.prepare_query_intent_dataset import load_jsonl


def train_and_optimize_logistic_regression(
    train_path: Path = Path("data/query_intent/splits/train.jsonl"),
    dev_path: Path = Path("data/query_intent/splits/dev.jsonl"),
    output_dir: Path = Path("models/query_intent/logistic_regression"),
) -> Dict[str, Any]:
    print("=" * 70)
    print("TRAINING LOGISTIC REGRESSION BASELINE (C5.5)")
    print("=" * 70)

    # 1. Load Datasets
    train_records = load_jsonl(train_path)
    dev_records = load_jsonl(dev_path)

    X_train = [r["normalized_text"] for r in train_records]
    y_train = [r["intent"] for r in train_records]

    X_dev = [r["normalized_text"] for r in dev_records]
    y_dev = [r["intent"] for r in dev_records]

    all_categories = sorted(TaxonomyRegistry.list_category_ids())
    print(f"Loaded {len(X_train)} train queries and {len(X_dev)} dev queries across {len(all_categories)} categories.")

    # 2. Bounded Parameter Grid
    grid = [
        {"feature_type": "combined", "C": 1.0, "class_weight": None},
        {"feature_type": "combined", "C": 10.0, "class_weight": None},
        {"feature_type": "combined", "C": 0.1, "class_weight": None},
        {"feature_type": "combined", "C": 1.0, "class_weight": "balanced"},
        {"feature_type": "word", "C": 1.0, "class_weight": None},
        {"feature_type": "word", "C": 10.0, "class_weight": None},
        {"feature_type": "char", "C": 1.0, "class_weight": None},
    ]

    print(f"\nEvaluating {len(grid)} configurations on development split:")
    print(f"{'#':<3} | {'Features':<10} | {'C':<5} | {'ClassWeight':<12} | {'Dev Acc':<8} | {'Dev Macro F1':<12} | {'Duration'}")
    print("-" * 70)

    best_config = None
    best_macro_f1 = -1.0
    best_metrics = None
    best_pipeline = None
    best_train_duration = 0.0

    for idx, cfg in enumerate(grid, 1):
        pipeline = build_logistic_pipeline(
            feature_type=cfg["feature_type"],  # type: ignore
            C=cfg["C"],
            class_weight=cfg["class_weight"],
        )

        start = time.perf_counter()
        pipeline.fit(X_train, y_train)
        duration = time.perf_counter() - start

        # Predict on Dev
        y_pred = pipeline.predict(X_dev)
        metrics = calculate_classification_metrics(y_dev, y_pred, labels=all_categories)

        acc = metrics["accuracy"]
        macro_f1 = metrics["macro_f1"]
        cw_str = str(cfg["class_weight"])

        print(
            f"{idx:<3} | {cfg['feature_type']:<10} | {cfg['C']:<5.1f} | "
            f"{cw_str:<12} | {acc:<8.4f} | {macro_f1:<12.4f} | {duration * 1000:.1f} ms"
        )

        # Selection criterion: highest Macro F1, tie-breaker highest accuracy
        if (macro_f1 > best_macro_f1) or (macro_f1 == best_macro_f1 and (best_metrics and acc > best_metrics["accuracy"])):
            best_macro_f1 = macro_f1
            best_config = cfg
            best_metrics = metrics
            best_pipeline = pipeline
            best_train_duration = duration

    print("-" * 70)
    print(f"\nWinning Configuration: {best_config}")
    print(f"Dev Accuracy: {best_metrics['accuracy']:.4f} | Dev Macro F1: {best_metrics['macro_f1']:.4f}")

    # Extract feature stats for winning pipeline
    features_step = best_pipeline.named_steps["features"]
    X_train_trans = features_step.transform(X_train)
    feat_stats = compute_feature_stats(
        features_step, X_train_trans, feature_type=best_config["feature_type"], duration_seconds=best_train_duration
    ).to_dict()

    # Measure prediction latency on dev set
    pred_start = time.perf_counter()
    best_pipeline.predict(X_dev)
    pred_duration_ms = (time.perf_counter() - pred_start) * 1000.0

    best_metrics["timing"] = {
        "train_duration_ms": round(best_train_duration * 1000.0, 2),
        "predict_duration_ms": round(pred_duration_ms, 2),
        "per_query_predict_ms": round(pred_duration_ms / len(X_dev), 3),
    }

    # Save artifact
    model_path = save_model_artifact(
        pipeline=best_pipeline,
        model_id="logistic_regression_baseline",
        model_type="logistic_regression",
        hyperparameters=best_config,
        metrics=best_metrics,
        artifact_dir=output_dir,
        feature_stats=feat_stats,
    )
    print(f"\nSerialized model artifact to: {model_path}")

    # Print Detailed Classification Report
    print("\n" + "=" * 70)
    print("PER-CLASS EVALUATION REPORT (DEV SPLIT)")
    print("=" * 70)
    print(format_classification_report_table(best_metrics))
    print("=" * 70 + "\n")

    return best_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Logistic Regression for Query Intent")
    parser.add_argument(
        "--train-path",
        type=Path,
        default=Path("data/query_intent/splits/train.jsonl"),
        help="Path to training split jsonl",
    )
    parser.add_argument(
        "--dev-path",
        type=Path,
        default=Path("data/query_intent/splits/dev.jsonl"),
        help="Path to development split jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/query_intent/logistic_regression"),
        help="Target directory for model artifacts",
    )
    args = parser.parse_args()

    train_and_optimize_logistic_regression(
        train_path=args.train_path,
        dev_path=args.dev_path,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
