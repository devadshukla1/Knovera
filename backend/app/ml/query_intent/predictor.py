"""Lightweight Offline Prediction Interface for Query Intent (Phase 5 C5.5 / C5.6).

Loads versioned model artifacts, applies standardized C5.3 preprocessing,
and provides structured predictions with class probability or decision score distributions.
"""

from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any, Dict, List, Literal, Optional
import numpy as np

from backend.app.ml.query_intent.artifacts import load_model_artifact
from backend.app.ml.query_intent.preprocessing import (
    PREPROCESSING_VERSION,
    PreprocessedQuery,
    QueryPreprocessor,
)
from backend.app.ml.query_intent.taxonomy import TAXONOMY_VERSION, TaxonomyRegistry

ScoreType = Literal["probability", "decision_score"]
ConfidenceType = Literal["calibrated_probability", "uncalibrated_probability", "decision_score", "unavailable"]


@dataclass(frozen=True)
class QueryIntentPrediction:
    """Structured result of query intent classification."""

    query: str
    sanitized_query: str
    normalized_query: str
    predicted_intent: str
    class_scores: Dict[str, float]
    score_type: ScoreType
    model_id: str
    model_type: str
    taxonomy_version: str
    preprocessing_version: str
    prediction_score: Optional[float] = None
    confidence_type: str = "uncalibrated_probability"
    prediction_latency_ms: float = 0.0
    top_intents: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes prediction to a plain dictionary."""
        return {
            "query": self.query,
            "sanitized_query": self.sanitized_query,
            "normalized_query": self.normalized_query,
            "predicted_intent": self.predicted_intent,
            "class_scores": self.class_scores,
            "score_type": self.score_type,
            "model_id": self.model_id,
            "model_type": self.model_type,
            "taxonomy_version": self.taxonomy_version,
            "preprocessing_version": self.preprocessing_version,
            "prediction_score": self.prediction_score,
            "confidence_type": self.confidence_type,
            "prediction_latency_ms": self.prediction_latency_ms,
            "top_intents": self.top_intents,
        }


class QueryIntentPredictor:
    """Offline prediction service wrapping a trained scikit-learn intent classification pipeline."""

    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.pipeline, self.manifest = load_model_artifact(artifact_dir)
        self.model_id = self.manifest.get("model_id", "unknown_model")
        self.model_type = self.manifest.get("model_type", "unknown_type")
        self.taxonomy_version = self.manifest.get("taxonomy_version", TAXONOMY_VERSION)
        self.preprocessing_version = self.manifest.get("preprocessing_version", PREPROCESSING_VERSION)
        self.preprocessor = QueryPreprocessor()

        classifier = self.pipeline.named_steps["classifier"]
        self.classes_: List[str] = list(classifier.classes_)

    def predict(self, raw_query: str) -> QueryIntentPrediction:
        """Classifies a user query string into a single primary intent.

        Args:
            raw_query: Natural language query string.

        Returns:
            QueryIntentPrediction containing predicted intent and per-class score distribution.
        """
        start_time = time.perf_counter()

        # 1. Standardized C5.3 Preprocessing
        preprocessed: PreprocessedQuery = self.preprocessor.preprocess(raw_query)
        feature_input = [preprocessed.normalized_text]

        # 2. Pipeline Prediction
        predicted_intent = str(self.pipeline.predict(feature_input)[0])

        classifier = self.pipeline.named_steps["classifier"]
        class_scores: Dict[str, float] = {}

        # 3. Class Score Extraction (probability vs decision score)
        manifest_conf_type = self.manifest.get("confidence_output_type")

        if hasattr(classifier, "predict_proba"):
            probs = self.pipeline.predict_proba(feature_input)[0]
            score_type: ScoreType = "probability"
            confidence_type = manifest_conf_type or "uncalibrated_probability"
            for cls_name, prob in zip(self.classes_, probs):
                class_scores[cls_name] = round(float(prob), 4)
        elif hasattr(classifier, "decision_function"):
            decision_scores = self.pipeline.decision_function(feature_input)[0]
            score_type = "decision_score"
            confidence_type = "decision_score"
            if np.ndim(decision_scores) == 0:
                # Binary classification edge case (not expected for 13 classes)
                class_scores[self.classes_[0]] = round(float(-decision_scores), 4)
                class_scores[self.classes_[1]] = round(float(decision_scores), 4)
            else:
                for cls_name, score in zip(self.classes_, decision_scores):
                    class_scores[cls_name] = round(float(score), 4)
        else:
            score_type = "decision_score"
            confidence_type = "decision_score"
            class_scores[predicted_intent] = 1.0

        # Sort class scores descending
        sorted_scores = dict(sorted(class_scores.items(), key=lambda x: x[1], reverse=True))

        top_intents = [
            {"intent": k, "score": v}
            for k, v in list(sorted_scores.items())[:5]
        ]
        prediction_score = sorted_scores.get(predicted_intent, None)
        prediction_latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return QueryIntentPrediction(
            query=raw_query,
            sanitized_query=preprocessed.sanitized_text,
            normalized_query=preprocessed.normalized_text,
            predicted_intent=predicted_intent,
            class_scores=sorted_scores,
            score_type=score_type,
            model_id=self.model_id,
            model_type=self.model_type,
            taxonomy_version=self.taxonomy_version,
            preprocessing_version=self.preprocessing_version,
            prediction_score=prediction_score,
            confidence_type=confidence_type,
            prediction_latency_ms=prediction_latency_ms,
            top_intents=top_intents,
        )
