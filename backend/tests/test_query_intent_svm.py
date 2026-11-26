"""Unit tests for Linear SVM Query Intent Pipeline (Phase 5 C5.6)."""

from pathlib import Path
import numpy as np
import pytest

from backend.app.ml.query_intent.artifacts import (
    load_model_artifact,
    save_model_artifact,
)
from backend.app.ml.query_intent.svm_model import (
    build_svm_pipeline,
    train_linear_svm,
)
from backend.app.ml.query_intent.taxonomy import TaxonomyRegistry


@pytest.fixture
def sample_data() -> tuple[list[str], list[str]]:
    categories = sorted(TaxonomyRegistry.list_category_ids())
    X = []
    y = []
    for cat in categories:
        X.append(f"Sample query one for {cat}")
        X.append(f"Sample query two for {cat}")
        y.append(cat)
        y.append(cat)
    return X, y


def test_svm_pipeline_training_and_multiclass_prediction(
    sample_data: tuple[list[str], list[str]],
) -> None:
    """Verifies that Linear SVM trains on sparse TF-IDF and outputs decision scores."""
    X_train, y_train = sample_data
    pipeline, duration, converged = train_linear_svm(
        X_train, y_train, feature_type="combined", C=1.0, max_iter=1000
    )

    assert duration > 0.0
    assert converged is True
    assert len(pipeline.named_steps["classifier"].classes_) == 13

    # Predict class
    preds = pipeline.predict(["Sample query one for comparison"])
    assert len(preds) == 1
    assert preds[0] in TaxonomyRegistry.list_category_ids()

    # Decision function output
    scores = pipeline.decision_function(["Sample query one for comparison"])[0]
    assert len(scores) == 13


def test_svm_serialization_and_reloading(
    tmp_path: Path, sample_data: tuple[list[str], list[str]]
) -> None:
    """Verifies saving and loading Linear SVM pipeline via joblib."""
    X_train, y_train = sample_data
    pipeline, _, _ = train_linear_svm(X_train, y_train, feature_type="word", C=1.0)

    artifact_dir = tmp_path / "svm_model"
    model_path = save_model_artifact(
        pipeline=pipeline,
        model_id="test_svm_model",
        model_type="linear_svm",
        hyperparameters={"C": 1.0, "feature_type": "word"},
        metrics={"accuracy": 1.0},
        artifact_dir=artifact_dir,
    )
    assert model_path.exists()
    assert (artifact_dir / "manifest.json").exists()

    # Reload
    loaded_pipeline, manifest = load_model_artifact(artifact_dir)
    assert manifest["model_id"] == "test_svm_model"
    assert manifest["model_type"] == "linear_svm"

    # Verify prediction with loaded model
    pred = loaded_pipeline.predict(["Sample query one for explanation"])[0]
    assert pred in TaxonomyRegistry.list_category_ids()


def test_svm_class_weight_balanced(
    sample_data: tuple[list[str], list[str]],
) -> None:
    """Verifies that balanced class weighting can be trained without error."""
    X_train, y_train = sample_data
    pipeline, _, _ = train_linear_svm(
        X_train, y_train, feature_type="word", class_weight="balanced"
    )
    clf = pipeline.named_steps["classifier"]
    assert clf.class_weight == "balanced"
