"""Tests for Centralized IntentRouter and Module Dispatch (Phase 5 C5.9)."""

import pytest

from backend.app.ml.query_intent.predictor import QueryIntentPrediction
from backend.app.ml.query_intent.router import (
    INTENT_ROUTES,
    ROUTING_CONFIG_VERSION,
    IntentRouter,
    IntentRoutingDecision,
)
from backend.app.ml.query_intent.taxonomy import TaxonomyRegistry


def _make_prediction(
    intent: str,
    score: float = 0.85,
    confidence_type: str = "uncalibrated_probability",
) -> QueryIntentPrediction:
    """Helper to construct QueryIntentPrediction for routing tests."""
    return QueryIntentPrediction(
        query="Sample test query",
        sanitized_query="Sample test query",
        normalized_query="sample test query",
        predicted_intent=intent,
        class_scores={intent: score},
        score_type="probability",
        model_id="test_model",
        model_type="logistic_regression",
        taxonomy_version="1.0.0",
        preprocessing_version="1.0.0",
        prediction_score=score,
        confidence_type=confidence_type,
        prediction_latency_ms=1.5,
        top_intents=[{"intent": intent, "score": score}],
    )


def test_router_all_13_categories_have_valid_routes() -> None:
    """Verifies that every category in the authoritative taxonomy has an explicit route in INTENT_ROUTES."""
    all_categories = TaxonomyRegistry.list_category_ids()
    assert len(all_categories) == 13

    for category in all_categories:
        assert category in INTENT_ROUTES
        route = INTENT_ROUTES[category]
        assert "module" in route
        assert "requires_retrieval" in route
        assert "requires_citations" in route
        assert "requires_clarification" in route
        assert "requires_capability_response" in route


def test_router_knowledge_retrieval_intents() -> None:
    """Verifies that knowledge-intensive intents dispatch to their mapped modules with retrieval and citations required."""
    router = IntentRouter(confidence_threshold=0.50)
    knowledge_intents = [
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
    ]

    for intent in knowledge_intents:
        pred = _make_prediction(intent=intent, score=0.92)
        decision: IntentRoutingDecision = router.route(pred)

        assert decision.predicted_intent == intent
        assert decision.fallback_applied is False
        assert decision.requires_retrieval is True
        assert decision.requires_citations is True
        assert decision.requires_clarification is False
        assert decision.requires_capability_response is False
        assert decision.retrieval_mode == "hybrid"
        assert decision.retrieval_profile is not None


def test_router_general_conversation_intent() -> None:
    """Verifies that general_conversation bypasses document retrieval and citation requirements."""
    router = IntentRouter(confidence_threshold=0.50)
    pred = _make_prediction(intent="general_conversation", score=0.88)
    decision = router.route(pred)

    assert decision.selected_module == "general_conversation"
    assert decision.requires_retrieval is False
    assert decision.requires_citations is False
    assert decision.requires_clarification is False
    assert decision.requires_capability_response is False
    assert decision.fallback_applied is False


def test_router_unsupported_action_intent() -> None:
    """Verifies that unsupported_action routes to capability boundary handler without retrieval."""
    router = IntentRouter(confidence_threshold=0.50)
    pred = _make_prediction(intent="unsupported_action", score=0.95)
    decision = router.route(pred)

    assert decision.selected_module == "capability_boundary"
    assert decision.requires_retrieval is False
    assert decision.requires_citations is False
    assert decision.requires_capability_response is True
    assert decision.fallback_applied is False


def test_router_high_confidence_ambiguous_intent() -> None:
    """Verifies that high-confidence ambiguous intent routes to clarification handler."""
    router = IntentRouter(confidence_threshold=0.50)
    pred = _make_prediction(intent="ambiguous", score=0.75)
    decision = router.route(pred)

    assert decision.selected_module == "clarification"
    assert decision.requires_retrieval is False
    assert decision.requires_citations is False
    assert decision.requires_clarification is True
    assert decision.fallback_applied is False


def test_router_low_confidence_fallback() -> None:
    """Verifies that low confidence (< threshold) safely triggers fallback to default hybrid RAG."""
    router = IntentRouter(confidence_threshold=0.30)
    # Low confidence on explanation intent (below 0.30)
    pred = _make_prediction(intent="explanation", score=0.20)
    decision = router.route(pred)

    assert decision.fallback_applied is True
    assert decision.fallback_reason == "low_confidence"
    assert decision.selected_module == "knowledge_retrieval"
    assert decision.requires_retrieval is True
    assert decision.requires_citations is True


def test_router_distinguishes_high_ambiguous_from_low_confidence() -> None:
    """Verifies the critical distinction between a high-confidence ambiguous prediction and a low-confidence prediction."""
    router = IntentRouter(confidence_threshold=0.30)

    # 1. High-confidence ambiguous -> Clarification handler
    high_ambig = _make_prediction(intent="ambiguous", score=0.80)
    dec_ambig = router.route(high_ambig)
    assert dec_ambig.selected_module == "clarification"
    assert dec_ambig.requires_clarification is True
    assert dec_ambig.fallback_applied is False

    # 2. Low-confidence ambiguous -> Default RAG fallback (does not assume user was ambiguous)
    low_ambig = _make_prediction(intent="ambiguous", score=0.20)
    dec_low_ambig = router.route(low_ambig)
    assert dec_low_ambig.selected_module == "knowledge_retrieval"
    assert dec_low_ambig.fallback_applied is True
    assert dec_low_ambig.fallback_reason == "low_confidence"

    # 3. Low-confidence factual -> Default RAG fallback
    low_factual = _make_prediction(intent="factual_lookup", score=0.20)
    dec_low_fact = router.route(low_factual)
    assert dec_low_fact.selected_module == "knowledge_retrieval"
    assert dec_low_fact.fallback_applied is True
    assert dec_low_fact.fallback_reason == "low_confidence"


def test_router_invalid_intent_fallback() -> None:
    """Verifies that unrecognized intent categories trigger safe default RAG fallback."""
    router = IntentRouter(confidence_threshold=0.50)
    pred = _make_prediction(intent="completely_invalid_intent", score=0.99)
    decision = router.route(pred)

    assert decision.fallback_applied is True
    assert decision.fallback_reason == "invalid_intent_label"
    assert decision.selected_module == "knowledge_retrieval"
    assert decision.requires_retrieval is True


def test_router_unavailable_confidence_fallback() -> None:
    """Verifies that predictions with unavailable confidence fall back safely."""
    router = IntentRouter(confidence_threshold=0.50)
    pred = _make_prediction(intent="factual_lookup", score=1.0, confidence_type="unavailable")
    decision = router.route(pred)

    assert decision.fallback_applied is True
    assert decision.fallback_reason == "confidence_unavailable"
    assert decision.selected_module == "knowledge_retrieval"
