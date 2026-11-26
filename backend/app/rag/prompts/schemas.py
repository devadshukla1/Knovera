"""Schemas for Prompt Engineering and Structured Generation (Phase 3 C3.6)."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.llm.schemas import ChatMessage
from backend.app.rag.context.schemas import ContextPackage


class FactClaim(BaseModel):
    """Specific factual claim associated with supporting prompt-local source IDs."""

    text: str = Field(..., min_length=1, description="Factual assertion extracted from response")
    source_ids: List[str] = Field(default_factory=list, description="List of source IDs, e.g. ['S1', 'S2']")


class StructuredAnswerDraft(BaseModel):
    """Structured generation output from the LLM."""

    model_config = ConfigDict(from_attributes=True)

    answer: str = Field(..., description="Complete narrative answer text")
    claims: List[FactClaim] = Field(default_factory=list, description="Extracted factual claims with source IDs")
    limitations: List[str] = Field(default_factory=list, description="Noted evidence gaps or limitations")
    insufficient_evidence: bool = Field(
        default=False,
        description="True if provided documents lacked adequate evidence to answer the question",
    )
    answering_mode: Optional[str] = Field(
        default="mode_a",
        description="Detected answering mode: 'mode_a' (found), 'mode_b' (not found), 'mode_c' (partial)",
    )


class PromptInput(BaseModel):
    """Input parameters for prompt template rendering."""

    query: str = Field(..., min_length=1)
    context_package: ContextPackage
    conversation_history: Optional[List[ChatMessage]] = None
    task_type: str = Field(default="general_qa")


class RenderedPrompt(BaseModel):
    """Complete rendered prompt bundle ready for LLM consumption."""

    system_instruction: str
    messages: List[ChatMessage]
    prompt_version: str
    prompt_hash: str
    source_mapping: Dict[str, Any]
