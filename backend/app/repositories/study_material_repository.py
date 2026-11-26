"""Repository for Knovera Study Material Persistence and Retrieval (Phase 8)."""

from datetime import datetime, timezone
import random
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session, joinedload

from backend.app.core.logging import get_logger
from backend.app.ml.study_materials.schemas import (
    FillBlankExerciseCreate,
    FlashcardCreate,
    MCQQuestionCreate,
    QuizAttemptAnswerSubmit,
    RevisionNoteCreate,
    TrueFalseQuestionCreate,
)
from backend.app.models.study_material import (
    FillBlankExercise,
    Flashcard,
    MCQOption,
    MCQQuestion,
    QuizAttempt,
    QuizAttemptAnswer,
    RevisionNote,
    StudyMaterialGeneration,
    TrueFalseQuestion,
)

logger = get_logger("knovera.repositories.study_material")


class StudyMaterialRepository:
    """Handles database transactions, persistence, and queries for study materials and quizzes."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # =========================================================================
    # Generation Run Lifecycle
    # =========================================================================

    def create_generation_run(
        self,
        workspace_id: uuid.UUID,
        material_type: str,
        requested_count: int,
        provider_name: str,
        model_name: str,
        scope_type: str,
        scope_config: Optional[Dict[str, Any]] = None,
        status: str = "running",
    ) -> StudyMaterialGeneration:
        """Initializes a new study material generation record."""
        run = StudyMaterialGeneration(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            material_type=material_type,
            status=status,
            requested_count=requested_count,
            generated_count=0,
            validated_count=0,
            rejected_count=0,
            duration_ms=0,
            provider_name=provider_name,
            model_name=model_name,
            scope_type=scope_type,
            scope_config=scope_config or {},
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def complete_generation_run(
        self,
        generation_id: uuid.UUID,
        status: str,
        generated_count: int,
        validated_count: int,
        rejected_count: int,
        duration_ms: int,
        quality_report: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[StudyMaterialGeneration]:
        """Marks a generation run as completed, completed_with_warnings, or failed."""
        run = self.session.get(StudyMaterialGeneration, generation_id)
        if not run:
            return None

        run.status = status
        run.generated_count = generated_count
        run.validated_count = validated_count
        run.rejected_count = rejected_count
        run.duration_ms = duration_ms
        run.quality_report = quality_report
        run.error_message = error_message
        run.completed_at = datetime.now(timezone.utc)

        self.session.commit()
        self.session.refresh(run)
        return run

    def get_generation_run(
        self,
        generation_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Optional[StudyMaterialGeneration]:
        """Retrieves a single generation run ensuring workspace authorization."""
        stmt = select(StudyMaterialGeneration).where(
            StudyMaterialGeneration.id == generation_id,
            StudyMaterialGeneration.workspace_id == workspace_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_generation_runs(
        self,
        workspace_id: uuid.UUID,
        material_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[StudyMaterialGeneration], int]:
        """Lists historical generation runs for an authorized workspace."""
        base_stmt = select(StudyMaterialGeneration).where(
            StudyMaterialGeneration.workspace_id == workspace_id
        )
        if material_type:
            base_stmt = base_stmt.where(StudyMaterialGeneration.material_type == material_type)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = self.session.execute(count_stmt).scalar() or 0

        items_stmt = (
            base_stmt.order_by(desc(StudyMaterialGeneration.created_at))
            .offset(offset)
            .limit(limit)
        )
        runs = list(self.session.execute(items_stmt).scalars().all())
        return runs, total

    # =========================================================================
    # C8.1: Revision Notes
    # =========================================================================

    def save_revision_note(
        self,
        workspace_id: uuid.UUID,
        generation_id: Optional[uuid.UUID],
        note_data: RevisionNoteCreate,
    ) -> RevisionNote:
        """Persists a generated revision note."""
        now = datetime.now(timezone.utc)
        note = RevisionNote(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            generation_id=generation_id,
            title=note_data.title,
            overview=note_data.overview,
            length=note_data.length.value,
            detail_level=note_data.detail_level.value,
            focus=note_data.focus.value,
            sections=[s.model_dump() for s in note_data.sections],
            key_concepts=[c.model_dump() for c in note_data.key_concepts],
            important_points=note_data.important_points,
            formulas=[f.model_dump() for f in note_data.formulas],
            quick_summary=note_data.quick_summary,
            source_references=[r.model_dump(mode="json") for r in note_data.source_references],
            created_at=now,
            updated_at=now,
        )
        self.session.add(note)
        self.session.commit()
        self.session.refresh(note)
        return note

    def get_revision_note(
        self,
        note_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Optional[RevisionNote]:
        """Retrieves a single revision note verifying workspace tenancy."""
        stmt = select(RevisionNote).where(
            RevisionNote.id == note_id,
            RevisionNote.workspace_id == workspace_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_revision_notes(
        self,
        workspace_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[RevisionNote], int]:
        """Lists revision notes in a workspace."""
        base_stmt = select(RevisionNote).where(RevisionNote.workspace_id == workspace_id)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = self.session.execute(count_stmt).scalar() or 0

        items_stmt = (
            base_stmt.order_by(desc(RevisionNote.created_at))
            .offset(offset)
            .limit(limit)
        )
        notes = list(self.session.execute(items_stmt).scalars().all())
        return notes, total

    # =========================================================================
    # C8.2: Multiple-Choice Questions (MCQs)
    # =========================================================================

    def save_mcq_questions(
        self,
        workspace_id: uuid.UUID,
        generation_id: Optional[uuid.UUID],
        questions: List[MCQQuestionCreate],
    ) -> List[MCQQuestion]:
        """Persists validated MCQ questions with their 4 options atomically."""
        saved_questions: List[MCQQuestion] = []
        now = datetime.now(timezone.utc)

        for q_create in questions:
            q_id = uuid.uuid4()
            q_orm = MCQQuestion(
                id=q_id,
                workspace_id=workspace_id,
                generation_id=generation_id,
                question_text=q_create.question_text,
                difficulty=q_create.difficulty.value,
                question_type=q_create.question_type.value,
                correct_option_id=q_create.correct_option_id,
                explanation=q_create.explanation,
                topic_tags=q_create.topic_tags,
                source_references=[r.model_dump(mode="json") for r in q_create.source_references],
                is_active=True,
                created_at=now,
                updated_at=now,
            )

            for opt in q_create.options:
                opt_orm = MCQOption(
                    id=uuid.uuid4(),
                    question_id=q_id,
                    option_id=opt.option_id,
                    option_text=opt.option_text,
                    is_correct=opt.is_correct,
                    created_at=now,
                )
                q_orm.options.append(opt_orm)

            self.session.add(q_orm)
            saved_questions.append(q_orm)

        self.session.commit()
        for q in saved_questions:
            self.session.refresh(q)
        return saved_questions

    def get_mcq_question(
        self,
        question_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Optional[MCQQuestion]:
        """Retrieves a single MCQ with options preloaded."""
        stmt = (
            select(MCQQuestion)
            .options(joinedload(MCQQuestion.options))
            .where(
                MCQQuestion.id == question_id,
                MCQQuestion.workspace_id == workspace_id,
                MCQQuestion.is_active.is_(True),
            )
        )
        return self.session.execute(stmt).unique().scalar_one_or_none()

    def list_mcq_questions(
        self,
        workspace_id: uuid.UUID,
        difficulty: Optional[str] = None,
        question_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[MCQQuestion], int]:
        """Lists MCQs for a workspace with options eagerly loaded."""
        base_stmt = select(MCQQuestion).where(
            MCQQuestion.workspace_id == workspace_id,
            MCQQuestion.is_active.is_(True),
        )
        if difficulty:
            base_stmt = base_stmt.where(MCQQuestion.difficulty == difficulty)
        if question_type:
            base_stmt = base_stmt.where(MCQQuestion.question_type == question_type)

        count_stmt = select(func.count(MCQQuestion.id)).where(
            MCQQuestion.workspace_id == workspace_id,
            MCQQuestion.is_active.is_(True),
        )
        if difficulty:
            count_stmt = count_stmt.where(MCQQuestion.difficulty == difficulty)
        if question_type:
            count_stmt = count_stmt.where(MCQQuestion.question_type == question_type)

        total = self.session.execute(count_stmt).scalar() or 0

        items_stmt = (
            base_stmt.options(joinedload(MCQQuestion.options))
            .order_by(desc(MCQQuestion.created_at))
            .offset(offset)
            .limit(limit)
        )
        questions = list(self.session.execute(items_stmt).unique().scalars().all())
        return questions, total

    # =========================================================================
    # C8.3: Fill-in-the-Blanks Exercises
    # =========================================================================

    def save_fill_blank_exercises(
        self,
        workspace_id: uuid.UUID,
        generation_id: Optional[uuid.UUID],
        exercises: List[FillBlankExerciseCreate],
    ) -> List[FillBlankExercise]:
        """Persists validated fill-in-the-blank items."""
        saved_items: List[FillBlankExercise] = []
        now = datetime.now(timezone.utc)

        for ex in exercises:
            ex_orm = FillBlankExercise(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                generation_id=generation_id,
                chunk_id=ex.chunk_id,
                document_id=ex.document_id,
                sentence_with_blank=ex.sentence_with_blank,
                original_sentence=ex.original_sentence,
                canonical_answer=ex.canonical_answer,
                accepted_answers=ex.accepted_answers,
                target_start_offset=ex.target_start_offset,
                target_end_offset=ex.target_end_offset,
                difficulty=ex.difficulty.value,
                hint=ex.hint,
                explanation=ex.explanation,
                source_reference=ex.source_reference.model_dump(mode="json") if ex.source_reference else None,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            self.session.add(ex_orm)
            saved_items.append(ex_orm)

        self.session.commit()
        for item in saved_items:
            self.session.refresh(item)
        return saved_items

    def get_fill_blank_exercise(
        self,
        exercise_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Optional[FillBlankExercise]:
        """Retrieves a single fill-in-the-blank item."""
        stmt = select(FillBlankExercise).where(
            FillBlankExercise.id == exercise_id,
            FillBlankExercise.workspace_id == workspace_id,
            FillBlankExercise.is_active.is_(True),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_fill_blank_exercises(
        self,
        workspace_id: uuid.UUID,
        difficulty: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[FillBlankExercise], int]:
        """Lists fill-in-the-blank exercises."""
        base_stmt = select(FillBlankExercise).where(
            FillBlankExercise.workspace_id == workspace_id,
            FillBlankExercise.is_active.is_(True),
        )
        if difficulty:
            base_stmt = base_stmt.where(FillBlankExercise.difficulty == difficulty)

        count_stmt = select(func.count(FillBlankExercise.id)).where(
            FillBlankExercise.workspace_id == workspace_id,
            FillBlankExercise.is_active.is_(True),
        )
        if difficulty:
            count_stmt = count_stmt.where(FillBlankExercise.difficulty == difficulty)

        total = self.session.execute(count_stmt).scalar() or 0

        items_stmt = (
            base_stmt.order_by(desc(FillBlankExercise.created_at))
            .offset(offset)
            .limit(limit)
        )
        items = list(self.session.execute(items_stmt).scalars().all())
        return items, total

    # =========================================================================
    # C8.4: True/False Questions
    # =========================================================================

    def save_true_false_questions(
        self,
        workspace_id: uuid.UUID,
        generation_id: Optional[uuid.UUID],
        questions: List[TrueFalseQuestionCreate],
    ) -> List[TrueFalseQuestion]:
        """Persists validated True/False questions."""
        saved_items: List[TrueFalseQuestion] = []
        now = datetime.now(timezone.utc)

        for q in questions:
            tf_orm = TrueFalseQuestion(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                generation_id=generation_id,
                chunk_id=q.chunk_id,
                document_id=q.document_id,
                statement=q.statement,
                correct_answer=q.correct_answer,
                explanation=q.explanation,
                difficulty=q.difficulty.value,
                topic=q.topic,
                validation_status=q.validation_status.value,
                source_references=[r.model_dump(mode="json") for r in q.source_references],
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            self.session.add(tf_orm)
            saved_items.append(tf_orm)

        self.session.commit()
        for item in saved_items:
            self.session.refresh(item)
        return saved_items

    def get_true_false_question(
        self,
        question_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Optional[TrueFalseQuestion]:
        """Retrieves a single True/False question."""
        stmt = select(TrueFalseQuestion).where(
            TrueFalseQuestion.id == question_id,
            TrueFalseQuestion.workspace_id == workspace_id,
            TrueFalseQuestion.is_active.is_(True),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_true_false_questions(
        self,
        workspace_id: uuid.UUID,
        difficulty: Optional[str] = None,
        validation_status: Optional[str] = None,
        generation_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[TrueFalseQuestion], int]:
        """Lists True/False questions for a workspace."""
        base_stmt = select(TrueFalseQuestion).where(
            TrueFalseQuestion.workspace_id == workspace_id,
            TrueFalseQuestion.is_active.is_(True),
        )
        if difficulty:
            base_stmt = base_stmt.where(TrueFalseQuestion.difficulty == difficulty)
        if validation_status:
            base_stmt = base_stmt.where(TrueFalseQuestion.validation_status == validation_status)
        if generation_id:
            base_stmt = base_stmt.where(TrueFalseQuestion.generation_id == generation_id)

        count_stmt = select(func.count(TrueFalseQuestion.id)).where(
            TrueFalseQuestion.workspace_id == workspace_id,
            TrueFalseQuestion.is_active.is_(True),
        )
        if difficulty:
            count_stmt = count_stmt.where(TrueFalseQuestion.difficulty == difficulty)
        if validation_status:
            count_stmt = count_stmt.where(TrueFalseQuestion.validation_status == validation_status)
        if generation_id:
            count_stmt = count_stmt.where(TrueFalseQuestion.generation_id == generation_id)

        total = self.session.execute(count_stmt).scalar() or 0

        items_stmt = (
            base_stmt.order_by(desc(TrueFalseQuestion.created_at))
            .offset(offset)
            .limit(limit)
        )
        items = list(self.session.execute(items_stmt).scalars().all())
        return items, total

    # =========================================================================
    # C8.5: Flashcards
    # =========================================================================

    def save_flashcards(
        self,
        workspace_id: uuid.UUID,
        generation_id: Optional[uuid.UUID],
        cards: List[FlashcardCreate],
    ) -> List[Flashcard]:
        """Persists validated flashcards."""
        saved_items: List[Flashcard] = []
        now = datetime.now(timezone.utc)

        for card in cards:
            fc_orm = Flashcard(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                generation_id=generation_id,
                chunk_id=card.chunk_id,
                document_id=card.document_id,
                front=card.front,
                back=card.back,
                card_type=card.card_type.value,
                difficulty=card.difficulty.value,
                topic=card.topic,
                validation_status=card.validation_status.value,
                source_references=[r.model_dump(mode="json") for r in card.source_references],
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            self.session.add(fc_orm)
            saved_items.append(fc_orm)

        self.session.commit()
        for item in saved_items:
            self.session.refresh(item)
        return saved_items

    def get_flashcard(
        self,
        card_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Optional[Flashcard]:
        """Retrieves a single flashcard."""
        stmt = select(Flashcard).where(
            Flashcard.id == card_id,
            Flashcard.workspace_id == workspace_id,
            Flashcard.is_active.is_(True),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_flashcards(
        self,
        workspace_id: uuid.UUID,
        difficulty: Optional[str] = None,
        card_type: Optional[str] = None,
        topic: Optional[str] = None,
        generation_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Flashcard], int]:
        """Lists flashcards for a workspace."""
        base_stmt = select(Flashcard).where(
            Flashcard.workspace_id == workspace_id,
            Flashcard.is_active.is_(True),
        )
        if difficulty:
            base_stmt = base_stmt.where(Flashcard.difficulty == difficulty)
        if card_type:
            base_stmt = base_stmt.where(Flashcard.card_type == card_type)
        if topic:
            base_stmt = base_stmt.where(Flashcard.topic.ilike(f"%{topic}%"))
        if generation_id:
            base_stmt = base_stmt.where(Flashcard.generation_id == generation_id)

        count_stmt = select(func.count(Flashcard.id)).where(
            Flashcard.workspace_id == workspace_id,
            Flashcard.is_active.is_(True),
        )
        if difficulty:
            count_stmt = count_stmt.where(Flashcard.difficulty == difficulty)
        if card_type:
            count_stmt = count_stmt.where(Flashcard.card_type == card_type)
        if topic:
            count_stmt = count_stmt.where(Flashcard.topic.ilike(f"%{topic}%"))
        if generation_id:
            count_stmt = count_stmt.where(Flashcard.generation_id == generation_id)

        total = self.session.execute(count_stmt).scalar() or 0

        items_stmt = (
            base_stmt.order_by(desc(Flashcard.created_at))
            .offset(offset)
            .limit(limit)
        )
        items = list(self.session.execute(items_stmt).scalars().all())
        return items, total

    # =========================================================================
    # C8.6: Interactive Quiz Attempts & Answers
    # =========================================================================

    def create_quiz_attempt(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        questions_order: List[Dict[str, Any]],
        total_questions: int,
    ) -> QuizAttempt:
        """Creates a new quiz attempt record."""
        now = datetime.now(timezone.utc)
        attempt = QuizAttempt(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            status="in_progress",
            total_questions=total_questions,
            correct_answers_count=0,
            score_percentage=0.0,
            questions_order=questions_order,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(attempt)
        self.session.commit()
        self.session.refresh(attempt)
        return attempt

    def get_quiz_attempt(
        self,
        attempt_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Optional[QuizAttempt]:
        """Retrieves a single quiz attempt with options/answers preloaded."""
        stmt = (
            select(QuizAttempt)
            .options(joinedload(QuizAttempt.answers))
            .where(
                QuizAttempt.id == attempt_id,
                QuizAttempt.workspace_id == workspace_id,
            )
        )
        if user_id:
            stmt = stmt.where(QuizAttempt.user_id == user_id)
        return self.session.execute(stmt).unique().scalar_one_or_none()

    def list_quiz_attempts(
        self,
        workspace_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[QuizAttempt], int]:
        """Lists historical quiz attempts in workspace with filtering, sorting, and pagination."""
        base_stmt = select(QuizAttempt).where(QuizAttempt.workspace_id == workspace_id)
        if user_id:
            base_stmt = base_stmt.where(QuizAttempt.user_id == user_id)
        if status:
            base_stmt = base_stmt.where(QuizAttempt.status == status)
        if search:
            base_stmt = base_stmt.where(QuizAttempt.title.ilike(f"%{search.strip()}%"))
        if from_date:
            base_stmt = base_stmt.where(QuizAttempt.created_at >= from_date)
        if to_date:
            base_stmt = base_stmt.where(QuizAttempt.created_at <= to_date)

        count_stmt = select(func.count(QuizAttempt.id)).where(QuizAttempt.workspace_id == workspace_id)
        if user_id:
            count_stmt = count_stmt.where(QuizAttempt.user_id == user_id)
        if status:
            count_stmt = count_stmt.where(QuizAttempt.status == status)
        if search:
            count_stmt = count_stmt.where(QuizAttempt.title.ilike(f"%{search.strip()}%"))
        if from_date:
            count_stmt = count_stmt.where(QuizAttempt.created_at >= from_date)
        if to_date:
            count_stmt = count_stmt.where(QuizAttempt.created_at <= to_date)

        total = self.session.execute(count_stmt).scalar() or 0

        # Sort order determination
        sort_col = QuizAttempt.score_percentage if sort_by == "score_percentage" else QuizAttempt.created_at
        order_clause = desc(sort_col) if sort_order.lower() == "desc" else asc(sort_col)

        items_stmt = (
            base_stmt.order_by(order_clause)
            .offset(offset)
            .limit(limit)
        )
        attempts = list(self.session.execute(items_stmt).unique().scalars().all())
        return attempts, total

    def get_quiz_history_summary(
        self,
        workspace_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Calculates aggregate performance statistics across quiz attempts."""
        stmt = select(QuizAttempt).where(QuizAttempt.workspace_id == workspace_id)
        if user_id:
            stmt = stmt.where(QuizAttempt.user_id == user_id)

        all_attempts = list(self.session.execute(stmt).unique().scalars().all())

        total_attempts = len(all_attempts)
        completed = [a for a in all_attempts if a.status == "evaluated"]
        in_progress = [a for a in all_attempts if a.status == "in_progress"]

        completed_count = len(completed)
        in_progress_count = len(in_progress)

        avg_score = 0.0
        total_questions_answered = 0
        total_correct = 0

        if completed_count > 0:
            score_sum = sum(a.score_percentage or 0.0 for a in completed)
            avg_score = round(score_sum / completed_count, 2)
            total_questions_answered = sum(a.total_questions or 0 for a in completed)
            total_correct = sum(a.correct_answers_count or 0 for a in completed)

        overall_correct_rate = (
            round((total_correct / total_questions_answered) * 100.0, 2)
            if total_questions_answered > 0
            else 0.0
        )

        return {
            "total_attempts": total_attempts,
            "completed_attempts": completed_count,
            "in_progress_attempts": in_progress_count,
            "average_score": avg_score,
            "overall_correct_rate": overall_correct_rate,
            "total_questions_answered": total_questions_answered,
            "total_correct_answers": total_correct,
        }

    def get_quiz_history_trends(
        self,
        workspace_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """Returns chronological timeline data of completed quiz evaluations."""
        stmt = (
            select(QuizAttempt)
            .where(
                QuizAttempt.workspace_id == workspace_id,
                QuizAttempt.status == "evaluated",
            )
        )
        if user_id:
            stmt = stmt.where(QuizAttempt.user_id == user_id)

        stmt = stmt.order_by(asc(QuizAttempt.submitted_at), asc(QuizAttempt.created_at))
        completed = list(self.session.execute(stmt).unique().scalars().all())

        return [
            {
                "attempt_id": a.id,
                "title": a.title,
                "score_percentage": a.score_percentage or 0.0,
                "total_questions": a.total_questions,
                "correct_count": a.correct_answers_count or 0,
                "completed_at": a.submitted_at or a.created_at,
            }
            for a in completed
        ]

    def retake_quiz_attempt(
        self,
        workspace_id: uuid.UUID,
        attempt_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> QuizAttempt:
        """Creates a fresh, independent in-progress attempt cloning questions from original."""
        original = self.get_quiz_attempt(
            attempt_id=attempt_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not original:
            raise ValueError("Original quiz attempt not found")

        # Determine retake title
        base_title = original.title
        title = base_title if base_title.startswith("Retake: ") else f"Retake: {base_title}"

        now = datetime.now(timezone.utc)
        new_attempt = QuizAttempt(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=user_id or original.user_id,
            title=title,
            status="in_progress",
            total_questions=original.total_questions,
            correct_answers_count=0,
            score_percentage=0.0,
            questions_order=list(original.questions_order or []),
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(new_attempt)
        self.session.commit()
        self.session.refresh(new_attempt)
        return new_attempt

    def save_quiz_attempt_answers(
        self,
        attempt_id: uuid.UUID,
        answers: List[QuizAttemptAnswerSubmit],
    ) -> List[QuizAttemptAnswer]:
        """Upserts learner answers for an active attempt."""
        now = datetime.now(timezone.utc)
        saved: List[QuizAttemptAnswer] = []

        for ans in answers:
            # Check if answer record already exists for question
            stmt = select(QuizAttemptAnswer).where(
                QuizAttemptAnswer.attempt_id == attempt_id,
                QuizAttemptAnswer.question_id == ans.question_id,
            )
            existing = self.session.execute(stmt).scalar_one_or_none()

            if existing:
                existing.selected_answer = ans.selected_answer
                existing.updated_at = now
                saved.append(existing)
            else:
                new_ans = QuizAttemptAnswer(
                    id=uuid.uuid4(),
                    attempt_id=attempt_id,
                    question_id=ans.question_id,
                    question_type=ans.question_type,
                    selected_answer=ans.selected_answer,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(new_ans)
                saved.append(new_ans)

        self.session.commit()
        for item in saved:
            self.session.refresh(item)
        return saved

    def finalize_quiz_attempt(
        self,
        attempt_id: uuid.UUID,
        correct_count: int,
        score_percentage: float,
        evaluation_summary: Dict[str, Any],
    ) -> Optional[QuizAttempt]:
        """Finalizes and marks attempt as evaluated."""
        attempt = self.session.get(QuizAttempt, attempt_id)
        if not attempt:
            return None

        now = datetime.now(timezone.utc)
        attempt.status = "evaluated"
        attempt.correct_answers_count = correct_count
        attempt.score_percentage = score_percentage
        attempt.evaluation_summary = evaluation_summary
        attempt.submitted_at = now
        attempt.updated_at = now

        self.session.commit()
        self.session.refresh(attempt)
        return attempt

    # =========================================================================
    # Question Sampling & Cross-Type Fetching for Quizzes
    # =========================================================================

    def get_questions_by_ids(
        self,
        workspace_id: uuid.UUID,
        question_ids: List[uuid.UUID],
    ) -> Dict[str, List[Any]]:
        """Fetches heterogeneous questions (MCQ, True/False, FillBlank) by ID within workspace."""
        if not question_ids:
            return {"mcqs": [], "true_false": [], "fill_blanks": []}

        mcqs = list(
            self.session.execute(
                select(MCQQuestion)
                .options(joinedload(MCQQuestion.options))
                .where(
                    MCQQuestion.id.in_(question_ids),
                    MCQQuestion.workspace_id == workspace_id,
                    MCQQuestion.is_active.is_(True),
                )
            ).unique().scalars().all()
        )

        tf = list(
            self.session.execute(
                select(TrueFalseQuestion).where(
                    TrueFalseQuestion.id.in_(question_ids),
                    TrueFalseQuestion.workspace_id == workspace_id,
                    TrueFalseQuestion.is_active.is_(True),
                )
            ).scalars().all()
        )

        fb = list(
            self.session.execute(
                select(FillBlankExercise).where(
                    FillBlankExercise.id.in_(question_ids),
                    FillBlankExercise.workspace_id == workspace_id,
                    FillBlankExercise.is_active.is_(True),
                )
            ).scalars().all()
        )

        return {"mcqs": mcqs, "true_false": tf, "fill_blanks": fb}

    def sample_quiz_questions(
        self,
        workspace_id: uuid.UUID,
        question_types: Optional[List[str]] = None,
        count: int = 10,
        difficulty: Optional[str] = None,
        generation_ids: Optional[List[uuid.UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """Samples questions across supported types for a quiz attempt."""
        selected_types = question_types or ["mcq", "true_false", "fill_blank"]
        items: List[Dict[str, Any]] = []

        if "mcq" in selected_types:
            stmt = select(MCQQuestion).where(
                MCQQuestion.workspace_id == workspace_id,
                MCQQuestion.is_active.is_(True),
            )
            if difficulty:
                stmt = stmt.where(MCQQuestion.difficulty == difficulty)
            if generation_ids:
                stmt = stmt.where(MCQQuestion.generation_id.in_(generation_ids))
            mcqs = list(self.session.execute(stmt.options(joinedload(MCQQuestion.options)).limit(count)).unique().scalars().all())
            for q in mcqs:
                items.append({"id": q.id, "type": "mcq", "question": q})

        if "true_false" in selected_types:
            stmt = select(TrueFalseQuestion).where(
                TrueFalseQuestion.workspace_id == workspace_id,
                TrueFalseQuestion.is_active.is_(True),
            )
            if difficulty:
                stmt = stmt.where(TrueFalseQuestion.difficulty == difficulty)
            if generation_ids:
                stmt = stmt.where(TrueFalseQuestion.generation_id.in_(generation_ids))
            tfs = list(self.session.execute(stmt.limit(count)).scalars().all())
            for q in tfs:
                items.append({"id": q.id, "type": "true_false", "question": q})

        if "fill_blank" in selected_types:
            stmt = select(FillBlankExercise).where(
                FillBlankExercise.workspace_id == workspace_id,
                FillBlankExercise.is_active.is_(True),
            )
            if difficulty:
                stmt = stmt.where(FillBlankExercise.difficulty == difficulty)
            if generation_ids:
                stmt = stmt.where(FillBlankExercise.generation_id.in_(generation_ids))
            fbs = list(self.session.execute(stmt.limit(count)).scalars().all())
            for q in fbs:
                items.append({"id": q.id, "type": "fill_blank", "question": q})

        # Shuffle and clamp to count
        random.shuffle(items)
        return items[:count]
