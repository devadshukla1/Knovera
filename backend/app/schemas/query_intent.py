"""Pydantic schemas for Query Intent Classification API (Phase 5 C5.8)."""

from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class QueryIntentRequest(BaseModel):
    """Request payload for standalone query intent prediction."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language query string to classify.",
        examples=["Compare TF-IDF and BM25 in information retrieval."],
    )
    workspace_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional workspace ID to enforce access authorization context.",
    )

    model_config = ConfigDict(extra="forbid")


class TopIntentScore(BaseModel):
    """Ranked intent score."""

    intent: str = Field(..., description="Taxonomy intent category ID.")
    score: float = Field(..., description="Posterior probability or decision score.")


class QueryIntentResponse(BaseModel):
    """Structured response for query intent prediction."""

    predicted_intent: str = Field(..., description="Authoritative primary predicted intent category.")
    top_intents: List[TopIntentScore] = Field(
        default_factory=list,
        description="Ranked list of top candidate intents with scores.",
    )
    prediction_score: Optional[float] = Field(
        default=None,
        description="Primary prediction score or confidence.",
    )
    confidence_type: str = Field(
        ...,
        description="Confidence interpretation ('calibrated_probability', 'uncalibrated_probability', 'decision_score', 'unavailable').",
    )
    model_type: str = Field(..., description="Classifier architecture family (e.g. 'logistic_regression').")
    model_version: str = Field(..., description="Model version or model identifier.")
    taxonomy_version: str = Field(..., description="Authoritative taxonomy schema version (e.g. '1.0.0').")
    preprocessing_version: str = Field(..., description="Preprocessing pipeline version (e.g. '1.0.0').")
    prediction_latency_ms: float = Field(..., description="End-to-end inference latency in milliseconds.")
    sanitized_query: Optional[str] = Field(
        default=None,
        description="Preprocessed and sanitized query string (with sensitive entities redacted).",
    )

    model_config = ConfigDict(from_attributes=True)


class QueryIntentReadinessResponse(BaseModel):
    """Health diagnostic status of query intent prediction service."""

    status: str = Field(..., description="Readiness status ('ready' or 'unavailable').")
    model_id: Optional[str] = None
    model_type: Optional[str] = None
    taxonomy_version: Optional[str] = None
    preprocessing_version: Optional[str] = None
    classes_count: Optional[int] = None
    artifact_dir: Optional[str] = None
    error: Optional[str] = None
