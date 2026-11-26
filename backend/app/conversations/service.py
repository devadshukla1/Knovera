"""Conversation Service orchestrating persistence, idempotency, and RAG execution (Phase 3 C3.9)."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import re
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.citations.repository import CitationRepository
from backend.app.citations.schemas import CitationDetail
from backend.app.conversations.exceptions import (
    ConversationAccessDeniedError,
    ConversationNotFoundError,
    GenerationAlreadyPendingError,
    InvalidMessageError,
)
from backend.app.conversations.repository import ConversationRepository
from backend.app.conversations.schemas import (
    ChatTurnResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
    MessageSubmitRequest,
)
from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.llm.manager import LLMManager
from backend.app.llm.schemas import ChatMessage, LLMGenerationRequest, MessageRole
from backend.app.ml.query_intent.predictor import QueryIntentPrediction
from backend.app.ml.query_intent.router import IntentRouter, IntentRoutingDecision
from backend.app.ml.query_intent.service import QueryIntentService
from backend.app.models.citation import Citation
from backend.app.models.conversation import Conversation
from backend.app.models.document import Document
from backend.app.models.message import Message
from backend.app.models.workspace import Workspace
from backend.app.rag.context.schemas import ContextPackage
from backend.app.rag.orchestration.answer_generator import GroundedAnswerService
from backend.app.rag.orchestration.schemas import GroundedAnswerDraft

logger = get_logger("knovera.conversations.service")


class ConversationService:
    """Orchestrates conversation lifecycle, turn idempotency, and grounded answering."""

    def __init__(
        self,
        grounded_answer_service: Optional[GroundedAnswerService] = None,
        citation_repo: Optional[CitationRepository] = None,
        conversation_repo: Optional[ConversationRepository] = None,
        intent_service: Optional[QueryIntentService] = None,
        intent_router: Optional[IntentRouter] = None,
        llm_manager: Optional[LLMManager] = None,
    ) -> None:
        self.settings = get_settings()
        self.grounded_answer_service = grounded_answer_service or GroundedAnswerService()
        self.citation_repo = citation_repo or CitationRepository()
        self.conversation_repo = conversation_repo or ConversationRepository()
        self.intent_service = intent_service or QueryIntentService.get_instance()
        self.intent_router = intent_router or IntentRouter()
        self.llm_manager = llm_manager or LLMManager.get_instance()

    def create_conversation(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        title: Optional[str] = None,
        source_scope: Optional[Dict[str, Any]] = None,
    ) -> ConversationResponse:
        """Creates a new conversation thread for the authorized workspace owner."""
        workspace = self._get_verified_workspace(db, workspace_id, user_id)

        clean_scope = source_scope or {}
        # Validate any explicitly provided document_ids
        doc_ids = clean_scope.get("document_ids")
        if doc_ids:
            self._verify_document_ids_in_workspace(db, workspace.id, doc_ids)

        clean_title = (title or "").strip() or "New Conversation"
        conv = self.conversation_repo.create_conversation(
            db=db,
            workspace_id=workspace.id,
            user_id=user_id,
            title=clean_title,
            source_scope=clean_scope,
        )
        return ConversationResponse.model_validate(conv)

    def list_conversations(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> ConversationListResponse:
        """Lists conversations belonging to the authorized workspace."""
        workspace = self._get_verified_workspace(db, workspace_id, user_id)
        items, total = self.conversation_repo.list_conversations(
            db=db,
            workspace_id=workspace.id,
            limit=limit,
            offset=offset,
        )
        has_more = (offset + len(items)) < total
        return ConversationListResponse(
            items=[ConversationResponse.model_validate(c) for c in items],
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    def rename_conversation(
        self,
        db: Session,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        new_title: str,
    ) -> ConversationResponse:
        """Renames an existing conversation thread."""
        conv = self._get_verified_conversation(db, conversation_id, user_id)
        cleaned_title = (new_title or "").strip() or "Untitled Chat"
        self.conversation_repo.update_title(db, conv.id, cleaned_title)
        db.refresh(conv)
        return ConversationResponse.model_validate(conv)

    def delete_conversation(
        self,
        db: Session,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Deletes a conversation thread and all its messages."""
        conv = self._get_verified_conversation(db, conversation_id, user_id)
        return self.conversation_repo.delete_conversation(db, conv.id)

    def get_conversation_detail(
        self,
        db: Session,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> ConversationDetailResponse:
        """Retrieves conversation thread and ordered message history with resolved citations."""
        conv = self._get_verified_conversation(db, conversation_id, user_id)
        messages = self.conversation_repo.list_messages(
            db=db,
            conversation_id=conv.id,
            limit=limit,
            offset=offset,
        )

        message_responses: List[MessageResponse] = []
        for msg in messages:
            citations: List[CitationDetail] = []
            if msg.role == "assistant" and msg.citations:
                for c in msg.citations:
                    try:
                        detail = self.citation_repo.get_citation_detail(
                            db=db,
                            citation_id=c.id,
                            user_id=user_id,
                        )
                        citations.append(detail)
                    except Exception as err:
                        logger.warning("Could not resolve historical citation %s: %s", c.id, err)

            msg_res = MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                workspace_id=msg.workspace_id,
                role=msg.role,
                content=msg.content,
                status=msg.status,
                model_provider=msg.model_provider,
                model_name=msg.model_name,
                latency_ms=msg.latency_ms,
                failure_code=msg.failure_code,
                created_at=msg.created_at,
                citations=citations,
            )
            message_responses.append(msg_res)

        return ConversationDetailResponse(
            conversation=ConversationResponse.model_validate(conv),
            messages=message_responses,
        )

    async def submit_message(
        self,
        db: Session,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        request: MessageSubmitRequest,
    ) -> ChatTurnResponse:
        """Executes full message submission turn with idempotency, generation, and citation persistence."""
        conv = self._get_verified_conversation(db, conversation_id, user_id)
        workspace_id = conv.workspace_id

        # 1. Validate query text
        query = (request.content or "").strip()
        if not query:
            raise InvalidMessageError("Message content cannot be empty or whitespace.")

        # 2. Validate optional document scope override
        effective_doc_ids: Optional[List[uuid.UUID]] = None
        if request.document_ids is not None:
            effective_doc_ids = self._verify_document_ids_in_workspace(db, workspace_id, request.document_ids)
        elif conv.source_scope and "document_ids" in conv.source_scope:
            scope_raw = conv.source_scope["document_ids"]
            if scope_raw:
                effective_doc_ids = [uuid.UUID(str(d)) for d in scope_raw]

        # 3. Idempotency Check via client_request_id
        if request.client_request_id:
            existing_user_msg = self.conversation_repo.get_user_message_by_client_request_id(
                db=db,
                conversation_id=conv.id,
                client_request_id=request.client_request_id,
            )
            if existing_user_msg:
                logger.info("Found existing message for client_request_id %s", request.client_request_id)
                assistant_reply = self.conversation_repo.get_assistant_reply_for_user_message(
                    db=db,
                    user_message_id=existing_user_msg.id,
                )
                if assistant_reply and assistant_reply.status == "complete":
                    citations = self._resolve_message_citations(db, assistant_reply, user_id)
                    retrieval_meta = assistant_reply.retrieval_metadata or {}
                    return ChatTurnResponse(
                        conversation_id=conv.id,
                        user_message=MessageResponse.model_validate(existing_user_msg),
                        assistant_message=MessageResponse(
                            id=assistant_reply.id,
                            conversation_id=assistant_reply.conversation_id,
                            workspace_id=assistant_reply.workspace_id,
                            role=assistant_reply.role,
                            content=assistant_reply.content,
                            status=assistant_reply.status,
                            model_provider=assistant_reply.model_provider,
                            model_name=assistant_reply.model_name,
                            latency_ms=assistant_reply.latency_ms,
                            failure_code=assistant_reply.failure_code,
                            created_at=assistant_reply.created_at,
                            citations=citations,
                        ),
                        citations=citations,
                        insufficient_evidence=retrieval_meta.get("insufficient_evidence", False),
                        limitations=retrieval_meta.get("limitations", []),
                    )
                elif assistant_reply and assistant_reply.status == "pending":
                    raise GenerationAlreadyPendingError("A response is already generating for this request.")

        # 4. Check for active pending generation in conversation
        pending_msg = self.conversation_repo.get_pending_assistant_message(db, conv.id)
        if pending_msg:
            # Check stale timeout (20 seconds)
            elapsed_seconds = (datetime.now(timezone.utc) - pending_msg.created_at.replace(tzinfo=timezone.utc)).total_seconds()
            if elapsed_seconds > 20:
                logger.warning("Recovering stale pending message %s in conversation %s", pending_msg.id, conv.id)
                pending_msg.status = "failed"
                pending_msg.failure_code = "stale_timeout"
                db.commit()
            else:
                raise GenerationAlreadyPendingError("Another generation is currently in progress for this conversation.")

        # 5. Persist user message and pending assistant message in database transaction
        now = datetime.now(timezone.utc)
        user_message = self.conversation_repo.create_message(
            db=db,
            workspace_id=workspace_id,
            conversation_id=conv.id,
            role="user",
            content=query,
            status="complete",
            client_request_id=request.client_request_id,
            retrieval_metadata={"requested_document_ids": [str(d) for d in effective_doc_ids]} if effective_doc_ids else {},
        )
        user_message.created_at = now

        assistant_message = self.conversation_repo.create_message(
            db=db,
            workspace_id=workspace_id,
            conversation_id=conv.id,
            role="assistant",
            content="",
            status="pending",
            in_reply_to_message_id=user_message.id,
        )
        assistant_message.created_at = now + timedelta(microseconds=1000)
        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)

        # 6. Build recent conversation history for prompt context
        recent_messages = self.conversation_repo.list_messages(db, conv.id, limit=10)
        history_for_prompt: List[ChatMessage] = []
        for m in recent_messages:
            if m.id in (user_message.id, assistant_message.id):
                continue
            if m.status == "complete" and m.content:
                role = MessageRole.USER if m.role == "user" else MessageRole.ASSISTANT
                history_for_prompt.append(ChatMessage(role=role, content=m.content))

        # 7. Predict Query Intent and Determine Routing Decision
        try:
            intent_pred = await self.intent_service.predict(query)

            # Conversational Chat Guardrails:
            # 1. Prevent false ambiguous rejections when query contains domain subject keywords
            raw_lower = query.lower().strip()
            if intent_pred.predicted_intent == "ambiguous":
                stop_tokens = {
                    "what", "is", "are", "it", "its", "this", "that", "these", "those", "tell", "me",
                    "more", "why", "how", "huh", "a", "an", "the", "can", "you", "please", "help",
                    "about", "give", "show", "i", "want", "to", "know", "one", "two", "yes", "no"
                }
                substantive_words = [w for w in re.findall(r"\b\w+\b", raw_lower) if w not in stop_tokens and len(w) > 2]
                if len(substantive_words) >= 1:
                    logger.info("Chat guard: Remapping false ambiguous intent to explanation for query '%s'", raw_lower[:50])
                    intent_pred = replace(intent_pred, predicted_intent="explanation")

            # 2. Prevent false summarization when query lacks explicit summary keywords
            if intent_pred.predicted_intent == "summarization":
                summary_cues = {"summarize", "summarise", "summary", "tldr", "tl;dr", "synopsis", "recap", "abstract", "overview of the document", "overview of the entire"}
                if not any(cue in raw_lower for cue in summary_cues):
                    logger.info("Chat guard: Remapping false summarization intent to explanation for query '%s'", raw_lower[:50])
                    intent_pred = replace(intent_pred, predicted_intent="explanation")

            routing_decision = self.intent_router.route(intent_pred)
        except Exception as err:
            logger.warning("Intent classification failed; falling back to default RAG: %s", err)
            fallback_pred = QueryIntentPrediction(
                query=query,
                sanitized_query=query,
                normalized_query=query.lower(),
                predicted_intent="factual_lookup",
                class_scores={"factual_lookup": 1.0},
                score_type="probability",
                model_id="fallback",
                model_type="fallback",
                taxonomy_version="1.0.0",
                preprocessing_version="1.0.0",
                prediction_score=1.0,
                confidence_type="unavailable",
                prediction_latency_ms=0.0,
                top_intents=[{"intent": "factual_lookup", "score": 1.0}],
            )
            routing_decision = self.intent_router.route(fallback_pred)

        # 8. Execute Selected Handler based on Intent Routing Decision
        try:
            if self._is_knovera_capability_query(query):
                draft = await self._handle_knovera_capabilities(
                    query=query, conversation_history=history_for_prompt
                )
            elif (
                routing_decision.selected_module == "general_conversation"
                and not routing_decision.requires_retrieval
            ):
                draft = await self._handle_general_conversation(
                    query=query, conversation_history=history_for_prompt
                )
            elif (
                routing_decision.selected_module == "capability_boundary"
                and routing_decision.requires_capability_response
            ):
                draft = self._handle_capability_boundary(query=query)
            elif (
                routing_decision.selected_module == "clarification"
                and routing_decision.requires_clarification
            ):
                draft = self._handle_clarification(query=query)
            else:
                draft = await self.grounded_answer_service.generate_grounded_answer(
                    db=db,
                    workspace_id=workspace_id,
                    query=query,
                    document_ids=effective_doc_ids,
                    conversation_history=history_for_prompt,
                    retrieval_profile=routing_decision.retrieval_profile,
                )

            # 9. Persist assistant completion, citations, and intent classification metadata
            assistant_message.content = draft.answer
            assistant_message.status = "complete"
            assistant_message.model_provider = draft.model_provider
            assistant_message.model_name = draft.model_name
            assistant_message.latency_ms = draft.latency_ms
            assistant_message.retrieval_metadata = {
                "metrics": getattr(draft, "retrieval_metrics", {}),
                "prompt_version": getattr(draft, "prompt_version", "1.0.0"),
                "insufficient_evidence": getattr(draft, "insufficient_evidence", False),
                "limitations": getattr(draft, "limitations", []),
                "claims": [c.model_dump() for c in getattr(draft, "claims", [])],
                "intent_classification": {
                    "predicted_intent": routing_decision.predicted_intent,
                    "confidence": routing_decision.confidence,
                    "confidence_type": routing_decision.confidence_type,
                    "selected_module": routing_decision.selected_module,
                    "retrieval_profile": routing_decision.retrieval_profile,
                    "requires_retrieval": routing_decision.requires_retrieval,
                    "fallback_applied": routing_decision.fallback_applied,
                    "fallback_reason": routing_decision.fallback_reason,
                    "routing_reason": routing_decision.routing_reason,
                    "routing_config_version": routing_decision.routing_config_version,
                },
            }

            created_citations = (
                self.citation_repo.create_citations(
                    db=db,
                    message_id=assistant_message.id,
                    drafts=draft.citation_drafts,
                )
                if draft.citation_drafts
                else []
            )

            # Auto-title conversation if this is the first turn
            if conv.title == "New Conversation":
                auto_title = query[:80].strip()
                conv.title = auto_title
                conv.updated_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(assistant_message)

            resolved_citations = [
                self.citation_repo.get_citation_detail(db, c.id, user_id)
                for c in created_citations
            ]

            return ChatTurnResponse(
                conversation_id=conv.id,
                user_message=MessageResponse.model_validate(user_message),
                assistant_message=MessageResponse(
                    id=assistant_message.id,
                    conversation_id=assistant_message.conversation_id,
                    workspace_id=assistant_message.workspace_id,
                    role=assistant_message.role,
                    content=assistant_message.content,
                    status=assistant_message.status,
                    model_provider=assistant_message.model_provider,
                    model_name=assistant_message.model_name,
                    latency_ms=assistant_message.latency_ms,
                    failure_code=assistant_message.failure_code,
                    created_at=assistant_message.created_at,
                    citations=resolved_citations,
                ),
                citations=resolved_citations,
                insufficient_evidence=draft.insufficient_evidence,
                limitations=draft.limitations,
            )

        except Exception as exc:
            logger.error("Generation failed for message %s: %s", assistant_message.id, exc, exc_info=True)
            assistant_message.status = "failed"
            assistant_message.failure_code = getattr(exc, "code", exc.__class__.__name__)
            db.commit()
            raise exc

    def _resolve_message_citations(
        self,
        db: Session,
        assistant_message: Message,
        user_id: uuid.UUID,
    ) -> List[CitationDetail]:
        """Resolves citation details for an assistant message."""
        citations: List[CitationDetail] = []
        for c in assistant_message.citations:
            try:
                detail = self.citation_repo.get_citation_detail(db, c.id, user_id)
                citations.append(detail)
            except Exception as err:
                logger.warning("Could not resolve citation %s: %s", c.id, err)
        return citations

    def _get_verified_workspace(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Workspace:
        """Verifies workspace exists. In local single-user mode, permits local workspace access."""
        ws = (
            db.query(Workspace)
            .filter(
                Workspace.id == workspace_id,
            )
            .first()
        )
        if not ws:
            raise ConversationAccessDeniedError("Workspace not found or access denied.")
        return ws

    def _get_verified_conversation(
        self,
        db: Session,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Conversation:
        """Verifies conversation exists. In local single-user mode, permits local access."""
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
            )
            .first()
        )
        if not conv:
            raise ConversationNotFoundError("Conversation not found or access denied.")

        from backend.app.core.local_user import LOCAL_USER_ID
        if user_id and user_id != LOCAL_USER_ID and conv.created_by_user_id and conv.created_by_user_id != user_id:
            raise ConversationNotFoundError("Conversation not found or access denied.")

        return conv

    def _verify_document_ids_in_workspace(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        doc_ids: List[Any],
    ) -> List[uuid.UUID]:
        """Verifies all requested document IDs belong to the active workspace and are not deleted."""
        clean_uuids: List[uuid.UUID] = []
        for d in doc_ids:
            try:
                clean_uuids.append(uuid.UUID(str(d)))
            except (ValueError, TypeError):
                raise InvalidMessageError(f"Invalid document UUID format: {d}")

        if not clean_uuids:
            return []

        active_docs = (
            db.query(Document.id)
            .filter(
                Document.id.in_(clean_uuids),
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .all()
        )
        active_set = {row[0] for row in active_docs}
        missing = set(clean_uuids) - active_set
        if missing:
            raise InvalidMessageError(f"Requested documents not found in workspace: {list(missing)}")

        return clean_uuids

    def _handle_capability_boundary(self, query: str) -> GroundedAnswerDraft:
        """Handles unsupported external operational requests gracefully."""
        empty_context = ContextPackage(
            query=query,
            sources=[],
            included_source_count=0,
            omitted_source_count=0,
            available_context_tokens=4096,
            reserved_output_tokens=1500,
            source_mapping={},
        )
        return GroundedAnswerDraft(
            answer=(
                "I am Knovera, an AI-powered Knowledge Intelligence Platform designed for analyzing and "
                "synthesizing information from your uploaded academic and research documents. "
                "The requested external operation (such as booking flights, sending emails, or executing external system transactions) "
                "is outside my supported capabilities. You can upload documents (PDF, DOCX, PPTX) to your workspace to search, "
                "analyze, or extract knowledge from them."
            ),
            claims=[],
            limitations=["Requested external operation is outside Knovera capability boundary."],
            insufficient_evidence=False,
            context_package=empty_context,
            citation_drafts=[],
            model_provider="knovera_system",
            model_name="capability_boundary_handler",
            latency_ms=1,
            prompt_version="1.0.0",
            retrieval_metrics={},
        )

    def _handle_clarification(self, query: str) -> GroundedAnswerDraft:
        """Handles ambiguous or context-deprived queries by requesting clarification."""
        empty_context = ContextPackage(
            query=query,
            sources=[],
            included_source_count=0,
            omitted_source_count=0,
            available_context_tokens=4096,
            reserved_output_tokens=1500,
            source_mapping={},
        )
        return GroundedAnswerDraft(
            answer=(
                "Your question appears ambiguous or lacks specific context for retrieval. "
                "Could you please clarify your question or specify which document, topic, or concept "
                "you would like me to examine?"
            ),
            claims=[],
            limitations=["Query contains ambiguous or context-deprived phrasing requiring user clarification."],
            insufficient_evidence=True,
            context_package=empty_context,
            citation_drafts=[],
            model_provider="knovera_system",
            model_name="clarification_handler",
            latency_ms=1,
            prompt_version="1.0.0",
            retrieval_metrics={},
        )

    @staticmethod
    def _is_knovera_capability_query(query: str) -> bool:
        """Detects questions asking about Knovera's own capabilities and features."""
        q = re.sub(r"[^\w\s]", " ", query.lower()).strip()
        patterns = [
            r"\bwhat\s+(?:can|could)\s+you\s+do\b",
            r"\bwhat\s+you\s+can\s+do\b",
            r"\bwhat\s+(?:can|does)\s+knovera\s+do\b",
            r"\bwhat\s+are\s+your\s+(?:capabilities|features|functions|skills)\b",
            r"\bhow\s+can\s+you\s+help(?:\s+me)?\b",
            r"\bwho\s+are\s+you\b",
            r"\btell\s+me\s+about\s+(?:yourself|knovera)\b",
        ]
        return any(re.search(p, q) for p in patterns)

    async def _handle_knovera_capabilities(
        self,
        query: str,
        conversation_history: Optional[List[ChatMessage]] = None,
    ) -> GroundedAnswerDraft:
        """Uses the central LLM to explain Knovera's actual implemented capabilities."""
        empty_context = ContextPackage(
            query=query,
            sources=[],
            included_source_count=0,
            omitted_source_count=0,
            available_context_tokens=4096,
            reserved_output_tokens=1500,
            source_mapping={},
        )
        system_prompt = (
            "You are Knovera, an AI-powered Knowledge Intelligence Platform.\n"
            "The user is asking what you can do. Explain Knovera's actual implemented capabilities clearly using clean Markdown:\n"
            "- **Document Library & Ingestion:** Upload and index PDF, DOCX, PPTX, and TXT files into isolated workspaces.\n"
            "- **Document-Grounded Research Chat:** Ask questions across your uploaded documents using hybrid retrieval (BM25 + dense vector search + cross-encoder reranking) with page-level citations.\n"
            "- **General-Knowledge Answering:** Answer general conceptual questions clearly, explicitly distinguishing document evidence from general knowledge.\n"
            "- **Interactive Knowledge Graph & Knovera Mind Map:** Explore hierarchical mind maps and concept relationships with learning status tracking.\n"
            "- **Study Studio:** Generate interactive Quizzes (MCQ, True/False, Fill-in-the-Blank), Flashcards, and Revision Notes grounded in your documents.\n"
            "- **Learning Analytics:** Track concept mastery over time using Bayesian Knowledge Tracing (BKT) and review recommendations.\n\n"
            "Only describe these implemented features. Do not invent external actions you cannot perform."
        )
        messages: List[ChatMessage] = [ChatMessage(role=MessageRole.SYSTEM, content=system_prompt)]
        if conversation_history:
            messages.extend(conversation_history[-4:])
        messages.append(ChatMessage(role=MessageRole.USER, content=query))

        gen_req = LLMGenerationRequest(
            model=self.llm_manager.get_active_model(),
            messages=messages,
            temperature=0.3,
            max_output_tokens=600,
            timeout_seconds=self.settings.LLM_TIMEOUT_SECONDS,
        )
        t0 = time.perf_counter()
        resp = await self.llm_manager.generate_with_retry(
            request=gen_req,
            provider=self.llm_manager.get_active_provider(),
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return GroundedAnswerDraft(
            answer=resp.content,
            claims=[],
            limitations=[],
            insufficient_evidence=False,
            context_package=empty_context,
            citation_drafts=[],
            model_provider=resp.provider,
            model_name=resp.requested_model,
            latency_ms=latency_ms,
            prompt_version="1.0.0",
            retrieval_metrics={},
        )

    async def _handle_general_conversation(
        self,
        query: str,
        conversation_history: Optional[List[ChatMessage]] = None,
    ) -> GroundedAnswerDraft:
        """Handles pleasantries and general conversation via the central LLM without hardcoded fallbacks."""
        empty_context = ContextPackage(
            query=query,
            sources=[],
            included_source_count=0,
            omitted_source_count=0,
            available_context_tokens=4096,
            reserved_output_tokens=1500,
            source_mapping={},
        )
        messages: List[ChatMessage] = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=(
                    "You are Knovera, an AI assistant for research and document intelligence. "
                    "Respond politely, helpfully, and concisely to greetings, pleasantries, or general questions. "
                    "If the question is about general knowledge rather than a greeting, provide an accurate and clear explanation, "
                    "noting that the answer is based on general knowledge."
                ),
            )
        ]
        if conversation_history:
            messages.extend(conversation_history[-4:])
        messages.append(ChatMessage(role=MessageRole.USER, content=query))

        gen_req = LLMGenerationRequest(
            model=self.llm_manager.get_active_model(),
            messages=messages,
            temperature=0.5,
            max_output_tokens=600,
            timeout_seconds=self.settings.LLM_TIMEOUT_SECONDS,
        )
        t0 = time.perf_counter()
        resp = await self.llm_manager.generate_with_retry(
            request=gen_req,
            provider=self.llm_manager.get_active_provider(),
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return GroundedAnswerDraft(
            answer=resp.content,
            claims=[],
            limitations=[],
            insufficient_evidence=False,
            context_package=empty_context,
            citation_drafts=[],
            model_provider=resp.provider,
            model_name=resp.requested_model,
            latency_ms=latency_ms,
            prompt_version="1.0.0",
            retrieval_metrics={},
        )
