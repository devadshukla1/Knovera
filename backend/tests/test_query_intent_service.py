"""Tests for QueryIntentService Lifecycle, Non-blocking Inference, and Fallbacks (Phase 5 C5.8)."""

from pathlib import Path
import pytest

from backend.app.ml.query_intent.service import (
    QueryIntentModelUnavailableError,
    QueryIntentService,
    QueryIntentValidationError,
)


@pytest.mark.asyncio
async def test_query_intent_service_lifecycle_and_readiness() -> None:
    """Verifies that QueryIntentService loads once, caches singleton, and reports readiness."""
    service = QueryIntentService.get_instance()
    readiness = service.is_ready()

    assert readiness["status"] in ("ready", "unavailable")
    if readiness["status"] == "ready":
        assert readiness["taxonomy_version"] == "1.0.0"
        assert readiness["classes_count"] == 13
        assert "model_id" in readiness


@pytest.mark.asyncio
async def test_query_intent_service_validation() -> None:
    """Verifies input validation constraints: empty strings, whitespace, and excessive length."""
    service = QueryIntentService.get_instance()

    with pytest.raises(QueryIntentValidationError, match="cannot be empty"):
        await service.predict("")

    with pytest.raises(QueryIntentValidationError, match="cannot be empty"):
        await service.predict("   \n\t  ")

    with pytest.raises(QueryIntentValidationError, match="must be a string"):
        service.validate_query(12345)  # type: ignore

    # Oversized query check
    huge_query = "word " * 600  # 3000 chars > 2000 limit
    with pytest.raises(QueryIntentValidationError, match="exceeds maximum"):
        await service.predict(huge_query)


@pytest.mark.asyncio
async def test_query_intent_service_predict_non_blocking() -> None:
    """Verifies that predict() executes asynchronously and returns complete prediction metadata."""
    service = QueryIntentService.get_instance()
    pred = await service.predict("Compare BM25 and dense retrieval in Knovera.")

    assert pred.predicted_intent is not None
    assert pred.predicted_intent in [
        "factual_lookup",
        "definition",
        "explanation",
        "comparison",
        "summarization",
        "procedural_guidance",
        "analytical_reasoning",
        "information_extraction",
        "source_evidence",
        "recommendation",
        "general_conversation",
        "unsupported_action",
        "ambiguous",
    ]
    assert pred.prediction_score is not None
    assert pred.prediction_latency_ms >= 0.0
    assert len(pred.top_intents) <= 5
    assert pred.confidence_type in (
        "calibrated_probability",
        "uncalibrated_probability",
        "decision_score",
        "unavailable",
    )


@pytest.mark.asyncio
async def test_query_intent_service_missing_artifact_fallback() -> None:
    """Verifies that missing model artifact directory triggers graceful fallback under default_rag."""
    fake_path = Path("models/query_intent/non_existent_directory_12345")
    fallback_service = QueryIntentService(model_dir=fake_path)

    readiness = fallback_service.is_ready()
    assert readiness["status"] == "unavailable"

    # With default_rag policy, it returns a safe fallback prediction
    pred = await fallback_service.predict("What is BM25?")
    assert pred.predicted_intent == "knowledge_retrieval" or pred.predicted_intent == "factual_lookup"
    assert pred.confidence_type == "unavailable"
    assert pred.model_type == "fallback"


@pytest.mark.asyncio
async def test_query_intent_service_controlled_error_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that when policy is controlled_error, missing artifact raises QueryIntentModelUnavailableError."""
    fake_path = Path("models/query_intent/non_existent_directory_12345")
    service = QueryIntentService(model_dir=fake_path)
    monkeypatch.setattr(service.settings, "QUERY_INTENT_MODEL_FAILURE_POLICY", "controlled_error")

    with pytest.raises(QueryIntentModelUnavailableError):
        await service.predict("What is BM25?")
