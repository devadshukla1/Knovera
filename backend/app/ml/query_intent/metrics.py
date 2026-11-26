"""Classification Metrics and Error Analysis Suite for Query Intent (Phase 5 C5.5 / C5.6).

Calculates Accuracy, Macro/Weighted Precision, Recall, F1, Per-Class breakdowns across
all 13 categories, and 13x13 raw and row-normalized confusion matrices.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    log_loss,
    precision_recall_fscore_support,
)

from backend.app.ml.query_intent.taxonomy import TaxonomyRegistry


def calculate_classification_metrics(
    y_true: List[str],
    y_pred: List[str],
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Computes comprehensive classification metrics across all taxonomy categories.

    Args:
        y_true: True ground truth class labels.
        y_pred: Predicted class labels.
        labels: Ordered list of all class labels to evaluate. Defaults to all 13 taxonomy categories.

    Returns:
        Structured dictionary containing scalar summary metrics, per-class metrics,
        and confusion matrix.
    """
    if labels is None:
        labels = sorted(TaxonomyRegistry.list_category_ids())

    # 1. Overall Accuracy
    accuracy = float(accuracy_score(y_true, y_pred))

    # 2. Macro and Weighted Metrics
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="weighted", zero_division=0
    )

    # 3. Per-Class Metrics
    per_class_p, per_class_r, per_class_f1, per_class_support = (
        precision_recall_fscore_support(
            y_true, y_pred, labels=labels, average=None, zero_division=0
        )
    )

    per_class_metrics: Dict[str, Dict[str, Any]] = {}
    for idx, label in enumerate(labels):
        per_class_metrics[label] = {
            "precision": round(float(per_class_p[idx]), 4),
            "recall": round(float(per_class_r[idx]), 4),
            "f1": round(float(per_class_f1[idx]), 4),
            "support": int(per_class_support[idx]),
        }

    # 4. Confusion Matrix (13x13)
    cm_raw = confusion_matrix(y_true, y_pred, labels=labels)

    # Row-normalized confusion matrix (percentages)
    with np.errstate(divide="ignore", invalid="ignore"):
        row_sums = cm_raw.sum(axis=1, keepdims=True)
        cm_norm = np.where(row_sums > 0, cm_raw / row_sums, 0.0)

    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(float(macro_p), 4),
        "macro_recall": round(float(macro_r), 4),
        "macro_f1": round(float(macro_f1), 4),
        "weighted_precision": round(float(weighted_p), 4),
        "weighted_recall": round(float(weighted_r), 4),
        "weighted_f1": round(float(weighted_f1), 4),
        "total_samples": len(y_true),
        "labels": labels,
        "per_class": per_class_metrics,
        "confusion_matrix": {
            "labels": labels,
            "counts": cm_raw.tolist(),
            "normalized": np.round(cm_norm, 4).tolist(),
        },
    }


