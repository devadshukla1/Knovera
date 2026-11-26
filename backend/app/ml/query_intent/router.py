"""Centralized Query Intent Router for Knovera Module Dispatch (Phase 5 C5.9).

Translates validated query intent predictions into structured module routing decisions,
enforcing confidence thresholds, fallback policies, and strict access isolation.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, Optional

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.ml.query_intent.predictor import QueryIntentPrediction
from backend.app.ml.query_intent.taxonomy import TaxonomyRegistry

logger = get_logger("knovera.ml.query_intent.router")

ROUTING_CONFIG_VERSION = "1.0.0"

# Authoritative Intent-to-Module Mapping for all 13 Categories
INTENT_ROUTES: Dict[str, Dict[str, Any]] = {
    "factual_lookup": {
        "module": "knowledge_retrieval",
        "retrieval_mode": "hybrid",
        "retrieval_profile": "factual",
        "requires_retrieval": True,
        "requires_citations": True,
        "requires_clarification": False,
        "requires_capability_response": False,
        "description": "Standard knowledge retrieval for direct facts, numbers, dates, and metrics.",
    },
    "definition": {
        "module": "concept_explanation",
        "retrieval_mode": "hybrid",
        "retrieval_profile": "definition",
        "requires_retrieval": True,
        "requires_citations": True,
        "requires_clarification": False,
        "requires_capability_response": False,
        "description": "Concept explanation prioritizing definitional and terminological passages.",
    },
    "explanation": {
        "module": "explanatory_retrieval",
        "retrieval_mode": "hybrid",
        "retrieval_profile": "explanatory",
        "requires_retrieval": True,
        "requires_citations": True,
        "requires_clarification": False,
        "requires_capability_response": False,
        "description": "Explanatory knowledge retrieval for mechanisms, causes, and workflows.",
    },
    "comparison": {
        "module": "comparative_retrieval",
        "retrieval_mode": "hybrid",
        "retrieval_profile": "comparative",
        "requires_retrieval": True,
        "requires_citations": True,
        "requires_clarification": False,
        "requires_capability_response": False,
        "description": "Comparative retrieval contrasting multiple entities, algorithms, or techniques.",
    },
    "summarization": {
        "module": "summarization",
        "retrieval_mode": "hybrid",
        "retrieval_profile": "summarization",
        "requires_retrieval": True,
        "requires_citations": True,
        "requires_clarification": False,
        "requires_capability_response": False,
        "description": "Summarization workflow condensing representative scope across documents.",
    },
    "procedural_guidance": {
        "module": "procedural_guidance",
        "retrieval_mode": "hybrid",
        "retrieval_profile": "procedural",
        "requires_retrieval": True,
        "requires_citations": True,
        "requires_clarification": False,
        "requires_capability_response": False,
        "description": "Step-by-step guidance workflow preserving ordered procedural methods.",
    },
    "analytical_reasoning": {
        "module": "evidence_analysis",
        "retrieval_mode": "hybrid",
        "retrieval_profile": "analytical",
        "requires_retrieval": True,
        "requires_citations": True,
        "requires_clarification": False,
        "requires_capability_response": False,
        "description": "Evidence analysis interpreting findings, evaluations, and trade-offs.",
    },
    "information_extraction": {
        "module": "structured_extraction",
        "retrieval_mode": "hybrid",
        "retrieval_profile": "extraction",
        "requires_retrieval": True,
        "requires_citations": True,
        "requires_clarification": False,
        "requires_capability_response": False,
        "description": "Structured information extraction compiling lists, entities, and parameters.",
    },
    "source_evidence": {
        "module": "citation_retrieval",
        "retrieval_mode": "hybrid",
        "retrieval_profile": "citation",
        "requires_retrieval": True,
        "requires_citations": True,
        "requires_clarification": False,
        "requires_capability_response": False,
        "description": "Evidence and citation retrieval pinpointing exact source citations and pages.",
    },
    "recommendation": {
        "module": "evidence_based_recommendation",
        "retrieval_mode": "hybrid",
        "retrieval_profile": "recommendation",
        "requires_retrieval": True,
        "requires_citations": True,
        "requires_clarification": False,
        "requires_capability_response": False,
        "description": "Evidence-based recommendation providing source-backed selection guidance.",
    },
    "general_conversation": {
        "module": "general_conversation",
        "retrieval_mode": None,
        "retrieval_profile": None,
        "requires_retrieval": False,
        "requires_citations": False,
        "requires_clarification": False,
        "requires_capability_response": False,
        "description": "General conversational handler bypassing document retrieval.",
    },
    "unsupported_action": {
        "module": "capability_boundary",
        "retrieval_mode": None,
        "retrieval_profile": None,
        "requires_retrieval": False,
        "requires_citations": False,
        "requires_clarification": False,
        "requires_capability_response": True,
        "description": "Capability boundary handler explaining unsupported external operations.",
    },
    "ambiguous": {
        "module": "clarification",
        "retrieval_mode": None,
        "retrieval_profile": None,
        "requires_retrieval": False,
        "requires_citations": False,
        "requires_clarification": True,
        "requires_capability_response": False,
        "description": "Clarification handler prompting for required conversational details.",
    },
}


@dataclass(frozen=True)
class IntentRoutingDecision:
    """Structured decision produced by IntentRouter to guide downstream execution."""

    predicted_intent: str
    selected_module: str
    retrieval_mode: Optional[str]
    retrieval_profile: Optional[str]
    requires_retrieval: bool
    requires_citations: bool
    requires_clarification: bool
    requires_capability_response: bool
    confidence: Optional[float]
    confidence_type: str
    routing_reason: str
    fallback_applied: bool
    fallback_reason: Optional[str]
    routing_config_version: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializes routing decision to dictionary."""
        return {
            "predicted_intent": self.predicted_intent,
            "selected_module": self.selected_module,
            "retrieval_mode": self.retrieval_mode,
            "retrieval_profile": self.retrieval_profile,
            "requires_retrieval": self.requires_retrieval,
            "requires_citations": self.requires_citations,
            "requires_clarification": self.requires_clarification,
            "requires_capability_response": self.requires_capability_response,
            "confidence": self.confidence,
            "confidence_type": self.confidence_type,
            "routing_reason": self.routing_reason,
            "fallback_applied": self.fallback_applied,
            "fallback_reason": self.fallback_reason,
            "routing_config_version": self.routing_config_version,
        }


