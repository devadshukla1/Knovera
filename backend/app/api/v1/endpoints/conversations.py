"""API endpoints for Knovera conversation management and message exchange (Phase 3 C3.9)."""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.conversations.exceptions import (
    ConversationAccessDeniedError,
    ConversationNotFoundError,
    GenerationAlreadyPendingError,
    InvalidMessageError,
)
from backend.app.conversations.schemas import (
    ChatTurnResponse,
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageSubmitRequest,
)
from backend.app.conversations.service import ConversationService
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.models.user import User

logger = get_logger("knovera.api.conversations")
router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation thread in a workspace",
)
def create_conversation(
    workspace_id: uuid.UUID,
    payload: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    """Creates a personal conversation thread scoped to the authorized workspace."""
    service = ConversationService()
    try:
        return service.create_conversation(
            db=db,
            workspace_id=workspace_id,
            user_id=current_user.id,
            title=payload.title,
            source_scope=payload.source_scope,
        )
    except (ConversationNotFoundError, ConversationAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    except InvalidMessageError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get(
    "/workspaces/{workspace_id}/conversations",
    response_model=ConversationListResponse,
    summary="List conversations in a workspace",
)
def list_conversations(
    workspace_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationListResponse:
    """Lists conversations belonging to the authorized workspace."""
    service = ConversationService()
    try:
        return service.list_conversations(
            db=db,
            workspace_id=workspace_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except (ConversationNotFoundError, ConversationAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")


@router.get(
    "/workspaces/{workspace_id}/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation detail and message history with citations (workspace alias)",
)
@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation detail and message history with citations",
)
def get_conversation_detail(
    conversation_id: uuid.UUID,
    workspace_id: Optional[uuid.UUID] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    """Retrieves conversation thread and ordered message history with citations."""
    service = ConversationService()
    try:
        return service.get_conversation_detail(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except (ConversationNotFoundError, ConversationAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


class ConversationRenameRequest(BaseModel):
    title: str


@router.patch(
    "/workspaces/{workspace_id}/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Rename conversation thread (workspace alias)",
)
@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Rename conversation thread",
)
def rename_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationRenameRequest,
    workspace_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    """Renames an existing conversation."""
    service = ConversationService()
    try:
        return service.rename_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            new_title=payload.title,
        )
    except (ConversationNotFoundError, ConversationAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.delete(
    "/workspaces/{workspace_id}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation thread (workspace alias)",
)
@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation thread",
)
def delete_conversation(
    conversation_id: uuid.UUID,
    workspace_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes an entire conversation thread and its messages."""
    service = ConversationService()
    try:
        service.delete_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
        return None
    except (ConversationNotFoundError, ConversationAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatTurnResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit user question and receive grounded response with citations",
)
async def submit_message(
    conversation_id: uuid.UUID,
    payload: MessageSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatTurnResponse:
    """Processes user question, retrieves evidence, generates grounded answer, and saves turn."""
    service = ConversationService()
    try:
        return await service.submit_message(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            request=payload,
        )
    except (ConversationNotFoundError, ConversationAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    except GenerationAlreadyPendingError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))
    except InvalidMessageError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        logger.error("Unhandled message submission failure: %s", err, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Answer generation failed")


class WorkspaceChatPayload(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    selected_document_ids: Optional[List[str]] = None


@router.post(
    "/workspaces/{workspace_id}/chat",
    status_code=status.HTTP_200_OK,
    summary="Direct workspace chat turn endpoint for interactive Research Chat",
)
async def workspace_chat(
    workspace_id: uuid.UUID,
    payload: WorkspaceChatPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Processes user question within workspace context, returning a grounded or general knowledge response."""
    service = ConversationService()
    conv_id: Optional[uuid.UUID] = None
    if payload.conversation_id:
        try:
            conv_id = uuid.UUID(str(payload.conversation_id))
        except (ValueError, TypeError):
            conv_id = None

    if conv_id:
        try:
            service.get_conversation(db=db, conversation_id=conv_id, user_id=current_user.id)
        except Exception:
            conv_id = None

    if not conv_id:
        title = payload.message[:60].strip() or "Research Chat"
        new_conv = service.create_conversation(
            db=db,
            workspace_id=workspace_id,
            user_id=current_user.id,
            title=title,
        )
        conv_id = new_conv.id

    doc_uuids = None
    if payload.selected_document_ids:
        doc_uuids = [uuid.UUID(str(d)) for d in payload.selected_document_ids]

    turn_req = MessageSubmitRequest(
        content=payload.message,
        document_ids=doc_uuids,
    )

    try:
        turn_res = await service.submit_message(
            db=db,
            conversation_id=conv_id,
            user_id=current_user.id,
            request=turn_req,
        )
    except Exception as exc:
        logger.error("Workspace chat failed: %s", exc, exc_info=True)
        from backend.app.llm.exceptions import (
            ProviderAuthenticationError,
            ProviderConfigurationError,
            ProviderInvalidRequestError,
            ProviderRateLimitError,
            ProviderTimeoutError,
        )
        detail_msg = str(exc) if hasattr(exc, "detail") else getattr(exc, "message", str(exc))
        if isinstance(exc, ProviderAuthenticationError):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Groq authentication failed: {detail_msg}. Please verify GROQ_API_KEY in backend .env.",
            )
        if isinstance(exc, ProviderRateLimitError):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Groq rate limit exceeded: {detail_msg}",
            )
        if isinstance(exc, ProviderTimeoutError):
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Groq inference timed out: {detail_msg}",
            )
        if isinstance(exc, ProviderInvalidRequestError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid LLM request or model configuration: {detail_msg}",
            )
        if isinstance(exc, ProviderConfigurationError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"LLM provider is not configured on the server: {detail_msg}",
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Generation failed: {detail_msg}")

    # Build response format expected by frontend ChatMessage
    citations = []
    for c in turn_res.citations:
        cit_id = getattr(c, "citation_id", None) or getattr(c, "id", None) or uuid.uuid4()
        cit_num = getattr(c, "display_number", None) or getattr(c, "display_order", 1)
        doc_id = getattr(c, "document_id", "")
        doc_title = getattr(c, "document_name", None) or getattr(c, "document_title", None) or "Document"
        page_num = getattr(c, "page_start", None) or getattr(c, "page_end", None)
        snippet = getattr(c, "quote_text", None) or getattr(c, "excerpt", None) or getattr(c, "snippet", "")
        score = getattr(c, "relevance_score", None) or getattr(c, "confidence_score", None)

        citations.append({
            "id": str(cit_id),
            "citation_number": cit_num,
            "document_id": str(doc_id),
            "document_title": doc_title,
            "page_number": page_num,
            "snippet": snippet,
            "confidence_score": score,
        })

    return {
        "id": str(turn_res.assistant_message.id),
        "conversation_id": str(conv_id),
        "role": "assistant",
        "content": turn_res.assistant_message.content,
        "citations": citations,
        "evidence_status": "insufficient" if turn_res.insufficient_evidence else "full",
        "created_at": turn_res.assistant_message.created_at.isoformat(),
    }
