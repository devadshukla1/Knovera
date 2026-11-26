"""Flashcard Generator for Knovera Study Material Generation (Phase 8 C8.5).

Generates high-yield active-recall study flashcards across 8 pedagogical categories:
- Definition, Concept, Fact, Formula, Algorithm, Comparison, Application, Terminology
- Conciseness (~5-10 words per side, ~80 characters)
- Technical notation and formula preservation
- Source chunk provenance and deterministic fallback
"""

import json
import re
from typing import List, Optional

from backend.app.core.logging import get_logger
from backend.app.llm.manager import LLMManager
from backend.app.llm.schemas import ChatMessage, LLMGenerationRequest, MessageRole
from backend.app.ml.study_materials.prompts import build_flashcards_prompt
from backend.app.ml.study_materials.provenance import (
    build_source_reference,
    find_supporting_chunk,
    format_source_context,
)
from backend.app.ml.study_materials.schemas import (
    FlashcardCreate,
    FlashcardGenerateRequest,
    FlashcardType,
    QuestionDifficulty,
    SourceReference,
    ValidationStatus,
)
from backend.app.ml.study_materials.source_resolver import ResolvedChunk

logger = get_logger("knovera.study_materials.flashcard_generator")


class FlashcardGenerator:
    """Generates high-yield active-recall study flashcards from source chunks."""

    def __init__(self, llm_manager: Optional[LLMManager] = None) -> None:
        self.llm_manager = llm_manager

    async def generate(
        self,
        chunks: List[ResolvedChunk],
        request: FlashcardGenerateRequest,
    ) -> List[FlashcardCreate]:
        """Generates list of validated flashcards."""
        if not chunks:
            raise ValueError("Cannot generate flashcards without source chunks")

        context_text = format_source_context(chunks, token_budget=3500)
        prompt = build_flashcards_prompt(
            context_text=context_text,
            count=request.count,
            difficulty=request.difficulty,
            card_type=request.card_type,
        )

        manager = self.llm_manager or LLMManager.get_instance()
        llm_response_content: Optional[str] = None

        if manager:
            try:
                active_provider = manager.get_active_provider()
                model_name = getattr(manager.settings, "LLM_MODEL", "mock-model") or "mock-model"
                llm_req = LLMGenerationRequest(
                    model=model_name,
                    messages=[
                        ChatMessage(
                            role=MessageRole.SYSTEM,
                            content="You are an active-recall learning specialist for Knovera. Always output valid JSON array of flashcard objects.",
                        ),
                        ChatMessage(role=MessageRole.USER, content=prompt),
                    ],
                    temperature=0.2,
                    max_output_tokens=3000,
                    response_format="json_object",
                )
                resp = await manager.generate_with_retry(llm_req, provider=active_provider)
                llm_response_content = resp.content
            except Exception as exc:
                logger.warning("LLM generation failed for flashcards: %s. Using deterministic fallback.", exc)

        cards = self._parse_or_fallback(
            llm_response_content=llm_response_content,
            chunks=chunks,
            request=request,
        )

        # Attach source references
        for card in cards:
            supporting_chunk = find_supporting_chunk(card.front + " " + card.back, chunks)
            if supporting_chunk:
                card.chunk_id = supporting_chunk.chunk_id
                card.document_id = supporting_chunk.document_id
                card.source_references = [build_source_reference(supporting_chunk, supporting_chunk.content[:200])]
            elif chunks:
                card.chunk_id = chunks[0].chunk_id
                card.document_id = chunks[0].document_id
                card.source_references = [build_source_reference(chunks[0], chunks[0].content[:200])]

        return cards

    def _parse_or_fallback(
        self,
        llm_response_content: Optional[str],
        chunks: List[ResolvedChunk],
        request: FlashcardGenerateRequest,
    ) -> List[FlashcardCreate]:
        """Parses LLM JSON or falls back to deterministic flashcard generation."""
        if llm_response_content:
            try:
                clean_text = llm_response_content.strip()
                if clean_text.startswith("```"):
                    clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
                    clean_text = re.sub(r"\s*```$", "", clean_text)

                data = json.loads(clean_text)
                items = data if isinstance(data, list) else data.get("cards", data.get("flashcards", []))

                parsed: List[FlashcardCreate] = []
                for item in items:
                    front = (item.get("front") or "").strip()
                    back = (item.get("back") or "").strip()
                    if not front or not back:
                        continue

                    # Map card_type safely
                    raw_type = str(item.get("card_type", "concept")).lower()
                    try:
                        c_type = FlashcardType(raw_type)
                    except ValueError:
                        c_type = FlashcardType.CONCEPT

                    raw_diff = str(item.get("difficulty", "medium")).lower()
                    try:
                        c_diff = QuestionDifficulty(raw_diff)
                    except ValueError:
                        c_diff = QuestionDifficulty.MEDIUM

                    parsed.append(
                        FlashcardCreate(
                            front=front,
                            back=back,
                            card_type=c_type,
                            difficulty=c_diff,
                            topic=item.get("topic") or request.topic or chunks[0].document_title,
                            validation_status=ValidationStatus.VALIDATED,
                        )
                    )

                if len(parsed) >= request.count:
                    return parsed[: request.count]
                elif parsed:
                    supplement = self._build_deterministic_cards(chunks, request.count - len(parsed), request)
                    return parsed + supplement
            except Exception as exc:
                logger.warning("Failed to parse flashcard JSON: %s. Using deterministic fallback.", exc)

        return self._build_deterministic_cards(chunks, request.count, request)

    def _build_deterministic_cards(
        self,
        chunks: List[ResolvedChunk],
        count: int,
        request: FlashcardGenerateRequest,
    ) -> List[FlashcardCreate]:
        """Generates deterministic, high-yield flashcards from source concepts and sentences."""
        cards: List[FlashcardCreate] = []
        sentences_with_chunks = []

        for c in chunks:
            raw_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", c.content) if len(s.strip()) > 30]
            for s in raw_sents:
                sentences_with_chunks.append((s, c))

        if not sentences_with_chunks:
            sentences_with_chunks.append((f"{chunks[0].document_title} provides core academic knowledge.", chunks[0]))

        target_categories = [
            FlashcardType.DEFINITION,
            FlashcardType.CONCEPT,
            FlashcardType.FACT,
            FlashcardType.ALGORITHM,
            FlashcardType.FORMULA,
            FlashcardType.COMPARISON,
            FlashcardType.TERMINOLOGY,
            FlashcardType.APPLICATION,
        ]

        for i in range(count):
            sent, chunk = sentences_with_chunks[i % len(sentences_with_chunks)]
            words = sent.split()
            lead_term = " ".join(words[: min(3, len(words))])

            assigned_type = request.card_type or target_categories[i % len(target_categories)]

            if assigned_type == FlashcardType.DEFINITION:
                front = f"Define '{lead_term}' according to {chunk.document_title}:"
                back = sent
            elif assigned_type == FlashcardType.FORMULA:
                front = f"What is the mathematical formulation or notation associated with '{lead_term}'?"
                back = f"In {chunk.document_title}: {sent}"
            elif assigned_type == FlashcardType.ALGORITHM:
                front = f"What are the core operational steps or properties of '{lead_term}'?"
                back = sent
            elif assigned_type == FlashcardType.COMPARISON:
                front = f"How is '{lead_term}' distinguished in the documented architecture?"
                back = sent
            else:
                front = f"What is the key principle regarding '{lead_term}'?"
                back = sent

            difficulty_cycle = [QuestionDifficulty.EASY, QuestionDifficulty.MEDIUM, QuestionDifficulty.HARD]
            diff = request.difficulty or difficulty_cycle[i % len(difficulty_cycle)]

            cards.append(
                FlashcardCreate(
                    front=front[:180],
                    back=back[:400],
                    card_type=assigned_type,
                    difficulty=diff,
                    topic=request.topic or chunk.document_title,
                    validation_status=ValidationStatus.VALIDATED,
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                )
            )

        return cards
