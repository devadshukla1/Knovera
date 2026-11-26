"""Pydantic schemas for Knovera conversation management and chat turns (Phase 3 C3.9)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from backend.app.citations.schemas import CitationDetail


class ConversationCreateRequest(BaseModel):
    """Input payload to create a new conversation thread."""

    title: Optional[str] = Field(None, max_length=200, description="Optional custom title for the conversation")
    source_scope: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Default document filters or scope")


class ConversationResponse(BaseModel):
    """Public summary representation of a conversation thread."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    created_by_user_id: uuid.UUID
    title: str
    source_scope: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """Paginated list of conversations within a workspace."""

    items: List[ConversationResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class MessageSubmitRequest(BaseModel):
    """Payload to submit a user question to an existing conversation."""

    content: str = Field(..., min_length=1, max_length=4000, description="User question or research prompt")
    client_request_id: Optional[uuid.UUID] = Field(None, description="Client idempotency UUID token")
    document_ids: Optional[List[uuid.UUID]] = Field(None, description="Optional document filter overriding default scope")


class MessageResponse(BaseModel):
    """Single message in a conversation thread with associated citations."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    workspace_id: uuid.UUID
    role: str
    content: str
    status: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    latency_ms: Optional[int] = None
    failure_code: Optional[str] = None
    created_at: datetime
    citations: List[CitationDetail] = Field(default_factory=list)


class ConversationDetailResponse(BaseModel):
    """Full conversation history including ordered messages and their citations."""

    conversation: ConversationResponse
    messages: List[MessageResponse]


class ChatTurnResponse(BaseModel):
    """Atomic response for a submitted user question and its generated answer."""

    conversation_id: uuid.UUID
    user_message: MessageResponse
    assistant_message: MessageResponse
    citations: List[CitationDetail] = Field(default_factory=list)
    insufficient_evidence: bool = False
    limitations: List[str] = Field(default_factory=list)
