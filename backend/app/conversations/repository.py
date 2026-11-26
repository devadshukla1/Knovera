"""Conversation repository for database operations on conversations and messages (Phase 3 C3.9)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import case, desc
from sqlalchemy.orm import Session

from backend.app.models.citation import Citation
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message


class ConversationRepository:
    """Handles CRUD persistence for conversations and messages."""

    def create_conversation(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        source_scope: Dict[str, Any],
    ) -> Conversation:
        """Creates a new conversation thread."""
        conversation = Conversation(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            created_by_user_id=user_id,
            title=title,
            source_scope=source_scope or {},
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    def get_conversation(
        self,
        db: Session,
        conversation_id: uuid.UUID,
    ) -> Optional[Conversation]:
        """Loads a conversation by ID."""
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()

    def list_conversations(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Conversation], int]:
        """Lists conversations for an authorized workspace ordered by last updated."""
        query = db.query(Conversation).filter(Conversation.workspace_id == workspace_id)
        total = query.count()
        items = (
            query.order_by(desc(Conversation.updated_at), desc(Conversation.id))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def update_title(
        self,
        db: Session,
        conversation_id: uuid.UUID,
        new_title: str,
    ) -> None:
        """Updates conversation title."""
        db.query(Conversation).filter(Conversation.id == conversation_id).update(
            {"title": new_title[:200], "updated_at": datetime.now(timezone.utc)}
        )
        db.commit()

    def delete_conversation(
        self,
        db: Session,
        conversation_id: uuid.UUID,
    ) -> bool:
        """Deletes a conversation and cascades to messages and citations."""
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conv:
            return False
        db.delete(conv)
        db.commit()
        return True

    def create_message(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        status: str = "complete",
        client_request_id: Optional[uuid.UUID] = None,
        in_reply_to_message_id: Optional[uuid.UUID] = None,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        retrieval_metadata: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[int] = None,
        failure_code: Optional[str] = None,
    ) -> Message:
        """Creates a single message entry."""
        msg = Message(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            status=status,
            client_request_id=client_request_id,
            in_reply_to_message_id=in_reply_to_message_id,
            model_provider=model_provider,
            model_name=model_name,
            retrieval_metadata=retrieval_metadata or {},
            latency_ms=latency_ms,
            failure_code=failure_code,
        )
        db.add(msg)
        return msg

    def get_user_message_by_client_request_id(
        self,
        db: Session,
        conversation_id: uuid.UUID,
        client_request_id: uuid.UUID,
    ) -> Optional[Message]:
        """Checks for existing user message submitted with client_request_id."""
        return (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.client_request_id == client_request_id,
                Message.role == "user",
            )
            .first()
        )

    def get_assistant_reply_for_user_message(
        self,
        db: Session,
        user_message_id: uuid.UUID,
    ) -> Optional[Message]:
        """Finds assistant message linked in reply to a given user message."""
        return (
            db.query(Message)
            .filter(
                Message.in_reply_to_message_id == user_message_id,
                Message.role == "assistant",
            )
            .first()
        )

    def get_pending_assistant_message(
        self,
        db: Session,
        conversation_id: uuid.UUID,
    ) -> Optional[Message]:
        """Checks if a generation is currently pending in this conversation."""
        return (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
                Message.status == "pending",
            )
            .order_by(desc(Message.created_at))
            .first()
        )

    def list_messages(
        self,
        db: Session,
        conversation_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """Returns messages in deterministic chronological order: (created_at ASC, role 'user' first, id ASC)."""
        role_priority = case((Message.role == "user", 0), else_=1)
        return (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), role_priority.asc(), Message.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
