"""Quiz Evaluation Service (Phase 8: C8.7).

Authoritative, deterministic backend evaluation for Knovera quiz sessions:
- Multi-type evaluation (MCQ, True/False, Fill-in-the-Blanks)
- Robust answer normalization (Unicode NFC, whitespace collapsing, punctuation preservation)
- Numerical & decimal equivalence (e.g. 0.5 == 0.50, 42 == 42.0)
- Technical notation resilience (C++, Node.js, TF-IDF, snake_case)
- Idempotency and tamper-proof immutable evaluation snapshots
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import unicodedata
from uuid import UUID
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.ml.study_materials.schemas import (
    MCQOptionReviewResponse,
    QuestionDifficulty,
    QuizAttemptAnswerSubmit,
    QuizAttemptResultDetail,
    QuizAttemptResultResponse,
    QuizAttemptStatus,
    SourceReference,
)
from backend.app.models.study_material import (
    FillBlankExercise,
    MCQQuestion,
    QuizAttempt,
    QuizAttemptAnswer,
    TrueFalseQuestion,
)
from backend.app.repositories.study_material_repository import StudyMaterialRepository

logger = get_logger("knovera.study_materials.evaluation_service")


def normalize_text_answer(raw: Any) -> str:
    """Normalizes raw learner text answers for deterministic comparison.

    Rules:
    - Return empty string for None
    - Apply Unicode NFC normalization
    - Strip leading and trailing whitespace
    - Collapse consecutive internal whitespace into a single space
    - Preserve special programming and scientific symbols/punctuation (C++, Node.js, TF-IDF)
    - Lowercase for case-insensitive matching
    """
    if raw is None:
        return ""
    text = str(raw)
    text = unicodedata.normalize("NFC", text)
    # Collapse multiple whitespace characters into one
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def are_answers_equivalent(
    learner: Any,
    canonical: Any,
    accepted_variants: Optional[List[str]] = None,
) -> bool:
    """Compares learner answer against canonical target and accepted variants.

    Supports:
    1. Exact normalized text equality
    2. Numerical / decimal equivalence (e.g., 0.5 == 0.50, 12.0 == 12)
    """
    if learner is None:
        return False
    if isinstance(learner, str) and not learner.strip():
        return False

    norm_learner = normalize_text_answer(learner)
    targets = [str(canonical)] + [str(v) for v in (accepted_variants or [])]

    # Check if learner answer is a valid number
    learner_float: Optional[float] = None
    if re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", norm_learner):
        try:
            learner_float = float(norm_learner)
        except (ValueError, TypeError):
            learner_float = None

    for target in targets:
        norm_target = normalize_text_answer(target)
        if norm_learner == norm_target:
            return True

        if learner_float is not None:
            if re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", norm_target):
                try:
                    target_float = float(norm_target)
                    if abs(learner_float - target_float) < 1e-6:
                        return True
                except (ValueError, TypeError):
                    pass

    return False


class QuizEvaluationService:
    """Authoritative quiz assessment evaluator."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = StudyMaterialRepository(session)

    # =========================================================================
    # Single-Question Evaluators
    # =========================================================================

    def evaluate_mcq(
        self,
        mcq: MCQQuestion,
        learner_answer: Any,
    ) -> Tuple[bool, float, bool, str, Any, List[SourceReference]]:
        """Evaluates a multiple-choice question.

        Returns:
            (is_correct, score, is_unanswered, explanation, correct_val, source_refs)
        """
        explanation = mcq.explanation or "No explanation provided."
        correct_val = mcq.correct_option_id
        source_refs = [
            SourceReference(**r) if isinstance(r, dict) else r
            for r in (mcq.source_references or [])
        ]

        if learner_answer is None or (isinstance(learner_answer, str) and not learner_answer.strip()):
            return False, 0.0, True, explanation, correct_val, source_refs

        norm_learner = str(learner_answer).strip().upper()
        norm_correct = str(mcq.correct_option_id).strip().upper()

        # Check option ID match (e.g. "A", "B", "C", "D" or uuid)
        is_correct = (norm_learner == norm_correct)

        # Fallback check: if learner submitted full option text matching the correct option
        if not is_correct and mcq.options:
            for opt in mcq.options:
                if str(opt.option_id).strip().upper() == norm_correct:
                    if normalize_text_answer(opt.option_text) == normalize_text_answer(learner_answer):
                        is_correct = True
                        break

        score = 1.0 if is_correct else 0.0
        return is_correct, score, False, explanation, correct_val, source_refs

    def evaluate_true_false(
        self,
        tf: TrueFalseQuestion,
        learner_answer: Any,
    ) -> Tuple[bool, float, bool, str, Any, List[SourceReference]]:
        """Evaluates a true/false statement question.

        Returns:
            (is_correct, score, is_unanswered, explanation, correct_val, source_refs)
        """
        explanation = tf.explanation or "No explanation provided."
        correct_val = tf.correct_answer
        source_refs = [
            SourceReference(**r) if isinstance(r, dict) else r
            for r in (tf.source_references or [])
        ]

        if learner_answer is None or (isinstance(learner_answer, str) and not learner_answer.strip()):
            return False, 0.0, True, explanation, correct_val, source_refs

        learner_bool: Optional[bool] = None
        if isinstance(learner_answer, bool):
            learner_bool = learner_answer
        elif isinstance(learner_answer, str):
            s = learner_answer.strip().lower()
            if s in ("true", "t", "1", "yes"):
                learner_bool = True
            elif s in ("false", "f", "0", "no"):
                learner_bool = False
        elif isinstance(learner_answer, (int, float)):
            if learner_answer == 1:
                learner_bool = True
            elif learner_answer == 0:
                learner_bool = False

        if learner_bool is None:
            # Malformed/unrecognized answer value
            return False, 0.0, False, explanation, correct_val, source_refs

        is_correct = (learner_bool is bool(tf.correct_answer))
        score = 1.0 if is_correct else 0.0
        return is_correct, score, False, explanation, correct_val, source_refs

    def evaluate_fill_blank(
        self,
        fb: FillBlankExercise,
        learner_answer: Any,
    ) -> Tuple[bool, float, bool, str, Any, List[SourceReference]]:
        """Evaluates a fill-in-the-blank exercise with fuzzy/canonical normalization.

        Returns:
            (is_correct, score, is_unanswered, explanation, correct_val, source_refs)
        """
        explanation = fb.explanation or f"The target answer is '{fb.canonical_answer}'."
        correct_val = fb.canonical_answer
        source_refs = []
        if fb.source_reference:
            ref = fb.source_reference
            source_refs = [SourceReference(**ref) if isinstance(ref, dict) else ref]

        if learner_answer is None or (isinstance(learner_answer, str) and not learner_answer.strip()):
            return False, 0.0, True, explanation, correct_val, source_refs

        is_correct = are_answers_equivalent(
            learner=learner_answer,
            canonical=fb.canonical_answer,
            accepted_variants=fb.accepted_answers,
        )
        score = 1.0 if is_correct else 0.0
        return is_correct, score, False, explanation, correct_val, source_refs

    # =========================================================================
    # Full Attempt Evaluation Pipeline
    # =========================================================================

    def evaluate_attempt(
        self,
        attempt: QuizAttempt,
        answers: Optional[List[QuizAttemptAnswerSubmit]] = None,
    ) -> QuizAttemptResultResponse:
        """Evaluates all questions in an attempt, records scores, and freezes immutable summary.

        Idempotent: if attempt status is already 'evaluated', returns the frozen results.
        """
        # Idempotent return if already evaluated
        if attempt.status == QuizAttemptStatus.EVALUATED and attempt.evaluation_summary:
            summary = attempt.evaluation_summary
            results = [QuizAttemptResultDetail(**r) for r in summary.get("results", [])]
            return QuizAttemptResultResponse(
                attempt_id=attempt.id,
                title=attempt.title,
                status=QuizAttemptStatus.EVALUATED,
                total_questions=summary.get("total_questions", attempt.total_questions),
                correct_count=summary.get("correct_count", attempt.correct_answers_count or 0),
                incorrect_count=summary.get("incorrect_count", 0),
                unanswered_count=summary.get("unanswered_count", 0),
                score_percentage=summary.get("score_percentage", attempt.score_percentage or 0.0),
                started_at=attempt.started_at,
                submitted_at=attempt.submitted_at,
                results=results,
            )

        # Upsert submitted answers if provided
        if answers:
            self.repository.save_quiz_attempt_answers(
                attempt_id=attempt.id,
                answers=answers,
            )
            # Reload attempt answers
            attempt = self.repository.get_quiz_attempt(
                attempt_id=attempt.id,
                workspace_id=attempt.workspace_id,
                user_id=attempt.user_id,
            )
            if not attempt:
                raise ValueError("Quiz attempt reload failed")

        q_ids = [UUID(item["id"]) for item in (attempt.questions_order or [])]
        grouped = self.repository.get_questions_by_ids(
            workspace_id=attempt.workspace_id,
            question_ids=q_ids,
        )

        mcq_map = {q.id: q for q in grouped["mcqs"]}
        tf_map = {q.id: q for q in grouped["true_false"]}
        fb_map = {q.id: q for q in grouped["fill_blanks"]}
        answers_map = {a.question_id: a for a in (attempt.answers or [])}

        results: List[QuizAttemptResultDetail] = []
        correct_count = 0
        unanswered_count = 0

        for item in (attempt.questions_order or []):
            qid = UUID(item["id"])
            qtype = item.get("type") or item.get("question_type") or "mcq"
            ans_record = answers_map.get(qid)
            learner_val = ans_record.selected_answer if ans_record else None

            is_correct = False
            is_unanswered = False
            correct_val: Any = None
            explanation = ""
            source_refs: List[SourceReference] = []
            q_text = ""
            diff = QuestionDifficulty.MEDIUM

            if qtype == "mcq" and qid in mcq_map:
                mcq = mcq_map[qid]
                q_text = mcq.question_text
                diff = QuestionDifficulty(mcq.difficulty)
                (
                    is_correct,
                    _,
                    is_unanswered,
                    explanation,
                    correct_val,
                    source_refs,
                ) = self.evaluate_mcq(mcq, learner_val)

            elif qtype == "true_false" and qid in tf_map:
                tf = tf_map[qid]
                q_text = tf.statement
                diff = QuestionDifficulty(tf.difficulty)
                (
                    is_correct,
                    _,
                    is_unanswered,
                    explanation,
                    correct_val,
                    source_refs,
                ) = self.evaluate_true_false(tf, learner_val)

            elif qtype == "fill_blank" and qid in fb_map:
                fb = fb_map[qid]
                q_text = fb.sentence_with_blank
                diff = QuestionDifficulty(fb.difficulty)
                (
                    is_correct,
                    _,
                    is_unanswered,
                    explanation,
                    correct_val,
                    source_refs,
                ) = self.evaluate_fill_blank(fb, learner_val)

            if is_unanswered:
                unanswered_count += 1
            elif is_correct:
                correct_count += 1

            if ans_record:
                ans_record.is_correct = is_correct

            results.append(
                QuizAttemptResultDetail(
                    question_id=qid,
                    question_type=qtype,
                    question_text=q_text,
                    difficulty=diff,
                    learner_answer=learner_val,
                    correct_answer=correct_val,
                    is_correct=is_correct,
                    explanation=explanation,
                    source_references=source_refs,
                )
            )

        total_questions = len(attempt.questions_order or [])
        incorrect_count = max(0, total_questions - correct_count - unanswered_count)
        score_percentage = (
            round((correct_count / total_questions) * 100.0, 2)
            if total_questions > 0
            else 0.0
        )

        eval_summary = {
            "total_questions": total_questions,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "unanswered_count": unanswered_count,
            "score_percentage": score_percentage,
            "results": [r.model_dump(mode="json") for r in results],
        }

        finalized = self.repository.finalize_quiz_attempt(
            attempt_id=attempt.id,
            correct_count=correct_count,
            score_percentage=score_percentage,
            evaluation_summary=eval_summary,
        )

        # Phase 9 C9.6: Trigger BKT online mastery updates for evaluated attempt
        try:
            from backend.app.services.bkt_service import BKTService
            bkt_service = BKTService(self.session)
            bkt_service.process_attempt_evaluation(
                workspace_id=attempt.workspace_id,
                attempt_id=attempt.id,
                user_id=attempt.user_id,
            )
        except Exception as bkt_err:
            logger.warning("BKT mastery update notice: %s", bkt_err)

        # Phase 10 C10.1: Trigger fresh revision recommendations based on updated BKT mastery
        try:
            from backend.app.services.recommendation_service import RevisionRecommendationService
            from backend.app.schemas.recommendation import RevisionRecommendationGenerateRequest
            rec_service = RevisionRecommendationService(self.session)
            rec_service.generate_recommendations(
                workspace_id=attempt.workspace_id,
                user_id=attempt.user_id,
                req=RevisionRecommendationGenerateRequest(max_recommendations=10),
            )
        except Exception as rec_err:
            logger.warning("Recommendation generation notice: %s", rec_err)

        return QuizAttemptResultResponse(
            attempt_id=attempt.id,
            title=attempt.title,
            status=QuizAttemptStatus.EVALUATED,
            total_questions=total_questions,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            unanswered_count=unanswered_count,
            score_percentage=score_percentage,
            started_at=attempt.started_at,
            submitted_at=finalized.submitted_at if finalized else datetime.now(timezone.utc),
            results=results,
        )