class IntentRouter:
    """Evaluates predicted intent and confidence to select the appropriate Knovera processing module."""

    def __init__(
        self,
        confidence_threshold: Optional[float] = None,
        low_confidence_policy: Optional[str] = None,
        default_route: Optional[str] = None,
    ) -> None:
        self.settings = get_settings()
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else getattr(self.settings, "QUERY_INTENT_CONFIDENCE_THRESHOLD", 0.30)
        )
        self.low_confidence_policy = (
            low_confidence_policy
            or getattr(self.settings, "QUERY_INTENT_LOW_CONFIDENCE_POLICY", "default_rag")
        )
        self.default_route = (
            default_route or getattr(self.settings, "QUERY_INTENT_DEFAULT_ROUTE", "knowledge_retrieval")
        )
        self.config_version = getattr(
            self.settings, "QUERY_INTENT_ROUTING_CONFIG_VERSION", ROUTING_CONFIG_VERSION
        )

    def route(self, prediction: QueryIntentPrediction) -> IntentRoutingDecision:
        """Determines the application module and retrieval profile for a given query prediction.

        Rules:
            1. Validates intent against authoritative taxonomy. Invalid intents trigger safe fallback.
            2. If confidence is available and below the configured threshold:
               - Low-confidence predictions fall back to standard hybrid RAG (or configured policy).
               - Avoids dispatching uncertain queries to specialized handlers.
            3. Differentiates high-confidence 'ambiguous' intent from low-confidence prediction.
            4. High-confidence non-retrieval routes ('general_conversation', 'unsupported_action',
               'ambiguous') are dispatched to their specific handlers without document retrieval.
            5. Knowledge retrieval intents are routed with specialized retrieval profiles.
        """
        intent = prediction.predicted_intent
        confidence = prediction.prediction_score
        confidence_type = prediction.confidence_type

        # 1. Validate taxonomy membership
        if not TaxonomyRegistry.is_valid_category(intent):
            logger.warning("Unrecognized intent category '%s'; falling back to default RAG", intent)
            return self._build_fallback_decision(
                intent=intent,
                confidence=confidence,
                confidence_type=confidence_type,
                reason="Unrecognized intent label not present in authoritative taxonomy.",
                fallback_reason="invalid_intent_label",
            )

        # 2. Check for missing or unavailable confidence
        if confidence is None or confidence_type == "unavailable":
            logger.info("Prediction confidence unavailable for intent '%s'; applying safe fallback", intent)
            return self._build_fallback_decision(
                intent=intent,
                confidence=confidence,
                confidence_type=confidence_type,
                reason="Confidence score unavailable; safely defaulted to standard hybrid retrieval.",
                fallback_reason="confidence_unavailable",
            )

        # 3. Check Confidence Threshold
        # For decision_scores (SVM), thresholding requires different scales; for probabilities, threshold is [0.0, 1.0]
        is_low_confidence = False
        if confidence_type in ("calibrated_probability", "uncalibrated_probability"):
            if confidence < self.confidence_threshold:
                is_low_confidence = True

        if is_low_confidence:
            # Low confidence: Do not send to specialized routes (e.g. clarification or conversational)
            logger.info(
                "Prediction for '%s' had low confidence (%.4f < %.2f); falling back to default RAG",
                intent,
                confidence,
                self.confidence_threshold,
            )
            return self._build_fallback_decision(
                intent=intent,
                confidence=confidence,
                confidence_type=confidence_type,
                reason=(
                    f"Confidence score {confidence:.4f} is below the established threshold "
                    f"of {self.confidence_threshold:.2f}."
                ),
                fallback_reason="low_confidence",
            )

        # 4. High Confidence: Dispatch according to authoritative route
        route_info = INTENT_ROUTES.get(intent)
        if not route_info:
            return self._build_fallback_decision(
                intent=intent,
                confidence=confidence,
                confidence_type=confidence_type,
                reason=f"No route registered for valid intent '{intent}'.",
                fallback_reason="unregistered_route",
            )

        routing_reason = (
            f"Intent '{intent}' predicted with confidence {confidence:.4f} ({confidence_type}); "
            f"dispatched to module '{route_info['module']}' ({route_info['description']})."
        )

        return IntentRoutingDecision(
            predicted_intent=intent,
            selected_module=route_info["module"],
            retrieval_mode=route_info["retrieval_mode"],
            retrieval_profile=route_info["retrieval_profile"],
            requires_retrieval=route_info["requires_retrieval"],
            requires_citations=route_info["requires_citations"],
            requires_clarification=route_info["requires_clarification"],
            requires_capability_response=route_info["requires_capability_response"],
            confidence=confidence,
            confidence_type=confidence_type,
            routing_reason=routing_reason,
            fallback_applied=False,
            fallback_reason=None,
            routing_config_version=self.config_version,
        )

    def _build_fallback_decision(
        self,
        intent: str,
        confidence: Optional[float],
        confidence_type: str,
        reason: str,
        fallback_reason: str,
    ) -> IntentRoutingDecision:
        """Constructs safe default hybrid RAG routing decision."""
        default_info = INTENT_ROUTES.get("factual_lookup", {})
        return IntentRoutingDecision(
            predicted_intent=intent,
            selected_module=self.default_route,
            retrieval_mode="hybrid",
            retrieval_profile="default",
            requires_retrieval=True,
            requires_citations=True,
            requires_clarification=False,
            requires_capability_response=False,
            confidence=confidence,
            confidence_type=confidence_type,
            routing_reason=f"Fallback applied: {reason}",
            fallback_applied=True,
            fallback_reason=fallback_reason,
            routing_config_version=self.config_version,
        )
