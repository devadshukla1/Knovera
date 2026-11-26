"""Unit tests for Logistic Regression Query Intent Pipeline (Phase 5 C5.5)."""

from pathlib import Path
import numpy as np
import pytest

from backend.app.ml.query_intent.artifacts import (
    load_model_artifact,
    save_model_artifact,
)
from backend.app.ml.query_intent.logistic_model import (
    build_logistic_pipeline,
    train_logistic_regression,
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


def test_logistic_pipeline_training_and_multiclass_prediction(
    sample_data: tuple[list[str], list[str]],
) -> None:
    """Verifies that Logistic Regression trains on sparse TF-IDF and outputs 13-class probabilities."""
    X_train, y_train = sample_data
    pipeline, duration = train_logistic_regression(
        X_train, y_train, feature_type="combined", C=1.0, max_iter=500
    )

    assert duration > 0.0
    assert len(pipeline.named_steps["classifier"].classes_) == 13

    # Predict class
    preds = pipeline.predict(["Sample query one for factual_lookup"])
    assert len(preds) == 1
    assert preds[0] in TaxonomyRegistry.list_category_ids()

    # Predict probabilities
    probs = pipeline.predict_proba(["Sample query one for factual_lookup"])[0]
    assert len(probs) == 13
    assert np.isclose(np.sum(probs), 1.0, atol=1e-4)


def test_logistic_serialization_and_reloading(
    tmp_path: Path, sample_data: tuple[list[str], list[str]]
) -> None:
    """Verifies saving and loading Logistic Regression pipeline via joblib."""
    X_train, y_train = sample_data
    pipeline, _ = train_logistic_regression(X_train, y_train, feature_type="word", C=1.0)

    artifact_dir = tmp_path / "logistic_model"
    model_path = save_model_artifact(
        pipeline=pipeline,
        model_id="test_logistic_model",
        model_type="logistic_regression",
        hyperparameters={"C": 1.0, "feature_type": "word"},
        metrics={"accuracy": 1.0},
        artifact_dir=artifact_dir,
    )
    assert model_path.exists()
    assert (artifact_dir / "manifest.json").exists()

    # Reload
    loaded_pipeline, manifest = load_model_artifact(artifact_dir)
    assert manifest["model_id"] == "test_logistic_model"
    assert manifest["model_type"] == "logistic_regression"

    # Verify prediction with loaded model
    pred = loaded_pipeline.predict(["Sample query one for definition"])[0]
    assert pred in TaxonomyRegistry.list_category_ids()


def test_logistic_class_weight_balanced(
    sample_data: tuple[list[str], list[str]],
) -> None:
    """Verifies that balanced class weighting can be trained without error."""
    X_train, y_train = sample_data
    pipeline, _ = train_logistic_regression(
        X_train, y_train, feature_type="word", class_weight="balanced"
    )
    clf = pipeline.named_steps["classifier"]
    assert clf.class_weight == "balanced"
