"""Query Intent Service for Runtime Prediction and Lifecycle Management (Phase 5 C5.8).

Provides process-level cached model loading, non-blocking asynchronous inference,
taxonomy and artifact integrity verification, and explicit failure/fallback policies.
"""

import asyncio
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.ml.query_intent.predictor import QueryIntentPrediction, QueryIntentPredictor
from backend.app.ml.query_intent.taxonomy import TAXONOMY_VERSION, TaxonomyRegistry

logger = get_logger("knovera.ml.query_intent.service")


class QueryIntentServiceError(Exception):
    """Base exception for query intent service failures."""


class QueryIntentModelUnavailableError(QueryIntentServiceError):
    """Raised when the selected model artifact cannot be found or loaded."""


class QueryIntentInferenceError(QueryIntentServiceError):
    """Raised when feature extraction or model prediction fails."""


class QueryIntentValidationError(QueryIntentServiceError):
    """Raised when query input fails validation constraints."""


class QueryIntentService:
    """Thread-safe service managing query intent predictor lifecycle and runtime inference."""

    _instance: Optional["QueryIntentService"] = None
    _lock = threading.Lock()

    def __init__(self, model_dir: Optional[Path] = None) -> None:
        self.settings = get_settings()
        self.model_dir = model_dir or Path(self.settings.QUERY_INTENT_MODEL_DIR)
        self._predictor: Optional[QueryIntentPredictor] = None
        self._initialization_error: Optional[str] = None
        self._load_lock = threading.Lock()
        self._load_model()

    @classmethod
    def get_instance(cls, model_dir: Optional[Path] = None) -> "QueryIntentService":
        """Returns or creates the process-level singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(model_dir=model_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Resets the process-level singleton instance (primarily for testing)."""
        with cls._lock:
            cls._instance = None

    def _load_model(self) -> None:
        """Loads and verifies the approved model artifact once per process."""
        with self._load_lock:
            try:
                manifest_path = self.model_dir / "manifest.json"
                model_path = self.model_dir / "model.joblib"

                if not manifest_path.exists() or not model_path.exists():
                    msg = f"Model artifact files missing in {self.model_dir}"
                    logger.warning(msg)
                    self._initialization_error = msg
                    self._predictor = None
                    return

                predictor = QueryIntentPredictor(self.model_dir)

                # Validate taxonomy compatibility
                if predictor.taxonomy_version != TAXONOMY_VERSION:
                    msg = (
                        f"Model taxonomy version {predictor.taxonomy_version} does not match "
                        f"expected application version {TAXONOMY_VERSION}"
                    )
                    logger.error(msg)
                    self._initialization_error = msg
                    self._predictor = None
                    return

                # Validate expected classes against authoritative taxonomy
                expected_classes = set(TaxonomyRegistry.list_category_ids())
                model_classes = set(predictor.classes_)
                if not expected_classes.issubset(model_classes):
                    missing = expected_classes - model_classes
                    msg = f"Model is missing expected taxonomy categories: {missing}"
                    logger.error(msg)
                    self._initialization_error = msg
                    self._predictor = None
                    return

                self._predictor = predictor
                self._initialization_error = None
                logger.info(
                    "QueryIntentService successfully loaded %s (%s) from %s",
                    predictor.model_id,
                    predictor.model_type,
                    self.model_dir,
                )

            except Exception as exc:
                msg = f"Failed to load query intent model artifact: {exc}"
                logger.error(msg, exc_info=True)
                self._initialization_error = msg
                self._predictor = None

    def is_ready(self) -> Dict[str, Any]:
        """Returns current model readiness and diagnostic metadata."""
        if self._predictor is not None:
            return {
                "status": "ready",
                "model_id": self._predictor.model_id,
                "model_type": self._predictor.model_type,
                "taxonomy_version": self._predictor.taxonomy_version,
                "preprocessing_version": self._predictor.preprocessing_version,
                "classes_count": len(self._predictor.classes_),
                "artifact_dir": str(self.model_dir),
            }
        return {
            "status": "unavailable",
            "error": self._initialization_error,
            "artifact_dir": str(self.model_dir),
            "failure_policy": self.settings.QUERY_INTENT_MODEL_FAILURE_POLICY,
        }

    def validate_query(self, query: str) -> str:
        """Validates and normalizes query string before inference."""
        if not isinstance(query, str):
            raise QueryIntentValidationError("Query must be a string.")
        trimmed = query.strip()
        if not trimmed:
            raise QueryIntentValidationError("Query cannot be empty or whitespace.")
        max_len = getattr(self.settings, "QUERY_INTENT_MAX_QUERY_LENGTH", 2000)
        if len(trimmed) > max_len:
            raise QueryIntentValidationError(
                f"Query length ({len(trimmed)}) exceeds maximum configured limit of {max_len} characters."
            )
        return trimmed

    async def predict(self, raw_query: str) -> QueryIntentPrediction:
        """Asynchronously predicts query intent, offloading CPU-bound inference to worker thread."""
        cleaned_query = self.validate_query(raw_query)

        # Handle unavailable model according to configured failure policy
        if self._predictor is None:
            if self.settings.QUERY_INTENT_MODEL_FAILURE_POLICY == "controlled_error":
                raise QueryIntentModelUnavailableError(
                    self._initialization_error or "Query intent classifier is unavailable."
                )
            # Default RAG fallback prediction
            logger.warning("QueryIntent classifier unavailable; generating default fallback prediction.")
            default_route = getattr(self.settings, "QUERY_INTENT_DEFAULT_ROUTE", "factual_lookup")
            return QueryIntentPrediction(
                query=cleaned_query,
                sanitized_query=cleaned_query,
                normalized_query=cleaned_query.lower(),
                predicted_intent=default_route,
                class_scores={default_route: 1.0},
                score_type="probability",
                model_id="fallback_default",
                model_type="fallback",
                taxonomy_version=TAXONOMY_VERSION,
                preprocessing_version=getattr(self.settings, "QUERY_INTENT_PREPROCESSING_VERSION", "1.0.0"),
                prediction_score=1.0,
                confidence_type="unavailable",
                prediction_latency_ms=0.0,
                top_intents=[{"intent": default_route, "score": 1.0}],
            )

        try:
            # Offload CPU-bound scikit-learn feature extraction and predict call to thread pool
            loop = asyncio.get_running_loop()
            prediction = await loop.run_in_executor(None, self._predictor.predict, cleaned_query)
            return prediction
        except Exception as exc:
            logger.error("Inference failure for query '%s': %s", cleaned_query[:60], exc, exc_info=True)
            if self.settings.QUERY_INTENT_MODEL_FAILURE_POLICY == "controlled_error":
                raise QueryIntentInferenceError(f"Inference failed: {exc}") from exc

            default_route = getattr(self.settings, "QUERY_INTENT_DEFAULT_ROUTE", "factual_lookup")
            return QueryIntentPrediction(
                query=cleaned_query,
                sanitized_query=cleaned_query,
                normalized_query=cleaned_query.lower(),
                predicted_intent=default_route,
                class_scores={default_route: 1.0},
                score_type="probability",
                model_id="fallback_error",
                model_type="fallback",
                taxonomy_version=TAXONOMY_VERSION,
                preprocessing_version=getattr(self.settings, "QUERY_INTENT_PREPROCESSING_VERSION", "1.0.0"),
                prediction_score=1.0,
                confidence_type="unavailable",
                prediction_latency_ms=0.0,
                top_intents=[{"intent": default_route, "score": 1.0}],
            )
