"""Pydantic schemas for Knovera Revision Recommendations (Phase 9 C9.7)."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class RecommendationType(str, Enum):
    """Taxonomy of revision recommendations (C9.7)."""
    REVISE_CONCEPT = "revise_concept"
    PRACTICE_CONCEPT = "practice_concept"
    REINFORCE_CONCEPT = "reinforce_concept"
    REVIEW_SOURCE_MATERIAL = "review_source_material"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_ACTION_NEEDED = "no_action_needed"


class RecommendationPriority(str, Enum):
    """Priority bands for recommendation ranking (C9.7)."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationStatus(str, Enum):
    """Lifecycle state of a revision recommendation."""
    SUGGESTED = "suggested"
    VIEWED = "viewed"
    STARTED = "started"
    COMPLETED = "completed"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class RevisionRecommendationStatusUpdate(BaseModel):
    """Payload to update recommendation status."""
    status: RecommendationStatus


class RevisionRecommendationGenerateRequest(BaseModel):
    """Payload to trigger recommendation generation."""
    force_regenerate: bool = Field(
        default=False,
        description="Whether to archive previously suggested recommendations and re-evaluate candidates"
    )
    max_recommendations: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of active recommendations to return"
    )


class LinkedResourceItem(BaseModel):
    """A learning material linked to a concept recommendation."""
    resource_type: str = Field(description="revision_note, flashcard, question, or document_chunk")
    resource_id: UUID
    title: str
    preview: Optional[str] = None
    document_id: Optional[UUID] = None
    page_number: Optional[int] = None


class LinkedResources(BaseModel):
    """Collection of linked materials supporting a recommendation."""
    revision_notes: List[LinkedResourceItem] = Field(default_factory=list)
    flashcards: List[LinkedResourceItem] = Field(default_factory=list)
    practice_questions: List[LinkedResourceItem] = Field(default_factory=list)
    source_chunks: List[LinkedResourceItem] = Field(default_factory=list)


class RevisionRecommendationResponse(BaseModel):
    """Representation of an actionable, explainable revision recommendation."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    user_id: UUID
    concept_id: UUID
    concept_name: Optional[str] = None
    concept_description: Optional[str] = None
    recommendation_type: RecommendationType
    priority: RecommendationPriority
    explanation: str
    evidence_summary: Dict[str, Any]
    model_version_id: Optional[UUID] = None
    status: RecommendationStatus
    linked_resources: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ConceptRevisionResourcesResponse(BaseModel):
    """Revision resources available for a specific concept."""
    concept_id: UUID
    concept_name: str
    revision_notes: List[Dict[str, Any]] = Field(default_factory=list)
    flashcards: List[Dict[str, Any]] = Field(default_factory=list)
    practice_questions: List[Dict[str, Any]] = Field(default_factory=list)
    source_documents: List[Dict[str, Any]] = Field(default_factory=list)
