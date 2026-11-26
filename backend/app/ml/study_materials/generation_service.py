"""Study Material Generation Service (Phase 8 Orchestrator).

Coordinates:
- Source scope chunk resolution & tenancy boundaries
- Model generation execution via LLMManager (Notes, MCQs, Fill-in-Blanks, True/False, Flashcards)
- Quality validation & psychometric filtering
- Transactional persistence in PostgreSQL
- Telemetry, quality reporting, and answer-key separation
- Interactive quiz session lifecycle and authoritative grading
"""

from datetime import datetime, timezone
import random
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.llm.manager import LLMManager
from backend.app.ml.study_materials.evaluation_service import QuizEvaluationService
from backend.app.ml.study_materials.evidence_service import StudyMaterialEvidenceService
from backend.app.ml.study_materials.fill_blank_generator import FillBlankGenerator
from backend.app.ml.study_materials.flashcard_generator import FlashcardGenerator
from backend.app.ml.study_materials.mcq_generator import MCQGenerator
from backend.app.ml.study_materials.quality_checks import StudyMaterialQualityValidator
from backend.app.ml.study_materials.revision_notes import RevisionNoteGenerator
from backend.app.ml.study_materials.schemas import (
    FillBlankExerciseCreate,
    FillBlankGenerateRequest,
    FillBlankPracticeResponse,
    FillBlankReviewResponse,
    FlashcardCreate,
    FlashcardGenerateRequest,
    FlashcardResponse,
    GenerationStatus,
    MCQGenerateRequest,
    MCQOptionPracticeResponse,
    MCQOptionReviewResponse,
    MCQPracticeResponse,
    MCQQuestionCreate,
    MCQReviewResponse,
    MaterialType,
    QuestionDifficulty,
    QuestionExplanationResponse,
    QuestionSourcesResponse,
    QuizAttemptAnswerSaveRequest,
    QuizAttemptAnswerSubmit,
    QuizAttemptCreateRequest,
    QuizAttemptResponse,
    QuizAttemptResultDetail,
    QuizAttemptResultResponse,
    QuizAttemptStatus,
    QuizAttemptSummaryResponse,
    QuizHistoryListResponse,
    QuizHistorySummaryResponse,
    QuizHistoryTrendPoint,
    QuizHistoryTrendsResponse,
    QuizQuestionPracticeItem,
    RevisionNoteCreate,
    RevisionNoteResponse,
    RevisionNotesGenerateRequest,
    SourceReference,
    SourceScope,
    SourceScopeType,
    StudyMaterialGenerationRunResponse,
    TrueFalseGenerateRequest,
    TrueFalsePracticeResponse,
    TrueFalseQuestionCreate,
    TrueFalseReviewResponse,
    ValidationStatus,
    ViewMode,
)
from backend.app.ml.study_materials.source_resolver import SourceResolver
from backend.app.ml.study_materials.true_false_generator import TrueFalseGenerator
from backend.app.models.study_material import (
    FillBlankExercise,
    Flashcard,
    MCQQuestion,
    QuizAttempt,
    QuizAttemptAnswer,
    RevisionNote,
    StudyMaterialGeneration,
    TrueFalseQuestion,
)
from backend.app.repositories.study_material_repository import StudyMaterialRepository

logger = get_logger("knovera.study_materials.generation_service")


