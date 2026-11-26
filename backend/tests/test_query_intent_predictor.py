"""Unit tests for QueryIntentPredictor Offline Prediction Service (Phase 5 C5.5 / C5.6)."""

import json
from pathlib import Path
import pytest

from backend.app.ml.query_intent.predictor import (
    QueryIntentPrediction,
    QueryIntentPredictor,
)
from backend.app.ml.query_intent.taxonomy import TaxonomyRegistry


def test_predictor_with_selected_model() -> None:
    """Verifies that QueryIntentPredictor loads selected model and outputs valid predictions."""
    model_dir = Path("models/query_intent/selected_model")
    if not model_dir.exists():
        pytest.skip("Selected model artifact not yet generated.")

    predictor = QueryIntentPredictor(model_dir)
    assert predictor.model_id == "selected_query_intent_model"
    assert len(predictor.classes_) == 13

    # Test comparison query
    query = "Compare TCP and UDP protocols for streaming media."
    pred = predictor.predict(query)

    assert isinstance(pred, QueryIntentPrediction)
    assert pred.query == query
    assert pred.predicted_intent in TaxonomyRegistry.list_category_ids()
    assert pred.score_type == "probability"
    assert len(pred.class_scores) == 13

    # Verify probability distribution sums to ~1.0
    total_prob = sum(pred.class_scores.values())
    assert 0.99 <= total_prob <= 1.01

    # Test explanation query
    query2 = "How does backpropagation update neural network weights?"
    pred2 = predictor.predict(query2)
    assert pred2.predicted_intent in TaxonomyRegistry.list_category_ids()


def test_predictor_with_svm_model() -> None:
    """Verifies that QueryIntentPredictor handles Linear SVM decision scores."""
    model_dir = Path("models/query_intent/linear_svm")
    if not model_dir.exists():
        pytest.skip("SVM model artifact not yet generated.")

    predictor = QueryIntentPredictor(model_dir)
    pred = predictor.predict("What is the definition of BM25?")
    assert pred.score_type == "decision_score"
    assert len(pred.class_scores) == 13


def test_predictor_rejects_checksum_mismatch(tmp_path: Path) -> None:
    """Verifies that tampered model artifacts trigger a ValueError upon loading."""
    fake_dir = tmp_path / "tampered_model"
    fake_dir.mkdir(parents=True, exist_ok=True)

    # Write dummy model file
    model_file = fake_dir / "model.joblib"
    model_file.write_bytes(b"dummy corrupted model content")

    # Write manifest with wrong checksum
    manifest_file = fake_dir / "manifest.json"
    manifest_file.write_text(
        json.dumps({
            "model_id": "fake_model",
            "model_type": "linear_svm",
            "taxonomy_version": "1.0.0",
            "artifact": {
                "file_name": "model.joblib",
                "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
            },
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="checksum verification failed"):
        QueryIntentPredictor(fake_dir)
