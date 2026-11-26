"""Tests for Query Intent Metrics and Calibration Evaluation (Phase 5 C5.7)."""

import numpy as np
import pytest

from backend.app.ml.query_intent.metrics import (
    calculate_calibration_metrics,
    calculate_classification_metrics,
    format_classification_report_table,
    format_comparison_table,
)
from backend.app.ml.query_intent.taxonomy import TaxonomyRegistry


def test_calculate_classification_metrics_standard() -> None:
    """Verifies that classification metrics calculate accurately across all 13 taxonomy categories."""
    all_categories = sorted(TaxonomyRegistry.list_category_ids())
    y_true = ["factual_lookup", "definition", "comparison", "explanation"]
    y_pred = ["factual_lookup", "definition", "comparison", "definition"]  # 1 mistake

    metrics = calculate_classification_metrics(y_true, y_pred, labels=all_categories)

    assert metrics["total_samples"] == 4
    assert metrics["accuracy"] == 0.75
    assert "per_class" in metrics
    assert len(metrics["per_class"]) == 13
    assert metrics["per_class"]["factual_lookup"]["f1"] == 1.0
    assert metrics["per_class"]["factual_lookup"]["support"] == 1
    assert metrics["per_class"]["explanation"]["recall"] == 0.0
    assert metrics["per_class"]["explanation"]["support"] == 1

    # Confusion matrix checks
    cm = metrics["confusion_matrix"]
    assert len(cm["labels"]) == 13
    assert len(cm["counts"]) == 13
    assert len(cm["normalized"]) == 13


def test_calculate_calibration_metrics_ece_and_brier() -> None:
    """Verifies multiclass log loss, Brier score, and ECE computation."""
    labels = ["ambiguous", "factual_lookup", "summarization"]
    y_true = ["factual_lookup", "factual_lookup", "ambiguous", "summarization"]
    # Simulated probabilities: shape (4, 3)
    y_prob = np.array([
        [0.1, 0.8, 0.1],  # True: factual_lookup, Pred: factual_lookup (conf 0.8, correct)
        [0.2, 0.7, 0.1],  # True: factual_lookup, Pred: factual_lookup (conf 0.7, correct)
        [0.6, 0.2, 0.2],  # True: ambiguous, Pred: ambiguous (conf 0.6, correct)
        [0.1, 0.3, 0.6],  # True: summarization, Pred: summarization (conf 0.6, correct)
    ])

    calib = calculate_calibration_metrics(y_true, y_prob, labels=labels, n_bins=5)

    assert "log_loss" in calib
    assert calib["log_loss"] > 0.0
    assert "brier_score" in calib
    assert 0.0 <= calib["brier_score"] <= 2.0
    assert "ece" in calib
    assert 0.0 <= calib["ece"] <= 1.0
    assert "mce" in calib
    assert len(calib["bin_details"]) > 0


def test_format_comparison_table_renders_calibration() -> None:
    """Verifies that format_comparison_table renders ECE, Log Loss, and Brier Score columns."""
    lr_metrics = {"accuracy": 0.89, "macro_precision": 0.91, "macro_recall": 0.89, "macro_f1": 0.89, "weighted_f1": 0.89}
    svm_metrics = {"accuracy": 0.89, "macro_precision": 0.90, "macro_recall": 0.89, "macro_f1": 0.89, "weighted_f1": 0.89}

    table_str = format_comparison_table(
        logreg_metrics=lr_metrics,
        svm_metrics=svm_metrics,
        logreg_extra={"log_loss": "0.7516", "brier_score": "0.3080", "ece": "0.3203"},
        svm_extra={"log_loss": "N/A", "brier_score": "N/A", "ece": "N/A"},
    )

    assert "Log Loss" in table_str
    assert "Brier Score" in table_str
    assert "ECE" in table_str
    assert "0.7516" in table_str
    assert "N/A" in table_str
