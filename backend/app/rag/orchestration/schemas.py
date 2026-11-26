"""Schemas for RAG orchestration and grounded answer generation (Phase 3 C3.7)."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.citations.schemas import CitationDraft
from backend.app.rag.context.schemas import ContextPackage
from backend.app.rag.prompts.schemas import FactClaim


class GroundedAnswerDraft(BaseModel):
    """Complete in-memory generation result before database persistence."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    answer: str = Field(..., description="User-facing narrative answer text")
    claims: List[FactClaim] = Field(default_factory=list, description="Claim-to-source associations")
    limitations: List[str] = Field(default_factory=list, description="Explicitly noted caveats or gaps")
    insufficient_evidence: bool = Field(default=False, description="True if evidence was absent or inadequate")
    answering_mode: Optional[str] = Field(default="mode_a", description="Detected mode: 'mode_a', 'mode_b', or 'mode_c'")

    context_package: ContextPackage = Field(..., description="Authoritative context used during generation")
    citation_drafts: List[CitationDraft] = Field(default_factory=list, description="Resolved citation records")

    model_provider: str = Field(..., description="LLM provider adapter used (e.g. 'groq', 'gemini', 'mock')")
    model_name: str = Field(..., description="Specific model used for completion")
    latency_ms: int = Field(default=0, ge=0, description="Total generation duration in milliseconds")
    prompt_version: str = Field(..., description="Prompt template version string")
    retrieval_metrics: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic duration metrics")
