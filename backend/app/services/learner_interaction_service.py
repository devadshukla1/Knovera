"""Learner Interaction Service for Knovera Learner Intelligence Foundation (Phase 9 C9.2).

Captures normalized educational interaction events across questions, answers, and study materials.
Enforces anti-tampering (scores/correctness can never be injected by clients), idempotency keys,
and strict multi-tenant workspace/user isolation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.learner_intelligence import LearnerInteractionEvent
from backend.app.models.study_material import QuizAttempt
from backend.app.schemas.learner_intelligence import (
    LearnerEventType,
    LearnerInteractionBatchCreate,
    LearnerInteractionEventCreate,
    LearnerInteractionEventResponse,
    LearnerInteractionListResponse,
)
from backend.app.services.concept_mapping_service import ConceptQuestionMappingService

logger = get_logger("knovera.services.learner_interaction")


class LearnerInteractionService:
    """Service for capturing, persisting, and querying normalized learner interaction events."""

    def __init__(self, db: Session):
        self.db = db
        self.mapping_service = ConceptQuestionMappingService(db)

    def record_event(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        event_data: LearnerInteractionEventCreate,
        commit: bool = True,
    ) -> LearnerInteractionEvent:
        """Records a single learner interaction event with validation and deduplication."""
        # 1. Idempotency check: if an event with this key was already recorded by this user, return it
        if event_data.idempotency_key:
            existing = (
                self.db.query(LearnerInteractionEvent)
                .filter(
                    LearnerInteractionEvent.workspace_id == workspace_id,
                    LearnerInteractionEvent.user_id == user_id,
                    LearnerInteractionEvent.idempotency_key == event_data.idempotency_key,
                )
                .first()
            )
            if existing:
                return existing

        # 2. Validate Attempt ownership if provided
        if event_data.attempt_id:
            attempt = (
                self.db.query(QuizAttempt)
                .filter(
                    QuizAttempt.id == event_data.attempt_id,
                    QuizAttempt.workspace_id == workspace_id,
                )
                .first()
            )
            if not attempt:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Quiz attempt {event_data.attempt_id} not found in workspace.",
                )
            if attempt.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot record interactions for an attempt belonging to another user.",
                )

        # 3. Validate Question existence if provided
        if event_data.question_id:
            q_info = self.mapping_service.resolve_question(workspace_id, event_data.question_id)
            if not q_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Question {event_data.question_id} not found in workspace.",
                )

        # 4. Validate Concept existence if provided
        if event_data.concept_id:
            concept = (
                self.db.query(KnowledgeNode)
                .filter(
                    KnowledgeNode.id == event_data.concept_id,
                    KnowledgeNode.workspace_id == workspace_id,
                )
                .first()
            )
            if not concept:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Concept {event_data.concept_id} not found in workspace.",
                )

        # 5. Anti-tampering: defensively clean disallowed fields from metadata
        clean_metadata = dict(event_data.event_metadata or {})
        for disallowed_key in ("score", "score_percentage", "is_correct", "correct_count"):
            clean_metadata.pop(disallowed_key, None)

        now = datetime.now(timezone.utc)
        event = LearnerInteractionEvent(
            workspace_id=workspace_id,
            user_id=user_id,
            attempt_id=event_data.attempt_id,
            question_id=event_data.question_id,
            concept_id=event_data.concept_id,
            event_type=event_data.event_type.value,
            occurred_at=now,
            client_occurred_at=event_data.client_occurred_at,
            event_metadata=clean_metadata,
            idempotency_key=event_data.idempotency_key,
            schema_version=event_data.schema_version,
            created_at=now,
        )

        self.db.add(event)
        if commit:
            self.db.commit()
            self.db.refresh(event)

        return event

    def record_batch_events(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        batch: LearnerInteractionBatchCreate,
    ) -> List[LearnerInteractionEvent]:
        """Atomically ingests a batch of interaction events."""
        recorded_events: List[LearnerInteractionEvent] = []

        for item in batch.events:
            ev = self.record_event(
                workspace_id=workspace_id,
                user_id=user_id,
                event_data=item,
                commit=False,
            )
            recorded_events.append(ev)

        self.db.commit()
        for ev in recorded_events:
            self.db.refresh(ev)

        return recorded_events

    def list_events(
        self,
        workspace_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        attempt_id: Optional[uuid.UUID] = None,
        question_id: Optional[uuid.UUID] = None,
        concept_id: Optional[uuid.UUID] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> LearnerInteractionListResponse:
        """Retrieves paginated, filtered interaction events within a workspace."""
        query = self.db.query(LearnerInteractionEvent).filter(
            LearnerInteractionEvent.workspace_id == workspace_id
        )

        if user_id:
            query = query.filter(LearnerInteractionEvent.user_id == user_id)
        if attempt_id:
            query = query.filter(LearnerInteractionEvent.attempt_id == attempt_id)
        if question_id:
            query = query.filter(LearnerInteractionEvent.question_id == question_id)
        if concept_id:
            query = query.filter(LearnerInteractionEvent.concept_id == concept_id)
        if event_type:
            query = query.filter(LearnerInteractionEvent.event_type == event_type)

        total = query.count()
        events = (
            query.order_by(LearnerInteractionEvent.occurred_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = [
            LearnerInteractionEventResponse(
                id=e.id,
                workspace_id=e.workspace_id,
                user_id=e.user_id,
                attempt_id=e.attempt_id,
                question_id=e.question_id,
                concept_id=e.concept_id,
                event_type=e.event_type,
                occurred_at=e.occurred_at,
                client_occurred_at=e.client_occurred_at,
                event_metadata=e.event_metadata,
                idempotency_key=e.idempotency_key,
                schema_version=e.schema_version,
                created_at=e.created_at,
            )
            for e in events
        ]

        return LearnerInteractionListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_attempt_interactions(
        self,
        workspace_id: uuid.UUID,
        attempt_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> List[LearnerInteractionEventResponse]:
        """Retrieves chronological interaction history for a specific quiz attempt."""
        attempt = (
            self.db.query(QuizAttempt)
            .filter(
                QuizAttempt.id == attempt_id,
                QuizAttempt.workspace_id == workspace_id,
            )
            .first()
        )
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz attempt {attempt_id} not found in workspace.",
            )
        if attempt.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot inspect interactions for an attempt belonging to another user.",
            )

        events = (
            self.db.query(LearnerInteractionEvent)
            .filter(
                LearnerInteractionEvent.workspace_id == workspace_id,
                LearnerInteractionEvent.attempt_id == attempt_id,
            )
            .order_by(LearnerInteractionEvent.occurred_at.asc())
            .all()
        )

        return [
            LearnerInteractionEventResponse(
                id=e.id,
                workspace_id=e.workspace_id,
                user_id=e.user_id,
                attempt_id=e.attempt_id,
                question_id=e.question_id,
                concept_id=e.concept_id,
                event_type=e.event_type,
                occurred_at=e.occurred_at,
                client_occurred_at=e.client_occurred_at,
                event_metadata=e.event_metadata,
                idempotency_key=e.idempotency_key,
                schema_version=e.schema_version,
                created_at=e.created_at,
            )
            for e in events
        ]
