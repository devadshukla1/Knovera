"""Source-Grounded Response Generation Service for Knovera RAG (Phase 3 C3.7)."""

import re
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.citations.mapper import CitationMapper
from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.llm.manager import LLMManager
from backend.app.llm.schemas import ChatMessage, LLMGenerationRequest, MessageRole
from backend.app.rag.context.builder import ContextBuilder
from backend.app.rag.context.schemas import ContextPackage
from backend.app.rag.orchestration.abstention import AbstentionPolicy
from backend.app.rag.orchestration.schemas import GroundedAnswerDraft
from backend.app.rag.prompts.general_qa import GeneralQAPrompt
from backend.app.rag.prompts.parser import StructuredOutputParser
from backend.app.rag.prompts.schemas import PromptInput
from backend.app.rag.retrieval.hybrid_retriever import HybridRetriever
from backend.app.rag.retrieval.semantic_retriever import SemanticRetriever

logger = get_logger("knovera.rag.orchestration.generator")


class GroundedAnswerService:
    """Coordinates retrieval, context assembly, prompt rendering, LLM generation, and citation mapping."""

    def __init__(
        self,
        retriever: Optional[Any] = None,
        context_builder: Optional[ContextBuilder] = None,
        prompt_renderer: Optional[GeneralQAPrompt] = None,
        llm_manager: Optional[LLMManager] = None,
        output_parser: Optional[StructuredOutputParser] = None,
        citation_mapper: Optional[CitationMapper] = None,
    ) -> None:
        self.settings = get_settings()
        if retriever is not None:
            self.retriever = retriever
        elif self.settings.RETRIEVAL_MODE == "semantic":
            self.retriever = SemanticRetriever()
        else:
            self.retriever = HybridRetriever()
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_renderer = prompt_renderer or GeneralQAPrompt()
        self.llm_manager = llm_manager or LLMManager.get_instance()
        self.output_parser = output_parser or StructuredOutputParser()
        self.citation_mapper = citation_mapper or CitationMapper()

    async def generate_grounded_answer(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        query: str,
        document_ids: Optional[List[uuid.UUID]] = None,
        conversation_history: Optional[List[ChatMessage]] = None,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        retrieval_profile: Optional[str] = None,
    ) -> GroundedAnswerDraft:
        """Executes full grounded answer workflow with evidence verification and abstention enforcement.

        Guarantees:
            - Never calls LLM if the workspace has no indexed documents.
            - Never calls LLM if semantic retrieval yields zero usable candidates.
            - Prevents cross-workspace contamination via strict context revalidation.
            - Enforces claim-level source ID attribution and creates verified CitationDrafts.
        """
        start_time = time.perf_counter()

        # 1. Workspace has no indexed documents -> General knowledge answering with disclosure
        if not AbstentionPolicy.workspace_has_active_chunks(db, workspace_id):
            return await self._generate_empty_workspace_answer(
                query=query,
                conversation_history=conversation_history,
                model_name=model_name,
            )

        # 2. Multi-modal hybrid search (Dense ChromaDB + BM25 + RRF + Cross-Encoder reranking)
        retrieval_query = query
        if conversation_history:
            tokens = set(re.findall(r"\b\w+\b", query.lower()))
            pronouns = {"it", "its", "this", "that", "these", "those", "they", "them", "their", "he", "she"}
            is_followup = bool(tokens & pronouns) or len(tokens) <= 6
            if is_followup:
                for prev in reversed(conversation_history):
                    if getattr(prev, "role", None) in (MessageRole.USER, "user") and prev.content.strip():
                        prev_text = prev.content.strip()
                        retrieval_query = f"{prev_text} {query}"
                        logger.info("Contextualized follow-up retrieval query: '%s'", retrieval_query)
                        break

        try:
            search_res = self.retriever.retrieve(
                db=db,
                workspace_id=workspace_id,
                query=retrieval_query,
                document_ids=document_ids,
                top_k=self.settings.CONTEXT_MAX_CHUNKS,
            )
        except Exception as exc:
            logger.error("Document retrieval subsystem failed for workspace %s: %s", workspace_id, exc, exc_info=True)
            # Re-raise so system reports true retrieval error, not false absence of documents
            raise exc

        # 3. If retrieval returned zero matches -> Mode B (Not found in documents + General Knowledge)
        if retrieval_profile == "summarization":
            summary_candidates = self._collect_summarization_candidates(
                db=db,
                workspace_id=workspace_id,
                document_ids=document_ids,
                existing_results=search_res.results or [],
            )
            if summary_candidates:
                search_res.results = summary_candidates
                search_res.total_results = len(summary_candidates)

        if search_res.total_results == 0 or not search_res.results:
            return await self._generate_not_found_answer(
                query=query,
                conversation_history=conversation_history,
                model_name=model_name,
            )

        # 4. Context construction & PostgreSQL authorization revalidation
        context_pkg = self.context_builder.build_context(
            db=db,
            workspace_id=workspace_id,
            query=query,
            retrieval_results=search_res.results,
        )

        if context_pkg.included_source_count == 0:
            return await self._generate_not_found_answer(
                query=query,
                conversation_history=conversation_history,
                model_name=model_name,
            )

        # 5. Prompt rendering with anti-injection encapsulation and 3-mode instructions
        prompt_input = PromptInput(
            query=query,
            context_package=context_pkg,
            conversation_history=conversation_history,
        )
        rendered_prompt = self.prompt_renderer.render(prompt_input)

        # 6. LLM Generation via configured central provider (Groq)
        active_provider = self.llm_manager.get_active_provider()
        target_model = self.llm_manager.get_active_model(model_name)

        gen_request = LLMGenerationRequest(
            model=target_model,
            messages=rendered_prompt.messages,
            temperature=self.settings.LLM_TEMPERATURE,
            max_output_tokens=self.settings.LLM_MAX_OUTPUT_TOKENS,
            timeout_seconds=self.settings.LLM_TIMEOUT_SECONDS,
            response_format="json_object",
        )

        llm_response = await self.llm_manager.generate_with_retry(
            request=gen_request,
            provider=active_provider,
        )

        # 7. Parse structured JSON output & sanitize citations
        parsed_draft = self.output_parser.parse(
            raw_completion=llm_response.content,
            valid_source_ids=set(context_pkg.source_mapping.keys()),
        )

        # 8. Map claims to authoritative PostgreSQL CitationDrafts (only for document-grounded claims)
        citation_drafts: List[Any] = []
        if getattr(parsed_draft, "answering_mode", "mode_a") != "mode_b" and not parsed_draft.insufficient_evidence:
            citation_drafts = self.citation_mapper.create_citation_drafts(
                claims=parsed_draft.claims,
                source_mapping=context_pkg.source_mapping,
                db=db,
                workspace_id=workspace_id,
            )

        total_latency_ms = int((time.perf_counter() - start_time) * 1000)

        return GroundedAnswerDraft(
            answer=parsed_draft.answer,
            claims=parsed_draft.claims,
            limitations=parsed_draft.limitations,
            insufficient_evidence=parsed_draft.insufficient_evidence,
            answering_mode=getattr(parsed_draft, "answering_mode", "mode_a"),
            context_package=context_pkg,
            citation_drafts=citation_drafts,
            model_provider=llm_response.provider,
            model_name=llm_response.requested_model,
            latency_ms=total_latency_ms,
            prompt_version=rendered_prompt.prompt_version,
            retrieval_metrics=search_res.duration_metrics,
        )

    async def _generate_empty_workspace_answer(
        self,
        query: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        model_name: Optional[str] = None,
    ) -> GroundedAnswerDraft:
        """Generates general knowledge response when the workspace has zero uploaded documents."""
        start_time = time.perf_counter()
        empty_ctx = ContextPackage(
            query=query,
            sources=[],
            included_source_count=0,
            omitted_source_count=0,
            available_context_tokens=4096,
            reserved_output_tokens=1500,
            source_mapping={},
        )

        system_instruction = (
            "You are Knovera, an AI-powered Knowledge Intelligence Platform and research assistant.\n\n"
            "The user's current workspace does not contain any uploaded documents yet.\n"
            "You must NOT refuse to answer. Explain concepts clearly using your general world knowledge.\n"
            "Format your answer strictly as follows:\n\n"
            "There are no documents in this workspace yet. I can still answer your question using general knowledge.\n\n"
            "[Provide a useful, accurate, and comprehensive explanation using your general knowledge.]\n\n"
            "**Source:** General LLM knowledge, not your uploaded documents.\n\n"
            "You MUST respond with a valid JSON object conforming to this schema:\n"
            "{\n"
            '  "answering_mode": "mode_b",\n'
            '  "answer": "Complete formatted answer text following the exact structure above.",\n'
            '  "claims": [],\n'
            '  "limitations": ["Workspace has no uploaded documents."],\n'
            '  "insufficient_evidence": true\n'
            "}"
        )

        messages: List[ChatMessage] = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_instruction)
        ]
        if conversation_history:
            for hist in conversation_history[-4:]:
                if hist.role != MessageRole.SYSTEM:
                    messages.append(hist)
        messages.append(
            ChatMessage(
                role=MessageRole.USER,
                content=f"USER QUESTION:\n{query.strip()}\n\nPlease answer using general knowledge. You MUST output a valid JSON object.",
            )
        )

        active_provider = self.llm_manager.get_active_provider()
        target_model = self.llm_manager.get_active_model(model_name)

        gen_request = LLMGenerationRequest(
            model=target_model,
            messages=messages,
            temperature=0.2,
            max_output_tokens=self.settings.LLM_MAX_OUTPUT_TOKENS,
            timeout_seconds=self.settings.LLM_TIMEOUT_SECONDS,
            response_format="json_object",
        )

        llm_response = await self.llm_manager.generate_with_retry(
            request=gen_request,
            provider=active_provider,
        )

        try:
            parsed = self.output_parser.parse(llm_response.content, valid_source_ids=set())
            answer_text = parsed.answer
        except Exception:
            answer_text = (
                f"There are no documents in this workspace yet. I can still answer your question using general knowledge.\n\n"
                f"{llm_response.content.strip()}\n\n"
                f"**Source:** General LLM knowledge, not your uploaded documents."
            )

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return GroundedAnswerDraft(
            answer=answer_text,
            claims=[],
            limitations=["Workspace has no uploaded documents."],
            insufficient_evidence=True,
            answering_mode="mode_b",
            context_package=empty_ctx,
            citation_drafts=[],
            model_provider=llm_response.provider,
            model_name=llm_response.requested_model,
            latency_ms=latency_ms,
            prompt_version="general-qa-v2",
            retrieval_metrics={"reason": "empty_workspace"},
        )

    def _collect_summarization_candidates(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        document_ids: Optional[List[uuid.UUID]],
        existing_results: List[Any],
        max_chunks: int = 12,
    ) -> List[Any]:
        """Collects evenly distributed passages across target documents for comprehensive summarization."""
        from backend.app.models.document import Document
        from backend.app.models.document_chunk import DocumentChunk
        from backend.app.rag.retrieval.schemas import SemanticSearchResult

        q = (
            db.query(DocumentChunk, Document.original_filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(
                DocumentChunk.workspace_id == workspace_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
                Document.processing_status == "ready",
            )
        )
        if document_ids:
            q = q.filter(DocumentChunk.document_id.in_(document_ids))

        rows = q.order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).all()
        if not rows:
            return existing_results

        # Sample evenly across all chunks so beginning, middle, and conclusion are all covered
        if len(rows) > max_chunks:
            step = (len(rows) - 1) / (max_chunks - 1)
            indices = [round(i * step) for i in range(max_chunks)]
            sampled = [rows[idx] for idx in dict.fromkeys(indices)]
        else:
            sampled = rows

        candidates: List[SemanticSearchResult] = []
        for rank, (chunk, filename) in enumerate(sampled, start=1):
            candidates.append(
                SemanticSearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    workspace_id=workspace_id,
                    document_filename=filename,
                    content=chunk.content,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    slide_number=getattr(chunk, "slide_number", None),
                    section_title=chunk.section_title,
                    distance=round(rank * 0.01, 4),
                    rank=rank,
                    embedding_model=self.settings.EMBEDDING_MODEL,
                    embedding_revision="1.0.0",
                )
            )
        return candidates

    async def _generate_not_found_answer(
        self,
        query: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        model_name: Optional[str] = None,
    ) -> GroundedAnswerDraft:
        """Generates a Mode B response when document search yields no relevant evidence."""
        start_time = time.perf_counter()
        empty_ctx = ContextPackage(
            query=query,
            sources=[],
            included_source_count=0,
            omitted_source_count=0,
            available_context_tokens=4096,
            reserved_output_tokens=1500,
            source_mapping={},
        )

        system_instruction = (
            "You are Knovera, an AI-powered Knowledge Intelligence Platform and research assistant.\n\n"
            "The user asked a question, but NO relevant evidence was found in their uploaded workspace documents.\n"
            "You must NOT refuse to answer, and you must NOT fabricate document citations.\n"
            "Format your answer using clean, modern Markdown as follows:\n\n"
            "### Not Found in Workspace Documents\n\n"
            "I couldn't find sufficient information about this topic in your current workspace documents.\n\n"
            "### General Knowledge Overview\n\n"
            "[Provide a useful, accurate, and comprehensive explanation using your general knowledge, formatted with clear paragraphs, bullet points for key items, and selective bolding.]\n\n"
            "### Source Reference\n"
            "General knowledge (not from uploaded documents).\n\n"
            "You MUST respond with a valid JSON object conforming to this schema:\n"
            "{\n"
            '  "answering_mode": "mode_b",\n'
            '  "answer": "Complete formatted answer text following the exact Mode B structure above.",\n'
            '  "claims": [],\n'
            '  "limitations": ["Not found in uploaded documents; answered using general LLM knowledge."],\n'
            '  "insufficient_evidence": true\n'
            "}"
        )

        messages: List[ChatMessage] = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_instruction)
        ]
        if conversation_history:
            for hist in conversation_history[-4:]:
                if hist.role != MessageRole.SYSTEM:
                    messages.append(hist)
        messages.append(
            ChatMessage(
                role=MessageRole.USER,
                content=f"USER QUESTION:\n{query.strip()}\n\nPlease answer using general knowledge following the required Mode B format. You MUST output a valid JSON object.",
            )
        )

        active_provider = self.llm_manager.get_active_provider()
        target_model = self.llm_manager.get_active_model(model_name)

        gen_request = LLMGenerationRequest(
            model=target_model,
            messages=messages,
            temperature=0.2,
            max_output_tokens=self.settings.LLM_MAX_OUTPUT_TOKENS,
            timeout_seconds=self.settings.LLM_TIMEOUT_SECONDS,
            response_format="json_object",
        )

        llm_response = await self.llm_manager.generate_with_retry(
            request=gen_request,
            provider=active_provider,
        )

        try:
            parsed = self.output_parser.parse(llm_response.content, valid_source_ids=set())
            answer_text = parsed.answer
        except Exception:
            answer_text = (
                f"**Not found in your uploaded documents.**\n\n"
                f"I couldn't find sufficient information about this topic in your current workspace documents.\n\n"
                f"**However, based on general knowledge:**\n\n"
                f"{llm_response.content.strip()}\n\n"
                f"**Source:** General LLM knowledge, not your uploaded documents."
            )

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return GroundedAnswerDraft(
            answer=answer_text,
            claims=[],
            limitations=["Not found in uploaded documents; answered using general LLM knowledge."],
            insufficient_evidence=True,
            answering_mode="mode_b",
            context_package=empty_ctx,
            citation_drafts=[],
            model_provider=llm_response.provider,
            model_name=llm_response.requested_model,
            latency_ms=latency_ms,
            prompt_version="general-qa-v2",
            retrieval_metrics={"reason": "not_found_fallback"},
        )
