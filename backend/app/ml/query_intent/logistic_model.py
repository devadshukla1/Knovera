"""Logistic Regression Baseline for Knovera Query Intent Classification (Phase 5 C5.5).

Implements multiclass Logistic Regression pipeline supporting sparse TF-IDF inputs,
calibrated probability estimation, and class weighting.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from backend.app.ml.query_intent.features import FeatureType, build_feature_pipeline


def build_logistic_pipeline(
    feature_type: FeatureType = "combined",
    C: float = 1.0,
    class_weight: Optional[str] = None,
    max_iter: int = 2000,
    random_state: int = 42,
    solver: str = "lbfgs",
    word_weight: float = 1.0,
    char_weight: float = 1.0,
) -> Pipeline:
    """Constructs an end-to-end scikit-learn Pipeline with feature extraction and Logistic Regression.

    Args:
        feature_type: "word", "char", or "combined".
        C: Inverse regularization strength parameter.
        class_weight: None or "balanced".
        max_iter: Maximum iterations for solver convergence.
        random_state: Deterministic random seed.
        solver: Optimization algorithm (default "lbfgs" for multiclass).
        word_weight: Weight multiplier for word TF-IDF features.
        char_weight: Weight multiplier for char TF-IDF features.

    Returns:
        Configured, unfitted scikit-learn Pipeline.
    """
    feature_step = build_feature_pipeline(
        feature_type=feature_type,
        word_weight=word_weight,
        char_weight=char_weight,
    )

    classifier = LogisticRegression(
        C=C,
        solver=solver,
        class_weight=class_weight,
        max_iter=max_iter,
        random_state=random_state,
    )

    return Pipeline([
        ("features", feature_step),
        ("classifier", classifier),
    ])


def train_logistic_regression(
    X_train: List[str],
    y_train: List[str],
    feature_type: FeatureType = "combined",
    C: float = 1.0,
    class_weight: Optional[str] = None,
    max_iter: int = 2000,
    random_state: int = 42,
) -> Tuple[Pipeline, float]:
    """Fits the Logistic Regression pipeline strictly on training data.

    Returns:
        Tuple of (fitted_pipeline, train_duration_seconds).
    """
    pipeline = build_logistic_pipeline(
        feature_type=feature_type,
        C=C,
        class_weight=class_weight,
        max_iter=max_iter,
        random_state=random_state,
    )

    start_time = time.perf_counter()
    pipeline.fit(X_train, y_train)
    train_duration = time.perf_counter() - start_time

    return pipeline, train_duration
