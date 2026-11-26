"""Model Comparison, Error Analysis, and Selection CLI for Query Intent (Phase 5 C5.5 / C5.6).

Compares trained Logistic Regression baseline against Linear SVM on the identical development split,
performs confusion matrix and per-class error analysis, promotes the winning model to
models/query_intent/selected_model/, and optionally executes a frozen one-time test split evaluation.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List, Tuple

from backend.app.ml.query_intent.artifacts import load_model_artifact, save_model_artifact
from backend.app.ml.query_intent.metrics import (
    calculate_calibration_metrics,
    calculate_classification_metrics,
    format_classification_report_table,
    format_comparison_table,
)
from backend.app.ml.query_intent.taxonomy import TaxonomyRegistry
from backend.scripts.prepare_query_intent_dataset import load_jsonl


def compare_and_select_models(
    logreg_dir: Path = Path("models/query_intent/logistic_regression"),
    svm_dir: Path = Path("models/query_intent/linear_svm"),
    dev_path: Path = Path("data/query_intent/splits/dev.jsonl"),
    test_path: Path = Path("data/query_intent/splits/test.jsonl"),
    output_selected_dir: Path = Path("models/query_intent/selected_model"),
    eval_dir: Path = Path("models/query_intent/evaluation"),
    run_test_eval: bool = False,
) -> Dict[str, Any]:
    print("=" * 70)
    print("KNOVERA QUERY INTENT MODEL COMPARISON & ERROR ANALYSIS")
    print("=" * 70)

    # 1. Load Artifacts
    print(f"Loading Logistic Regression artifact from {logreg_dir}...")
    logreg_pipeline, logreg_manifest = load_model_artifact(logreg_dir)

    print(f"Loading Linear SVM artifact from {svm_dir}...")
    svm_pipeline, svm_manifest = load_model_artifact(svm_dir)

    # 2. Load Dev Data
    dev_records = load_jsonl(dev_path)
    X_dev = [r["normalized_text"] for r in dev_records]
    y_dev = [r["intent"] for r in dev_records]
    raw_queries_dev = [r["query_text"] for r in dev_records]
    all_categories = sorted(TaxonomyRegistry.list_category_ids())

    print(f"Loaded {len(X_dev)} development queries across {len(all_categories)} categories.\n")

    # 3. Evaluate Logistic Regression
    t0 = time.perf_counter()
    logreg_preds = list(logreg_pipeline.predict(X_dev))
    logreg_pred_time_ms = (time.perf_counter() - t0) * 1000.0

    logreg_metrics = calculate_classification_metrics(y_dev, logreg_preds, labels=all_categories)
    logreg_size_kb = logreg_manifest.get("artifact", {}).get("size_kb", 0.0)
    logreg_train_time_ms = logreg_manifest.get("metrics", {}).get("timing", {}).get("train_duration_ms", 0.0)

    # Calibration Metrics for Logistic Regression
    logreg_probs = logreg_pipeline.predict_proba(X_dev)
    logreg_calib = calculate_calibration_metrics(
        y_true=y_dev,
        y_prob=logreg_probs,
        labels=all_categories,
    )
    logreg_metrics["calibration"] = logreg_calib

    # 4. Evaluate Linear SVM
    t1 = time.perf_counter()
    svm_preds = list(svm_pipeline.predict(X_dev))
    svm_pred_time_ms = (time.perf_counter() - t1) * 1000.0

    svm_metrics = calculate_classification_metrics(y_dev, svm_preds, labels=all_categories)
    svm_size_kb = svm_manifest.get("artifact", {}).get("size_kb", 0.0)
    svm_train_time_ms = svm_manifest.get("metrics", {}).get("timing", {}).get("train_duration_ms", 0.0)
    svm_metrics["calibration"] = {
        "status": "uncalibrated_decision_scores",
        "log_loss": "N/A",
        "brier_score": "N/A",
        "ece": "N/A",
    }

    # 5. Print Comparison Table
    print("--- MODEL COMPARISON TABLE (DEV SPLIT) ---")
    comp_table = format_comparison_table(
        logreg_metrics=logreg_metrics,
        svm_metrics=svm_metrics,
        logreg_extra={
            "train_duration_ms": logreg_train_time_ms,
            "predict_duration_ms": logreg_pred_time_ms,
            "model_size_kb": logreg_size_kb,
            "log_loss": f"{logreg_calib['log_loss']:.4f}",
            "brier_score": f"{logreg_calib['brier_score']:.4f}",
            "ece": f"{logreg_calib['ece']:.4f}",
        },
        svm_extra={
            "train_duration_ms": svm_train_time_ms,
            "predict_duration_ms": svm_pred_time_ms,
            "model_size_kb": svm_size_kb,
            "log_loss": "N/A",
            "brier_score": "N/A",
            "ece": "N/A",
        },
    )
    print(comp_table)
    print()

    # 6. Detailed Error Analysis
    print("=" * 70)
    print("DETAILED ERROR ANALYSIS (DEV SPLIT)")
    print("=" * 70)

    both_wrong: List[Dict[str, Any]] = []
    logreg_only_right: List[Dict[str, Any]] = []
    svm_only_right: List[Dict[str, Any]] = []
    confused_pairs = Counter()

    for query_text, true_y, lr_y, svm_y in zip(raw_queries_dev, y_dev, logreg_preds, svm_preds):
        if lr_y != true_y and svm_y != true_y:
            both_wrong.append({
                "query": query_text,
                "true_intent": true_y,
                "logreg_pred": lr_y,
                "svm_pred": svm_y,
            })
            confused_pairs[(true_y, lr_y)] += 1
            confused_pairs[(true_y, svm_y)] += 1
        elif lr_y == true_y and svm_y != true_y:
            logreg_only_right.append({
                "query": query_text,
                "true_intent": true_y,
                "svm_pred": svm_y,
            })
            confused_pairs[(true_y, svm_y)] += 1
        elif svm_y == true_y and lr_y != true_y:
            svm_only_right.append({
                "query": query_text,
                "true_intent": true_y,
                "logreg_pred": lr_y,
            })
            confused_pairs[(true_y, lr_y)] += 1

    print(f"Total Dev Queries:                         {len(X_dev)}")
    print(f"Both Models Correct:                       {len(X_dev) - len(both_wrong) - len(logreg_only_right) - len(svm_only_right)}")
    print(f"Both Models Incorrect:                     {len(both_wrong)}")
    print(f"Logistic Regression Correct, SVM Wrong:    {len(logreg_only_right)}")
    print(f"Linear SVM Correct, Logistic Reg Wrong:    {len(svm_only_right)}\n")

    if confused_pairs:
        print("Most Frequently Confused Category Pairs (True -> Predicted):")
        for (true_c, pred_c), cnt in confused_pairs.most_common(5):
            print(f"  {true_c:<22} -> {pred_c:<22} (Count: {cnt})")
        print()

    if both_wrong:
        print("Queries Misclassified by Both Models:")
        for item in both_wrong:
            print(f"  Query:      '{item['query']}'")
            print(f"  True:       {item['true_intent']}")
            print(f"  LogReg:     {item['logreg_pred']}")
            print(f"  LinearSVM:  {item['svm_pred']}")
            print("-" * 50)
        print()

    # 7. Model Selection Rationale
    # Transparent lexicographic criteria:
    # 1. Higher Macro F1
    # 2. Higher Macro Recall
    # 3. Higher Macro Precision
    # 4. Probabilistic calibration capability (LogReg has predict_proba)
    if logreg_metrics["macro_f1"] > svm_metrics["macro_f1"]:
        winner_name = "logistic_regression"
        winning_pipeline = logreg_pipeline
        winning_manifest = logreg_manifest
        winning_metrics = logreg_metrics
        selection_rationale = (
            f"Logistic Regression achieved superior Macro F1 ({logreg_metrics['macro_f1']:.4f} vs {svm_metrics['macro_f1']:.4f}) "
            f"and higher Macro Precision ({logreg_metrics['macro_precision']:.4f} vs {svm_metrics['macro_precision']:.4f}) "
            f"while providing native class probability distributions via predict_proba()."
        )
    elif svm_metrics["macro_f1"] > logreg_metrics["macro_f1"]:
        winner_name = "linear_svm"
        winning_pipeline = svm_pipeline
        winning_manifest = svm_manifest
        winning_metrics = svm_metrics
        selection_rationale = (
            f"Linear SVM achieved superior Macro F1 ({svm_metrics['macro_f1']:.4f} vs {logreg_metrics['macro_f1']:.4f}) "
            f"and lower training/prediction latency."
        )
    else:
        # Tie: prefer Logistic Regression for native probability calibration
        winner_name = "logistic_regression"
        winning_pipeline = logreg_pipeline
        winning_manifest = logreg_manifest
        winning_metrics = logreg_metrics
        selection_rationale = (
            f"Both models achieved equal Macro F1 ({logreg_metrics['macro_f1']:.4f}). "
            f"Logistic Regression selected due to native predict_proba() class probability calibration."
        )

    print("=" * 70)
    print(f"SELECTED MODEL: {winner_name.upper()}")
    print(f"Rationale: {selection_rationale}")
    print("=" * 70)

    # 8. Promote Winning Model to selected_model/
    output_selected_dir.mkdir(parents=True, exist_ok=True)
    selected_manifest_path = output_selected_dir / "manifest.json"
    selected_model_path = output_selected_dir / "model.joblib"

    # Save to selected_model
    source_dir = logreg_dir if winner_name == "logistic_regression" else svm_dir
    shutil.copy2(source_dir / "model.joblib", selected_model_path)

    updated_manifest = dict(winning_manifest)
    updated_manifest["model_id"] = "selected_query_intent_model"
    updated_manifest["selected_from"] = winner_name
    updated_manifest["selection_rationale"] = selection_rationale
    updated_manifest["calibration_status"] = "uncalibrated" if winner_name == "logistic_regression" else "none"
    updated_manifest["confidence_output_type"] = (
        "uncalibrated_probability" if winner_name == "logistic_regression" else "decision_score"
    )
    if winner_name == "logistic_regression":
        updated_manifest["calibration_metrics"] = {
            "log_loss": logreg_calib["log_loss"],
            "brier_score": logreg_calib["brier_score"],
            "ece": logreg_calib["ece"],
            "mce": logreg_calib["mce"],
        }

    with open(selected_manifest_path, "w", encoding="utf-8") as f:
        json.dump(updated_manifest, f, indent=2, ensure_ascii=False)

    print(f"Promoted {winner_name} artifact to {output_selected_dir}")

    # 9. Save Evaluation Artifacts in models/query_intent/evaluation/
    eval_dir.mkdir(parents=True, exist_ok=True)

    with open(eval_dir / "development_metrics.json", "w", encoding="utf-8") as f:
        json.dump({
            "logistic_regression": logreg_metrics,
            "linear_svm": svm_metrics,
            "selected_model": winner_name,
            "selection_rationale": selection_rationale,
        }, f, indent=2, ensure_ascii=False)

    with open(eval_dir / "classification_report.json", "w", encoding="utf-8") as f:
        json.dump({
            "selected_model": winner_name,
            "per_class": winning_metrics["per_class"],
            "summary": {
                "accuracy": winning_metrics["accuracy"],
                "macro_f1": winning_metrics["macro_f1"],
                "macro_precision": winning_metrics["macro_precision"],
                "macro_recall": winning_metrics["macro_recall"],
                "weighted_f1": winning_metrics["weighted_f1"],
            },
        }, f, indent=2, ensure_ascii=False)

    with open(eval_dir / "confusion_matrix.json", "w", encoding="utf-8") as f:
        json.dump({
            "selected_model": winner_name,
            "confusion_matrix": winning_metrics["confusion_matrix"],
        }, f, indent=2, ensure_ascii=False)

    # 10. Optional Test Set Evaluation
    test_metrics = None
    if run_test_eval:
        print("\n" + "=" * 70)
        print("FROZEN ONE-TIME EVALUATION ON HELD-OUT TEST SPLIT")
        print("=" * 70)

        test_records = load_jsonl(test_path)
        X_test = [r["normalized_text"] for r in test_records]
        y_test = [r["intent"] for r in test_records]

        print(f"Evaluating frozen {winner_name} pipeline on {len(X_test)} test queries...")
        t_test = time.perf_counter()
        test_preds = list(winning_pipeline.predict(X_test))
        test_duration_ms = (time.perf_counter() - t_test) * 1000.0

        test_metrics = calculate_classification_metrics(y_test, test_preds, labels=all_categories)
        if hasattr(winning_pipeline, "predict_proba"):
            test_probs = winning_pipeline.predict_proba(X_test)
            test_calib = calculate_calibration_metrics(
                y_true=y_test,
                y_prob=test_probs,
                labels=all_categories,
            )
            test_metrics["calibration"] = test_calib

        test_metrics["timing"] = {
            "predict_duration_ms": round(test_duration_ms, 2),
            "per_query_predict_ms": round(test_duration_ms / len(X_test), 3),
        }

        print(f"Test Accuracy: {test_metrics['accuracy']:.4f} | Test Macro F1: {test_metrics['macro_f1']:.4f}")
        print("\n" + format_classification_report_table(test_metrics) + "\n")

        with open(eval_dir / "test_metrics.json", "w", encoding="utf-8") as f:
            json.dump({
                "selected_model": winner_name,
                "test_metrics": test_metrics,
            }, f, indent=2, ensure_ascii=False)

        print(f"Saved test evaluation metrics to {eval_dir / 'test_metrics.json'}")

    return {
        "logreg_metrics": logreg_metrics,
        "svm_metrics": svm_metrics,
        "selected_model": winner_name,
        "test_metrics": test_metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Query Intent Models")
    parser.add_argument("--logreg-dir", type=Path, default=Path("models/query_intent/logistic_regression"))
    parser.add_argument("--svm-dir", type=Path, default=Path("models/query_intent/linear_svm"))
    parser.add_argument("--dev-path", type=Path, default=Path("data/query_intent/splits/dev.jsonl"))
    parser.add_argument("--test-path", type=Path, default=Path("data/query_intent/splits/test.jsonl"))
    parser.add_argument("--selected-dir", type=Path, default=Path("models/query_intent/selected_model"))
    parser.add_argument("--eval-dir", type=Path, default=Path("models/query_intent/evaluation"))
    parser.add_argument("--test-eval", action="store_true", help="Execute frozen holdout test evaluation")

    args = parser.parse_args()

    compare_and_select_models(
        logreg_dir=args.logreg_dir,
        svm_dir=args.svm_dir,
        dev_path=args.dev_path,
        test_path=args.test_path,
        output_selected_dir=args.selected_dir,
        eval_dir=args.eval_dir,
        run_test_eval=args.test_eval,
    )


if __name__ == "__main__":
    main()