class StudyMaterialGenerationService:
    """Core service for orchestrating study material generation pipelines and quiz attempts."""

    def __init__(
        self,
        session: Session,
        llm_manager: Optional[LLMManager] = None,
    ) -> None:
        self.session = session
        self.llm_manager = llm_manager
        self.repository = StudyMaterialRepository(session)
        self.resolver = SourceResolver(session)
        self.evaluator = QuizEvaluationService(session)
        self.evidence_service = StudyMaterialEvidenceService(session)

    # =========================================================================
    # C8.1: Revision Notes Generation
    # =========================================================================

    async def generate_revision_notes(
        self,
        workspace_id: UUID,
        request: RevisionNotesGenerateRequest,
    ) -> Tuple[RevisionNoteResponse, StudyMaterialGenerationRunResponse]:
        """Resolves source chunks, runs RevisionNoteGenerator, validates, and persists."""
        start_time = time.perf_counter()
        manager = self.llm_manager or LLMManager.get_instance()
        provider_name = manager.get_active_provider_name() if manager else "mock"
        model_name = getattr(manager.settings, "LLM_MODEL", "mock-model") if manager else "mock-model"

        # 1. Resolve source chunks
        chunks = self.resolver.resolve(workspace_id=workspace_id, scope=request.scope)
        if not chunks:
            raise ValueError(f"No source documents found for scope '{request.scope.scope_type.value}' in workspace")

        # 2. Record run initialization
        run = self.repository.create_generation_run(
            workspace_id=workspace_id,
            material_type=MaterialType.REVISION_NOTES.value,
            requested_count=1,
            provider_name=provider_name,
            model_name=model_name,
            scope_type=request.scope.scope_type.value,
            scope_config=request.scope.model_dump(mode="json"),
        )

        try:
            generator = RevisionNoteGenerator(llm_manager=manager)
            raw_note = await generator.generate(chunks=chunks, request=request)

            # 3. Quality Validation
            valid_notes, report = StudyMaterialQualityValidator.validate_revision_notes_batch(
                notes=[raw_note],
                chunks=chunks,
            )

            if not valid_notes:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                reasons = "; ".join(report.rejection_reasons)
                self.repository.complete_generation_run(
                    generation_id=run.id,
                    status=GenerationStatus.FAILED.value,
                    generated_count=1,
                    validated_count=0,
                    rejected_count=1,
                    duration_ms=duration_ms,
                    quality_report=report.model_dump(),
                    error_message=f"Quality validation failed: {reasons}",
                )
                raise ValueError(f"Generated note failed quality checks: {reasons}")

            # 4. Persistence
            saved_orm = self.repository.save_revision_note(
                workspace_id=workspace_id,
                generation_id=run.id,
                note_data=valid_notes[0],
            )

            # 5. Mark run completed
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            completed_run = self.repository.complete_generation_run(
                generation_id=run.id,
                status=GenerationStatus.COMPLETED.value,
                generated_count=1,
                validated_count=1,
                rejected_count=0,
                duration_ms=duration_ms,
                quality_report=report.model_dump(),
            )

            response = RevisionNoteResponse(
                id=saved_orm.id,
                workspace_id=saved_orm.workspace_id,
                generation_id=saved_orm.generation_id,
                title=saved_orm.title,
                overview=saved_orm.overview,
                length=saved_orm.length,
                detail_level=saved_orm.detail_level,
                focus=saved_orm.focus,
                sections=saved_orm.sections,
                key_concepts=saved_orm.key_concepts,
                important_points=saved_orm.important_points,
                formulas=saved_orm.formulas,
                quick_summary=saved_orm.quick_summary,
                source_references=saved_orm.source_references,
                created_at=saved_orm.created_at,
                updated_at=saved_orm.updated_at,
            )
            run_response = StudyMaterialGenerationRunResponse.model_validate(completed_run or run)
            return response, run_response

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self.repository.complete_generation_run(
                generation_id=run.id,
                status=GenerationStatus.FAILED.value,
                generated_count=0,
                validated_count=0,
                rejected_count=1,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    # =========================================================================
    # C8.2: MCQ Generation
    # =========================================================================

    async def generate_mcqs(
        self,
        workspace_id: UUID,
        request: MCQGenerateRequest,
    ) -> Tuple[List[MCQReviewResponse], StudyMaterialGenerationRunResponse]:
        """Resolves source chunks, runs MCQGenerator, validates psychometrics, and persists."""
        start_time = time.perf_counter()
        manager = self.llm_manager or LLMManager.get_instance()
        provider_name = manager.get_active_provider_name() if manager else "mock"
        model_name = getattr(manager.settings, "LLM_MODEL", "mock-model") if manager else "mock-model"

        chunks = self.resolver.resolve(workspace_id=workspace_id, scope=request.scope)
        if not chunks:
            raise ValueError(f"No source documents found for scope '{request.scope.scope_type.value}' in workspace")

        run = self.repository.create_generation_run(
            workspace_id=workspace_id,
            material_type=MaterialType.MCQ.value,
            requested_count=request.count,
            provider_name=provider_name,
            model_name=model_name,
            scope_type=request.scope.scope_type.value,
            scope_config=request.scope.model_dump(mode="json"),
        )

        try:
            generator = MCQGenerator(llm_manager=manager)
            raw_mcqs = await generator.generate(chunks=chunks, request=request)

            # 3. Quality Validation
            valid_mcqs, report = StudyMaterialQualityValidator.validate_mcq_batch(
                questions=raw_mcqs,
                total_requested=request.count,
            )

            # 4. Persistence
            saved_orms = self.repository.save_mcq_questions(
                workspace_id=workspace_id,
                generation_id=run.id,
                questions=valid_mcqs,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            status = (
                GenerationStatus.COMPLETED.value
                if len(valid_mcqs) >= request.count
                else (
                    GenerationStatus.COMPLETED_WITH_WARNINGS.value
                    if valid_mcqs
                    else GenerationStatus.FAILED.value
                )
            )

            completed_run = self.repository.complete_generation_run(
                generation_id=run.id,
                status=status,
                generated_count=len(raw_mcqs),
                validated_count=len(valid_mcqs),
                rejected_count=len(raw_mcqs) - len(valid_mcqs),
                duration_ms=duration_ms,
                quality_report=report.model_dump(),
            )

            responses = [self.format_mcq_review(q) for q in saved_orms]
            run_response = StudyMaterialGenerationRunResponse.model_validate(completed_run or run)
            return responses, run_response

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self.repository.complete_generation_run(
                generation_id=run.id,
                status=GenerationStatus.FAILED.value,
                generated_count=0,
                validated_count=0,
                rejected_count=request.count,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    # =========================================================================
    # C8.3: Fill-in-the-Blanks Generation
    # =========================================================================

    async def generate_fill_blanks(
        self,
        workspace_id: UUID,
        request: FillBlankGenerateRequest,
    ) -> Tuple[List[FillBlankReviewResponse], StudyMaterialGenerationRunResponse]:
        """Resolves source chunks, runs FillBlankGenerator, validates, and persists items."""
        start_time = time.perf_counter()
        manager = self.llm_manager or LLMManager.get_instance()
        provider_name = manager.get_active_provider_name() if manager else "mock"
        model_name = getattr(manager.settings, "LLM_MODEL", "mock-model") if manager else "mock-model"

        chunks = self.resolver.resolve(workspace_id=workspace_id, scope=request.scope)
        if not chunks:
            raise ValueError(f"No source documents found for scope '{request.scope.scope_type.value}' in workspace")

        run = self.repository.create_generation_run(
            workspace_id=workspace_id,
            material_type=MaterialType.FILL_BLANKS.value,
            requested_count=request.count,
            provider_name=provider_name,
            model_name=model_name,
            scope_type=request.scope.scope_type.value,
            scope_config=request.scope.model_dump(mode="json"),
        )

        try:
            generator = FillBlankGenerator(llm_manager=manager)
            raw_items = await generator.generate(chunks=chunks, request=request)

            # 3. Quality Validation
            valid_items, report = StudyMaterialQualityValidator.validate_fill_blanks_batch(
                items=raw_items,
                total_requested=request.count,
            )

            # 4. Persistence
            saved_orms = self.repository.save_fill_blank_exercises(
                workspace_id=workspace_id,
                generation_id=run.id,
                exercises=valid_items,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            status = (
                GenerationStatus.COMPLETED.value
                if len(valid_items) >= request.count
                else (
                    GenerationStatus.COMPLETED_WITH_WARNINGS.value
                    if valid_items
                    else GenerationStatus.FAILED.value
                )
            )

            completed_run = self.repository.complete_generation_run(
                generation_id=run.id,
                status=status,
                generated_count=len(raw_items),
                validated_count=len(valid_items),
                rejected_count=len(raw_items) - len(valid_items),
                duration_ms=duration_ms,
                quality_report=report.model_dump(),
            )

            responses = [self.format_fill_blank_review(item) for item in saved_orms]
            run_response = StudyMaterialGenerationRunResponse.model_validate(completed_run or run)
            return responses, run_response

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self.repository.complete_generation_run(
                generation_id=run.id,
                status=GenerationStatus.FAILED.value,
                generated_count=0,
                validated_count=0,
                rejected_count=request.count,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    # =========================================================================
    # C8.4: True/False Generation
    # =========================================================================

    async def generate_true_false(
        self,
        workspace_id: UUID,
        request: TrueFalseGenerateRequest,
    ) -> Tuple[List[TrueFalseQuestion], StudyMaterialGenerationRunResponse]:
        """Resolves source chunks, runs TrueFalseGenerator, validates balance & grounding, persists."""
        start_time = time.perf_counter()
        manager = self.llm_manager or LLMManager.get_instance()
        provider_name = manager.get_active_provider_name() if manager else "mock"
        model_name = getattr(manager.settings, "LLM_MODEL", "mock-model") if manager else "mock-model"

        chunks = self.resolver.resolve(workspace_id=workspace_id, scope=request.scope)
        if not chunks:
            raise ValueError(f"No source documents found for scope '{request.scope.scope_type.value}' in workspace")

        run = self.repository.create_generation_run(
            workspace_id=workspace_id,
            material_type=MaterialType.TRUE_FALSE.value,
            requested_count=request.count,
            provider_name=provider_name,
            model_name=model_name,
            scope_type=request.scope.scope_type.value,
            scope_config=request.scope.model_dump(mode="json"),
        )

        try:
            generator = TrueFalseGenerator(llm_manager=manager)
            raw_questions = await generator.generate(chunks=chunks, request=request)

            # 3. Quality Validation
            valid_questions, report = StudyMaterialQualityValidator.validate_true_false_batch(
                questions=raw_questions,
                total_requested=request.count,
            )

            # 4. Persistence
            saved_orms = self.repository.save_true_false_questions(
                workspace_id=workspace_id,
                generation_id=run.id,
                questions=valid_questions,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            status = (
                GenerationStatus.COMPLETED.value
                if len(valid_questions) >= request.count
                else (
                    GenerationStatus.COMPLETED_WITH_WARNINGS.value
                    if valid_questions
                    else GenerationStatus.FAILED.value
                )
            )

            completed_run = self.repository.complete_generation_run(
                generation_id=run.id,
                status=status,
                generated_count=len(raw_questions),
                validated_count=len(valid_questions),
                rejected_count=len(raw_questions) - len(valid_questions),
                duration_ms=duration_ms,
                quality_report=report.model_dump(),
            )

            run_response = StudyMaterialGenerationRunResponse.model_validate(completed_run or run)
            return saved_orms, run_response

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self.repository.complete_generation_run(
                generation_id=run.id,
                status=GenerationStatus.FAILED.value,
                generated_count=0,
                validated_count=0,
                rejected_count=request.count,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    # =========================================================================
    # C8.5: Flashcard Generation
    # =========================================================================

    async def generate_flashcards(
        self,
        workspace_id: UUID,
        request: FlashcardGenerateRequest,
    ) -> Tuple[List[Flashcard], StudyMaterialGenerationRunResponse]:
        """Resolves source chunks, runs FlashcardGenerator, validates bounds, and persists cards."""
        start_time = time.perf_counter()
        manager = self.llm_manager or LLMManager.get_instance()
        provider_name = manager.get_active_provider_name() if manager else "mock"
        model_name = getattr(manager.settings, "LLM_MODEL", "mock-model") if manager else "mock-model"

        chunks = self.resolver.resolve(workspace_id=workspace_id, scope=request.scope)
        if not chunks:
            raise ValueError(f"No source documents found for scope '{request.scope.scope_type.value}' in workspace")

        run = self.repository.create_generation_run(
            workspace_id=workspace_id,
            material_type=MaterialType.FLASHCARDS.value,
            requested_count=request.count,
            provider_name=provider_name,
            model_name=model_name,
            scope_type=request.scope.scope_type.value,
            scope_config=request.scope.model_dump(mode="json"),
        )

        try:
            generator = FlashcardGenerator(llm_manager=manager)
            raw_cards = await generator.generate(chunks=chunks, request=request)

            # 3. Quality Validation
            valid_cards, report = StudyMaterialQualityValidator.validate_flashcards_batch(
                cards=raw_cards,
                total_requested=request.count,
            )

            # 4. Persistence
            saved_orms = self.repository.save_flashcards(
                workspace_id=workspace_id,
                generation_id=run.id,
                cards=valid_cards,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            status = (
                GenerationStatus.COMPLETED.value
                if len(valid_cards) >= request.count
                else (
                    GenerationStatus.COMPLETED_WITH_WARNINGS.value
                    if valid_cards
                    else GenerationStatus.FAILED.value
                )
            )

            completed_run = self.repository.complete_generation_run(
                generation_id=run.id,
                status=status,
                generated_count=len(raw_cards),
                validated_count=len(valid_cards),
                rejected_count=len(raw_cards) - len(valid_cards),
                duration_ms=duration_ms,
                quality_report=report.model_dump(),
            )

            run_response = StudyMaterialGenerationRunResponse.model_validate(completed_run or run)
            return saved_orms, run_response

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self.repository.complete_generation_run(
                generation_id=run.id,
                status=GenerationStatus.FAILED.value,
                generated_count=0,
                validated_count=0,
                rejected_count=request.count,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    def _ensure_question_concept_mappings(
        self,
        workspace_id: UUID,
        sampled_questions: List[Dict[str, Any]],
    ) -> None:
        """Ensures that all questions in the quiz have validated mappings to canonical KnowledgeNode concepts."""
        import re
        from backend.app.models.knowledge_node import KnowledgeNode
        from backend.app.models.learner_intelligence import QuestionConceptMapping

        try:
            existing_nodes = (
                self.session.query(KnowledgeNode)
                .filter(KnowledgeNode.workspace_id == workspace_id)
                .all()
            )
            node_map = {n.normalized_name: n for n in existing_nodes}

            for item in sampled_questions:
                q = item.get("question")
                qid = item.get("id") or getattr(q, "id", None)
                qtype = item.get("type", "mcq")
                if not qid:
                    continue

                concept_name: Optional[str] = None
                if q:
                    topic_tags = getattr(q, "topic_tags", None)
                    if topic_tags and len(topic_tags) > 0 and topic_tags[0]:
                        concept_name = topic_tags[0].strip()
                    elif getattr(q, "topic", None):
                        concept_name = getattr(q, "topic", "").strip()

                if not concept_name:
                    concept_name = "Core Subject Concepts"

                concept_name = re.sub(r"^[•\-\*#\d\.\s]+", "", concept_name).strip()
                if not concept_name or len(concept_name) < 2:
                    concept_name = "Core Optimization Principles"
                concept_name = concept_name[:100]
                norm_name = concept_name.lower()

                node = node_map.get(norm_name)
                if not node:
                    node = KnowledgeNode(
                        workspace_id=workspace_id,
                        node_type="concept",
                        category="concept",
                        name=concept_name,
                        normalized_name=norm_name,
                        description=f"Canonical concept for {concept_name}",
                        aliases=[],
                    )
                    self.session.add(node)
                    self.session.flush()
                    node_map[norm_name] = node

                existing_mapping = (
                    self.session.query(QuestionConceptMapping)
                    .filter(
                        QuestionConceptMapping.workspace_id == workspace_id,
                        QuestionConceptMapping.question_id == qid,
                        QuestionConceptMapping.concept_id == node.id,
                    )
                    .first()
                )
                if not existing_mapping:
                    q_text = getattr(q, "question_text", None) or getattr(q, "statement", None) or getattr(q, "sentence_with_blank", None) or ""
                    mapping = QuestionConceptMapping(
                        workspace_id=workspace_id,
                        question_id=qid,
                        question_type=qtype,
                        concept_id=node.id,
                        mapping_method="deterministic_extraction",
                        confidence_score=1.0,
                        validation_status="validated",
                        evidence_excerpt=q_text[:300] if q_text else None,
                    )
                    self.session.add(mapping)

            self.session.commit()
        except Exception as exc:
            logger.warning("Failed to auto-map question concepts: %s", exc)
            self.session.rollback()

    # =========================================================================
    # C8.6: Interactive Quiz Attempt Orchestration
    # =========================================================================

    async def create_quiz_attempt(
        self,
        workspace_id: UUID,
        user_id: UUID,
        request: QuizAttemptCreateRequest,
    ) -> QuizAttemptResponse:
        """Initializes an interactive quiz attempt with anti-cheat shielded practice questions."""
        sampled_questions: List[Dict[str, Any]] = []

        if request.question_ids:
            grouped = self.repository.get_questions_by_ids(
                workspace_id=workspace_id,
                question_ids=request.question_ids,
            )
            for q in grouped["mcqs"]:
                sampled_questions.append({"id": q.id, "type": "mcq", "question": q})
            for q in grouped["true_false"]:
                sampled_questions.append({"id": q.id, "type": "true_false", "question": q})
            for q in grouped["fill_blanks"]:
                sampled_questions.append({"id": q.id, "type": "fill_blank", "question": q})
        else:
            sampled_questions = self.repository.sample_quiz_questions(
                workspace_id=workspace_id,
                question_types=request.question_types,
                count=request.count,
                difficulty=request.difficulty.value if request.difficulty else None,
                generation_ids=request.generation_ids,
            )

        if not sampled_questions or len(sampled_questions) < request.count:
            # Check if workspace has uploaded documents to dynamically generate from
            chunks = self.resolver.resolve(workspace_id=workspace_id, scope=SourceScope(scope_type=SourceScopeType.WORKSPACE))
            if not chunks:
                if not sampled_questions:
                    raise ValueError("No eligible study material questions found in this workspace, and no documents are uploaded to generate new questions. Please upload a document first.")
            else:
                needed = request.count - len(sampled_questions)
                logger.info("Dynamically generating %d questions for interactive quiz in workspace %s", needed, workspace_id)
                target_types = request.question_types or ["mcq", "true_false", "fill_blank"]
                n_types = len(target_types)
                count_per_type = max(1, (needed + n_types - 1) // n_types)

                if "mcq" in target_types:
                    try:
                        await self.generate_mcqs(
                            workspace_id=workspace_id,
                            request=MCQGenerateRequest(
                                scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
                                count=count_per_type,
                                difficulty=request.difficulty,
                            ),
                        )
                    except Exception as exc:
                        logger.warning("Dynamic MCQ generation during quiz startup encountered error: %s", exc)

                if "true_false" in target_types:
                    try:
                        await self.generate_true_false(
                            workspace_id=workspace_id,
                            request=TrueFalseGenerateRequest(
                                scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
                                count=count_per_type,
                                difficulty=request.difficulty,
                            ),
                        )
                    except Exception as exc:
                        logger.warning("Dynamic True/False generation during quiz startup encountered error: %s", exc)

                if "fill_blank" in target_types:
                    try:
                        await self.generate_fill_blanks(
                            workspace_id=workspace_id,
                            request=FillBlankGenerateRequest(
                                scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
                                count=count_per_type,
                                difficulty=request.difficulty,
                            ),
                        )
                    except Exception as exc:
                        logger.warning("Dynamic Fill-in-Blank generation during quiz startup encountered error: %s", exc)

                # Re-sample from all available questions
                sampled_questions = self.repository.sample_quiz_questions(
                    workspace_id=workspace_id,
                    question_types=request.question_types,
                    count=request.count,
                    difficulty=request.difficulty.value if request.difficulty else None,
                    generation_ids=request.generation_ids,
                )

        if not sampled_questions:
            raise ValueError("No eligible study material questions found matching the requested criteria in this workspace")

        # Automatically map questions to canonical concepts for BKT & learning intelligence
        self._ensure_question_concept_mappings(workspace_id=workspace_id, sampled_questions=sampled_questions)

        questions_order = [
            {"id": str(item["id"]), "type": item["type"]}
            for item in sampled_questions
        ]

        title = request.title or f"Interactive Quiz — {datetime.now(timezone.utc).strftime('%b %d, %H:%M')}"
        attempt = self.repository.create_quiz_attempt(
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            questions_order=questions_order,
            total_questions=len(questions_order),
        )

        practice_items = self._format_practice_questions(sampled_questions)
        return QuizAttemptResponse(
            id=attempt.id,
            workspace_id=attempt.workspace_id,
            user_id=attempt.user_id,
            title=attempt.title,
            status=QuizAttemptStatus(attempt.status),
            total_questions=attempt.total_questions,
            answered_count=0,
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            questions=practice_items,
            saved_answers={},
        )

    def get_quiz_attempt(
        self,
        workspace_id: UUID,
        attempt_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> QuizAttemptResponse:
        """Loads active attempt with anti-cheat shielded practice questions and saved answers."""
        attempt = self.repository.get_quiz_attempt(
            attempt_id=attempt_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not attempt:
            raise ValueError("Quiz attempt not found")

        q_ids = [UUID(item["id"]) for item in attempt.questions_order]
        grouped = self.repository.get_questions_by_ids(
            workspace_id=workspace_id,
            question_ids=q_ids,
        )

        lookup: Dict[str, Any] = {}
        for q in grouped["mcqs"]:
            lookup[f"mcq_{str(q.id)}"] = q
        for q in grouped["true_false"]:
            lookup[f"true_false_{str(q.id)}"] = q
        for q in grouped["fill_blanks"]:
            lookup[f"fill_blank_{str(q.id)}"] = q

        ordered_items: List[Dict[str, Any]] = []
        for item in attempt.questions_order:
            key = f"{item['type']}_{item['id']}"
            if key in lookup:
                ordered_items.append({
                    "id": UUID(item["id"]),
                    "type": item["type"],
                    "question": lookup[key],
                })

        practice_items = self._format_practice_questions(ordered_items)
        saved_answers: Dict[str, Any] = {
            str(a.question_id): a.selected_answer for a in attempt.answers
        }

        return QuizAttemptResponse(
            id=attempt.id,
            workspace_id=attempt.workspace_id,
            user_id=attempt.user_id,
            title=attempt.title,
            status=QuizAttemptStatus(attempt.status),
            total_questions=attempt.total_questions,
            answered_count=len(saved_answers),
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            questions=practice_items,
            saved_answers=saved_answers,
        )

    def save_quiz_attempt_answers(
        self,
        workspace_id: UUID,
        attempt_id: UUID,
        answers: List[QuizAttemptAnswerSubmit],
        user_id: Optional[UUID] = None,
    ) -> QuizAttemptResponse:
        """Saves or updates learner answers in an active quiz attempt without evaluating."""
        attempt = self.repository.get_quiz_attempt(
            attempt_id=attempt_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not attempt:
            raise ValueError("Quiz attempt not found")
        if attempt.status == "evaluated":
            raise ValueError("Cannot modify answers for an already evaluated quiz attempt")

        self.repository.save_quiz_attempt_answers(
            attempt_id=attempt_id,
            answers=answers,
        )
        return self.get_quiz_attempt(workspace_id=workspace_id, attempt_id=attempt_id, user_id=user_id)

    def submit_quiz_attempt(
        self,
        workspace_id: UUID,
        attempt_id: UUID,
        answers: Optional[List[QuizAttemptAnswerSubmit]] = None,
        user_id: Optional[UUID] = None,
    ) -> QuizAttemptResultResponse:
        """Authoritatively evaluates quiz attempt on backend, computes score, persists summary."""
        attempt = self.repository.get_quiz_attempt(
            attempt_id=attempt_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not attempt:
            raise ValueError("Quiz attempt not found")

        return self.evaluator.evaluate_attempt(attempt=attempt, answers=answers)

    def get_quiz_attempt_results(
        self,
        workspace_id: UUID,
        attempt_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> QuizAttemptResultResponse:
        """Retrieves verified evaluation report for a submitted quiz attempt."""
        attempt = self.repository.get_quiz_attempt(
            attempt_id=attempt_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not attempt:
            raise ValueError("Quiz attempt not found")
        if attempt.status != "evaluated" or not attempt.evaluation_summary:
            raise ValueError("Quiz attempt has not been evaluated yet")

        summary = attempt.evaluation_summary
        results = [QuizAttemptResultDetail(**r) for r in summary.get("results", [])]

        return QuizAttemptResultResponse(
            attempt_id=attempt.id,
            title=attempt.title,
            status=QuizAttemptStatus(attempt.status),
            total_questions=summary.get("total_questions", attempt.total_questions),
            correct_count=summary.get("correct_count", attempt.correct_answers_count or 0),
            incorrect_count=summary.get("incorrect_count", 0),
            unanswered_count=summary.get("unanswered_count", 0),
            score_percentage=summary.get("score_percentage", attempt.score_percentage or 0.0),
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            results=results,
        )

    # =========================================================================
    # C8.8: Verified Explanations & Source Citations
    # =========================================================================

    def get_question_explanation(
        self,
        workspace_id: UUID,
        attempt_id: UUID,
        question_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> QuestionExplanationResponse:
        """Retrieves pedagogical explanation for a question in an evaluated quiz attempt."""
        return self.evidence_service.get_question_explanation(
            workspace_id=workspace_id,
            attempt_id=attempt_id,
            question_id=question_id,
            user_id=user_id,
        )

    def get_question_sources(
        self,
        workspace_id: UUID,
        attempt_id: UUID,
        question_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> QuestionSourcesResponse:
        """Retrieves and validates supporting document citations for an evaluated question."""
        return self.evidence_service.get_question_sources(
            workspace_id=workspace_id,
            attempt_id=attempt_id,
            question_id=question_id,
            user_id=user_id,
        )

    # =========================================================================
    # C8.9: Quiz History, Analytics & Independent Retakes
    # =========================================================================

    def retake_quiz_attempt(
        self,
        workspace_id: UUID,
        attempt_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> QuizAttemptResponse:
        """Creates a fresh in-progress attempt with the same questions and returns it."""
        new_attempt = self.repository.retake_quiz_attempt(
            workspace_id=workspace_id,
            attempt_id=attempt_id,
            user_id=user_id,
        )
        return self.get_quiz_attempt(
            workspace_id=workspace_id,
            attempt_id=new_attempt.id,
            user_id=user_id,
        )

    def get_quiz_history_summary(
        self,
        workspace_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> QuizHistorySummaryResponse:
        """Computes aggregate analytics and metrics across quiz attempts."""
        stats = self.repository.get_quiz_history_summary(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        return QuizHistorySummaryResponse(**stats)

    def get_quiz_history_trends(
        self,
        workspace_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> QuizHistoryTrendsResponse:
        """Extracts chronological performance trend points."""
        points = self.repository.get_quiz_history_trends(
            workspace_id=workspace_id,
            user_id=user_id,
        )
        return QuizHistoryTrendsResponse(
            trends=[QuizHistoryTrendPoint(**p) for p in points]
        )

    def _format_practice_questions(
        self,
        sampled_questions: List[Dict[str, Any]],
    ) -> List[QuizQuestionPracticeItem]:
        """Maps diverse question models to safe QuizQuestionPracticeItem (no answers leaked)."""
        items: List[QuizQuestionPracticeItem] = []
        for item in sampled_questions:
            q = item["question"]
            qtype = item["type"]
            doc_title: Optional[str] = None
            page_num: Optional[int] = None

            if qtype == "mcq":
                opts = [
                    MCQOptionPracticeResponse(
                        id=opt.id,
                        option_id=opt.option_id,
                        option_text=opt.option_text,
                    )
                    for opt in q.options
                ]
                if q.source_references and len(q.source_references) > 0:
                    doc_title = q.source_references[0].get("document_title") if isinstance(q.source_references[0], dict) else getattr(q.source_references[0], "document_title", None)
                    page_num = q.source_references[0].get("page_number") if isinstance(q.source_references[0], dict) else getattr(q.source_references[0], "page_number", None)

                items.append(
                    QuizQuestionPracticeItem(
                        id=q.id,
                        question_type="mcq",
                        question_text=q.question_text,
                        difficulty=QuestionDifficulty(q.difficulty),
                        options=opts,
                        document_title=doc_title,
                        page_number=page_num,
                    )
                )

            elif qtype == "true_false":
                if q.source_references and len(q.source_references) > 0:
                    doc_title = q.source_references[0].get("document_title") if isinstance(q.source_references[0], dict) else getattr(q.source_references[0], "document_title", None)
                    page_num = q.source_references[0].get("page_number") if isinstance(q.source_references[0], dict) else getattr(q.source_references[0], "page_number", None)

                items.append(
                    QuizQuestionPracticeItem(
                        id=q.id,
                        question_type="true_false",
                        question_text=q.statement,
                        difficulty=QuestionDifficulty(q.difficulty),
                        document_title=doc_title,
                        page_number=page_num,
                    )
                )

            elif qtype == "fill_blank":
                if q.source_reference:
                    doc_title = q.source_reference.get("document_title") if isinstance(q.source_reference, dict) else getattr(q.source_reference, "document_title", None)
                    page_num = q.source_reference.get("page_number") if isinstance(q.source_reference, dict) else getattr(q.source_reference, "page_number", None)

                items.append(
                    QuizQuestionPracticeItem(
                        id=q.id,
                        question_type="fill_blank",
                        question_text=q.sentence_with_blank,
                        difficulty=QuestionDifficulty(q.difficulty),
                        hint=q.hint,
                        document_title=doc_title,
                        page_number=page_num,
                    )
                )
        return items

    # =========================================================================
    # DTO Formatters & Answer Key Protection
    # =========================================================================

    @staticmethod
    def format_mcq_practice(orm: MCQQuestion) -> MCQPracticeResponse:
        """Shields correct option ID and explanations to prevent answer leakage."""
        options = [
            MCQOptionPracticeResponse(
                id=opt.id,
                option_id=opt.option_id,
                option_text=opt.option_text,
            )
            for opt in orm.options
        ]
        return MCQPracticeResponse(
            id=orm.id,
            workspace_id=orm.workspace_id,
            generation_id=orm.generation_id,
            question_text=orm.question_text,
            difficulty=orm.difficulty,
            question_type=orm.question_type,
            topic_tags=orm.topic_tags or [],
            options=options,
            created_at=orm.created_at,
        )

    @staticmethod
    def format_mcq_review(orm: MCQQuestion) -> MCQReviewResponse:
        """Full answer key, explanation, and evidence references."""
        options = [
            MCQOptionReviewResponse(
                id=opt.id,
                option_id=opt.option_id,
                option_text=opt.option_text,
                is_correct=opt.is_correct,
            )
            for opt in orm.options
        ]
        return MCQReviewResponse(
            id=orm.id,
            workspace_id=orm.workspace_id,
            generation_id=orm.generation_id,
            question_text=orm.question_text,
            difficulty=orm.difficulty,
            question_type=orm.question_type,
            correct_option_id=orm.correct_option_id,
            explanation=orm.explanation,
            topic_tags=orm.topic_tags or [],
            options=options,
            source_references=orm.source_references or [],
            created_at=orm.created_at,
        )

    @staticmethod
    def format_fill_blank_practice(orm: FillBlankExercise) -> FillBlankPracticeResponse:
        """Shields canonical answer, variants, and explanation to prevent answer leakage."""
        return FillBlankPracticeResponse(
            id=orm.id,
            workspace_id=orm.workspace_id,
            generation_id=orm.generation_id,
            sentence_with_blank=orm.sentence_with_blank,
            difficulty=orm.difficulty,
            hint=orm.hint,
            created_at=orm.created_at,
        )

    @staticmethod
    def format_fill_blank_review(orm: FillBlankExercise) -> FillBlankReviewResponse:
        """Full answer key, character offsets, variants, and explanation."""
        return FillBlankReviewResponse(
            id=orm.id,
            workspace_id=orm.workspace_id,
            generation_id=orm.generation_id,
            sentence_with_blank=orm.sentence_with_blank,
            original_sentence=orm.original_sentence,
            canonical_answer=orm.canonical_answer,
            accepted_answers=orm.accepted_answers or [],
            target_start_offset=orm.target_start_offset,
            target_end_offset=orm.target_end_offset,
            difficulty=orm.difficulty,
            hint=orm.hint,
            explanation=orm.explanation,
            source_reference=orm.source_reference,
            created_at=orm.created_at,
        )

    @staticmethod
    def format_true_false_practice(orm: TrueFalseQuestion) -> TrueFalsePracticeResponse:
        """Shields truth value and misconception explanation during practice."""
        return TrueFalsePracticeResponse(
            id=orm.id,
            workspace_id=orm.workspace_id,
            generation_id=orm.generation_id,
            statement=orm.statement,
            difficulty=orm.difficulty,
            topic=orm.topic,
            created_at=orm.created_at,
        )

    @staticmethod
    def format_true_false_review(orm: TrueFalseQuestion) -> TrueFalseReviewResponse:
        """Reveals truth value, misconception breakdown, and supporting sources."""
        return TrueFalseReviewResponse(
            id=orm.id,
            workspace_id=orm.workspace_id,
            generation_id=orm.generation_id,
            statement=orm.statement,
            correct_answer=orm.correct_answer,
            explanation=orm.explanation,
            difficulty=orm.difficulty,
            topic=orm.topic,
            validation_status=orm.validation_status,
            source_references=orm.source_references or [],
            created_at=orm.created_at,
        )

    @staticmethod
    def format_flashcard(orm: Flashcard) -> FlashcardResponse:
        """Full active recall flashcard representation."""
        return FlashcardResponse(
            id=orm.id,
            workspace_id=orm.workspace_id,
            generation_id=orm.generation_id,
            front=orm.front,
            back=orm.back,
            card_type=orm.card_type,
            difficulty=orm.difficulty,
            topic=orm.topic,
            validation_status=orm.validation_status,
            source_references=orm.source_references or [],
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