def calculate_calibration_metrics(
    y_true: List[str],
    y_prob: np.ndarray,
    labels: Optional[List[str]] = None,
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Computes multiclass calibration metrics: Log Loss, Brier Score, and Expected Calibration Error (ECE).

    Args:
        y_true: True class labels.
        y_prob: Predicted probability array of shape (N, K).
        labels: Class labels corresponding to columns of y_prob.
        n_bins: Number of equal-width probability bins for ECE calculation.

    Returns:
        Structured dictionary containing log_loss, brier_score, ece, mce, and reliability bin details.
    """
    if labels is None:
        labels = sorted(TaxonomyRegistry.list_category_ids())

    y_prob_arr = np.asarray(y_prob, dtype=float)
    N, K = y_prob_arr.shape

    # 1. Multiclass Cross-Entropy Log Loss
    try:
        loss = float(log_loss(y_true, y_prob_arr, labels=labels))
    except Exception:
        loss = float("nan")

    # 2. Multiclass Brier Score: (1/N) * sum_i sum_k (y_ik - p_ik)^2
    y_onehot = np.zeros((N, K), dtype=float)
    for i, label in enumerate(y_true):
        if label in labels:
            y_onehot[i, labels.index(label)] = 1.0
    brier = float(np.mean(np.sum((y_prob_arr - y_onehot) ** 2, axis=1)))

    # 3. Top-1 Confidence & Expected Calibration Error (ECE)
    pred_indices = np.argmax(y_prob_arr, axis=1)
    confidences = np.max(y_prob_arr, axis=1)
    predicted_labels = [labels[idx] for idx in pred_indices]
    corrects = np.array([1.0 if p == t else 0.0 for p, t in zip(predicted_labels, y_true)])

    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    mce = 0.0
    bin_details: List[Dict[str, Any]] = []

    for b in range(n_bins):
        low = bin_boundaries[b]
        high = bin_boundaries[b + 1]
        if b == n_bins - 1:
            mask = (confidences >= low) & (confidences <= high)
        else:
            mask = (confidences >= low) & (confidences < high)

        bin_count = int(np.sum(mask))
        if bin_count > 0:
            bin_acc = float(np.mean(corrects[mask]))
            bin_conf = float(np.mean(confidences[mask]))
            diff = abs(bin_acc - bin_conf)
            ece += (bin_count / N) * diff
            mce = max(mce, diff)
            bin_details.append({
                "bin": f"{low:.1f}-{high:.1f}",
                "count": bin_count,
                "accuracy": round(bin_acc, 4),
                "confidence": round(bin_conf, 4),
                "abs_diff": round(diff, 4),
            })

    return {
        "log_loss": round(loss, 4),
        "brier_score": round(brier, 4),
        "ece": round(ece, 4),
        "mce": round(mce, 4),
        "n_bins": n_bins,
        "bin_details": bin_details,
    }


def format_classification_report_table(metrics: Dict[str, Any]) -> str:
    """Formats per-class metrics into a clean Markdown table."""
    lines = [
        "| Category | Precision | Recall | F1-Score | Support |",
        "|---|---:|---:|---:|---:|",
    ]
    per_class = metrics["per_class"]
    for label in metrics["labels"]:
        data = per_class.get(label, {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0})
        lines.append(
            f"| `{label}` | {data['precision']:.4f} | {data['recall']:.4f} | "
            f"{data['f1']:.4f} | {data['support']} |"
        )

    lines.append(
        f"| **Macro Average** | **{metrics['macro_precision']:.4f}** | "
        f"**{metrics['macro_recall']:.4f}** | **{metrics['macro_f1']:.4f}** | "
        f"{metrics['total_samples']} |"
    )
    lines.append(
        f"| **Weighted Average** | **{metrics['weighted_precision']:.4f}** | "
        f"**{metrics['weighted_recall']:.4f}** | **{metrics['weighted_f1']:.4f}** | "
        f"{metrics['total_samples']} |"
    )
    lines.append(f"| **Accuracy** | | | **{metrics['accuracy']:.4f}** | {metrics['total_samples']} |")
    return "\n".join(lines)


def format_comparison_table(
    logreg_metrics: Dict[str, Any],
    svm_metrics: Dict[str, Any],
    logreg_extra: Optional[Dict[str, Any]] = None,
    svm_extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Formats comparison table between Logistic Regression and Linear SVM."""
    logreg_extra = logreg_extra or {}
    svm_extra = svm_extra or {}

    rows = [
        ("Accuracy", f"{logreg_metrics['accuracy']:.4f}", f"{svm_metrics['accuracy']:.4f}"),
        ("Macro Precision", f"{logreg_metrics['macro_precision']:.4f}", f"{svm_metrics['macro_precision']:.4f}"),
        ("Macro Recall", f"{logreg_metrics['macro_recall']:.4f}", f"{svm_metrics['macro_recall']:.4f}"),
        ("Macro F1", f"{logreg_metrics['macro_f1']:.4f}", f"{svm_metrics['macro_f1']:.4f}"),
        ("Weighted F1", f"{logreg_metrics['weighted_f1']:.4f}", f"{svm_metrics['weighted_f1']:.4f}"),
        ("Log Loss", f"{logreg_extra.get('log_loss', 'N/A')}", f"{svm_extra.get('log_loss', 'N/A')}"),
        ("Brier Score", f"{logreg_extra.get('brier_score', 'N/A')}", f"{svm_extra.get('brier_score', 'N/A')}"),
        ("ECE", f"{logreg_extra.get('ece', 'N/A')}", f"{svm_extra.get('ece', 'N/A')}"),
        ("Training Time", f"{logreg_extra.get('train_duration_ms', 0):.2f} ms", f"{svm_extra.get('train_duration_ms', 0):.2f} ms"),
        ("Prediction Time", f"{logreg_extra.get('predict_duration_ms', 0):.2f} ms", f"{svm_extra.get('predict_duration_ms', 0):.2f} ms"),
        ("Model Size", f"{logreg_extra.get('model_size_kb', 0):.2f} KB", f"{svm_extra.get('model_size_kb', 0):.2f} KB"),
    ]

    lines = [
        "| Metric | Logistic Regression | Linear SVM |",
        "|---|---:|---:|",
    ]
    for name, lr_val, svm_val in rows:
        lines.append(f"| {name} | {lr_val} | {svm_val} |")

    return "\n".join(lines)
