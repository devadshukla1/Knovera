"""Linear Support Vector Machine (LinearSVC) Classifier for Knovera Query Intent (Phase 5 C5.6).

Implements multiclass Linear SVM pipeline on sparse TF-IDF features with decision scores,
class weighting, and convergence monitoring.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
import warnings
from sklearn.exceptions import ConvergenceWarning
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from backend.app.ml.query_intent.features import FeatureType, build_feature_pipeline


def build_svm_pipeline(
    feature_type: FeatureType = "combined",
    C: float = 1.0,
    class_weight: Optional[str] = None,
    max_iter: int = 5000,
    random_state: int = 42,
    dual: Any = "auto",
    word_weight: float = 1.0,
    char_weight: float = 1.0,
) -> Pipeline:
    """Constructs an end-to-end scikit-learn Pipeline with feature extraction and LinearSVC.

    Args:
        feature_type: "word", "char", or "combined".
        C: Regularization parameter.
        class_weight: None or "balanced".
        max_iter: Maximum solver iterations.
        random_state: Deterministic random seed.
        dual: Formulation parameter ("auto" in scikit-learn 1.3+).
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

    classifier = LinearSVC(
        C=C,
        class_weight=class_weight,
        max_iter=max_iter,
        random_state=random_state,
        dual=dual,
    )

    return Pipeline([
        ("features", feature_step),
        ("classifier", classifier),
    ])


def train_linear_svm(
    X_train: List[str],
    y_train: List[str],
    feature_type: FeatureType = "combined",
    C: float = 1.0,
    class_weight: Optional[str] = None,
    max_iter: int = 5000,
    random_state: int = 42,
) -> Tuple[Pipeline, float, bool]:
    """Fits the Linear SVM pipeline strictly on training data.

    Returns:
        Tuple of (fitted_pipeline, train_duration_seconds, converged_flag).
    """
    pipeline = build_svm_pipeline(
        feature_type=feature_type,
        C=C,
        class_weight=class_weight,
        max_iter=max_iter,
        random_state=random_state,
    )

    converged = True
    start_time = time.perf_counter()
    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always", ConvergenceWarning)
        pipeline.fit(X_train, y_train)
        for w in captured_warnings:
            if issubclass(w.category, ConvergenceWarning):
                converged = False

    train_duration = time.perf_counter() - start_time
    return pipeline, train_duration, converged
