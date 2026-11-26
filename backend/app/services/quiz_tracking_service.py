"""Quiz Attempt Tracking Service for Knovera Learner Intelligence Foundation (Phase 9 C9.3).

Provides detailed operational tracking, question-level analytics, timing/revisions,
and concept performance attribution without modifying Phase 8 C8.9 Quiz History.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.learner_intelligence import (
    LearnerInteractionEvent,
    QuestionConceptMapping,
)
from backend.app.models.study_material import QuizAttempt, QuizAttemptAnswer
from backend.app.schemas.learner_intelligence import (
    ConceptPerformanceMetric,
    LearningInteractionsSummaryResponse,
    QuestionTrackingMetric,
    QuizAttemptConceptPerformanceResponse,
    QuizAttemptTrackingResponse,
)

logger = get_logger("knovera.services.quiz_tracking")


class QuizAttemptTrackingService:
    """Service for computing operational attempt tracking and concept performance attribution."""

    def __init__(self, db: Session):
        self.db = db

    def get_attempt_concept_performance(
        self,
        workspace_id: uuid.UUID,
        attempt_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> QuizAttemptConceptPerformanceResponse:
        """Computes concept-level performance breakdown for a quiz attempt."""
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
                detail="Cannot access performance data for an attempt belonging to another user.",
            )

        # Index answers by question_id
        answers_by_qid: Dict[uuid.UUID, QuizAttemptAnswer] = {
            a.question_id: a for a in attempt.answers
        }

        question_ids = list(answers_by_qid.keys())
        if not question_ids and attempt.questions_order:
            for item in attempt.questions_order:
                qid_str = item.get("id") or item.get("question_id")
                if qid_str:
                    try:
                        question_ids.append(uuid.UUID(str(qid_str)))
                    except (ValueError, TypeError):
                        pass

        concept_metrics_map: Dict[uuid.UUID, Dict[str, Any]] = defaultdict(
            lambda: {
                "name": "",
                "category": "concept",
                "attempted": 0,
                "answered": 0,
                "correct": 0,
                "incorrect": 0,
                "unanswered": 0,
            }
        )

        if question_ids:
            # Query mappings for these questions
            mappings = (
                self.db.query(QuestionConceptMapping)
                .join(KnowledgeNode, QuestionConceptMapping.concept_id == KnowledgeNode.id)
                .filter(
                    QuestionConceptMapping.workspace_id == workspace_id,
                    QuestionConceptMapping.question_id.in_(question_ids),
                    QuestionConceptMapping.validation_status.in_(["validated", "candidate"]),
                )
                .all()
            )

            # Map concepts to set of questions
            concept_to_questions: Dict[uuid.UUID, List[uuid.UUID]] = defaultdict(list)
            for m in mappings:
                cid = m.concept_id
                concept_to_questions[cid].append(m.question_id)
                if not concept_metrics_map[cid]["name"] and m.concept:
                    concept_metrics_map[cid]["name"] = m.concept.name
                    concept_metrics_map[cid]["category"] = m.concept.category

            for cid, qids in concept_to_questions.items():
                unique_qids = set(qids)
                concept_metrics_map[cid]["attempted"] = len(unique_qids)

                for qid in unique_qids:
                    ans = answers_by_qid.get(qid)
                    if not ans or ans.selected_answer is None:
                        concept_metrics_map[cid]["unanswered"] += 1
                    else:
                        concept_metrics_map[cid]["answered"] += 1
                        if ans.is_correct is True:
                            concept_metrics_map[cid]["correct"] += 1
                        else:
                            concept_metrics_map[cid]["incorrect"] += 1

        concepts: List[ConceptPerformanceMetric] = []
        for cid, stats in concept_metrics_map.items():
            answered = stats["answered"]
            correct = stats["correct"]
            correct_rate = round((correct / answered) * 100.0, 1) if answered > 0 else 0.0

            concepts.append(
                ConceptPerformanceMetric(
                    concept_id=cid,
                    concept_name=stats["name"] or "Unknown Concept",
                    category=stats["category"],
                    questions_attempted=stats["attempted"],
                    questions_answered=answered,
                    correct_answers=correct,
                    incorrect_answers=stats["incorrect"],
                    unanswered=stats["unanswered"],
                    correct_rate=correct_rate,
                )
            )

        # Sort by concept name
        concepts.sort(key=lambda x: x.concept_name.lower())

        return QuizAttemptConceptPerformanceResponse(
            attempt_id=attempt.id,
            title=attempt.title,
            status=attempt.status,
            evaluated_at=attempt.submitted_at,
            concepts=concepts,
        )

    def get_attempt_tracking(
        self,
        workspace_id: uuid.UUID,
        attempt_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> QuizAttemptTrackingResponse:
        """Computes comprehensive operational tracking metrics for a quiz attempt."""
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
                detail="Cannot access tracking data for an attempt belonging to another user.",
            )

        # Load all interaction events for this attempt
        events = (
            self.db.query(LearnerInteractionEvent)
            .filter(
                LearnerInteractionEvent.workspace_id == workspace_id,
                LearnerInteractionEvent.attempt_id == attempt_id,
            )
            .order_by(LearnerInteractionEvent.occurred_at.asc())
            .all()
        )

        events_by_question: Dict[uuid.UUID, List[LearnerInteractionEvent]] = defaultdict(list)
        for ev in events:
            if ev.question_id:
                events_by_question[ev.question_id].append(ev)

        # Index answers
        answers_by_qid: Dict[uuid.UUID, QuizAttemptAnswer] = {
            a.question_id: a for a in attempt.answers
        }

        # Build question order
        ordered_qids: List[Tuple[uuid.UUID, str, int]] = []
        if attempt.questions_order:
            for idx, item in enumerate(attempt.questions_order):
                qid_str = item.get("id") or item.get("question_id")
                qtype = item.get("question_type") or item.get("type") or "mcq"
                if qid_str:
                    try:
                        ordered_qids.append((uuid.UUID(str(qid_str)), qtype, idx + 1))
                    except (ValueError, TypeError):
                        pass

        if not ordered_qids:
            for idx, ans in enumerate(attempt.answers):
                ordered_qids.append((ans.question_id, ans.question_type, idx + 1))

        # Query mapped concept names for all question IDs
        all_qids = [q[0] for q in ordered_qids]
        mapped_concepts_by_qid: Dict[uuid.UUID, List[str]] = defaultdict(list)
        if all_qids:
            mappings = (
                self.db.query(QuestionConceptMapping)
                .join(KnowledgeNode, QuestionConceptMapping.concept_id == KnowledgeNode.id)
                .filter(
                    QuestionConceptMapping.workspace_id == workspace_id,
                    QuestionConceptMapping.question_id.in_(all_qids),
                )
                .all()
            )
            for m in mappings:
                if m.concept:
                    mapped_concepts_by_qid[m.question_id].append(m.concept.name)

        # Build QuestionTrackingMetric list
        question_metrics: List[QuestionTrackingMetric] = []
        for qid, qtype, display_order in ordered_qids:
            ans = answers_by_qid.get(qid)
            q_events = events_by_question.get(qid, [])

            is_answered = ans is not None and ans.selected_answer is not None
            is_correct = ans.is_correct if ans else None
            selected_answer = ans.selected_answer if ans else None

            # Calculate revision count
            revision_count = sum(
                1 for e in q_events if e.event_type in ("answer_revised", "answer_saved", "answer_selected")
            )
            if revision_count > 0:
                revision_count -= 1  # First selection is initial, subsequent are revisions

            hint_opened = any(e.event_type == "hint_opened" for e in q_events)
            explanation_opened = any(e.event_type == "explanation_opened" for e in q_events)
            source_opened = any(
                e.event_type in ("source_opened", "source_page_navigated") for e in q_events
            )

            # Response duration
            duration_ms: Optional[int] = None
            for e in q_events:
                if "duration_ms" in e.event_metadata:
                    try:
                        duration_ms = int(e.event_metadata["duration_ms"])
                        break
                    except (ValueError, TypeError):
                        pass
                elif "time_spent_ms" in e.event_metadata:
                    try:
                        duration_ms = int(e.event_metadata["time_spent_ms"])
                        break
                    except (ValueError, TypeError):
                        pass

            if duration_ms is None and len(q_events) >= 2:
                first_ts = q_events[0].occurred_at
                last_ts = q_events[-1].occurred_at
                duration_ms = int((last_ts - first_ts).total_seconds() * 1000)

            question_metrics.append(
                QuestionTrackingMetric(
                    question_id=qid,
                    question_type=qtype,
                    display_order=display_order,
                    is_answered=is_answered,
                    is_correct=is_correct,
                    selected_answer=selected_answer,
                    response_duration_ms=duration_ms,
                    revision_count=max(0, revision_count),
                    hint_opened=hint_opened,
                    explanation_opened=explanation_opened,
                    source_opened=source_opened,
                    mapped_concepts=mapped_concepts_by_qid.get(qid, []),
                )
            )

        # Attempt level metrics
        total_q = attempt.total_questions or len(ordered_qids)
        answered_c = sum(1 for qm in question_metrics if qm.is_answered)
        unanswered_c = max(0, total_q - answered_c)
        correct_c = attempt.correct_answers_count
        incorrect_c = max(0, answered_c - correct_c)

        total_duration_sec: Optional[int] = None
        if attempt.submitted_at and attempt.started_at:
            total_duration_sec = int((attempt.submitted_at - attempt.started_at).total_seconds())

        concept_perf = self.get_attempt_concept_performance(
            workspace_id, attempt_id, user_id
        ).concepts

        return QuizAttemptTrackingResponse(
            attempt_id=attempt.id,
            workspace_id=attempt.workspace_id,
            user_id=attempt.user_id,
            title=attempt.title,
            status=attempt.status,
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            total_duration_seconds=total_duration_sec,
            total_questions=total_q,
            answered_count=answered_c,
            unanswered_count=unanswered_c,
            correct_count=correct_c,
            incorrect_count=incorrect_c,
            score_percentage=attempt.score_percentage,
            questions=question_metrics,
            concept_performance=concept_perf,
        )

    def get_interactions_summary(
        self,
        workspace_id: uuid.UUID,
    ) -> LearningInteractionsSummaryResponse:
        """Workspace-scoped interaction event analytics summary."""
        total_events = (
            self.db.query(func.count(LearnerInteractionEvent.id))
            .filter(LearnerInteractionEvent.workspace_id == workspace_id)
            .scalar()
            or 0
        )

        type_counts = (
            self.db.query(
                LearnerInteractionEvent.event_type,
                func.count(LearnerInteractionEvent.id),
            )
            .filter(LearnerInteractionEvent.workspace_id == workspace_id)
            .group_by(LearnerInteractionEvent.event_type)
            .all()
        )
        events_by_type = {event_type: count for event_type, count in type_counts}

        active_attempts_count = (
            self.db.query(func.count(QuizAttempt.id))
            .filter(
                QuizAttempt.workspace_id == workspace_id,
                QuizAttempt.status == "in_progress",
            )
            .scalar()
            or 0
        )

        return LearningInteractionsSummaryResponse(
            workspace_id=workspace_id,
            total_events=total_events,
            events_by_type=events_by_type,
            active_attempts_count=active_attempts_count,
            total_hints_opened=events_by_type.get("hint_opened", 0),
            total_explanations_opened=events_by_type.get("explanation_opened", 0),
            total_sources_opened=events_by_type.get("source_opened", 0)
            + events_by_type.get("source_page_navigated", 0),
        )
