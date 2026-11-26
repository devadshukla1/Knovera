"""Learning Analytics Service for Knovera (Phase 9 C9.8).

Computes verified, tenant-isolated learning analytics from PostgreSQL:
- Overview KPIs (attempts, completion, average score, correct rate excluding unanswered)
- Detailed Quiz Performance & Score Trends
- Concept-Level Performance Attribution & Evidence Sufficiency
- Latent BKT Mastery Projection
- Meaningful Educational Activity Timeline
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.bkt import (
    BKTEvaluationRun,
    BKTModelVersion,
    LearnerConceptMastery,
)
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.learner_intelligence import (
    LearnerInteractionEvent,
    QuestionConceptMapping,
    RevisionRecommendation,
)
from backend.app.models.study_material import QuizAttempt, QuizAttemptAnswer
from backend.app.schemas.analytics import (
    ActivityTimelineItem,
    ActivityTimelineResponse,
    AnalyticsDateFilter,
    AnalyticsOverviewResponse,
    ConceptAnalyticsItem,
    ConceptAnalyticsResponse,
    MasteryAnalyticsItem,
    MasteryAnalyticsResponse,
    QuizPerformanceResponse,
    ScoreHistoryPoint,
    ScoreHistoryResponse,
)

logger = get_logger("knovera.services.analytics")


class LearningAnalyticsService:
    """Service providing aggregated educational intelligence and dashboard metrics."""

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Overview & KPI Summary
    # =========================================================================

    def get_overview(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        date_filter: str = "all",
    ) -> AnalyticsOverviewResponse:
        """Computes executive-level KPIs for the learning analytics dashboard."""
        since_dt = self._resolve_date_cutoff(date_filter)

        # 1. Query Attempts
        attempt_query = self.db.query(QuizAttempt).filter(
            QuizAttempt.workspace_id == workspace_id,
            QuizAttempt.user_id == user_id,
        )
        if since_dt:
            attempt_query = attempt_query.filter(QuizAttempt.created_at >= since_dt)
        attempts = attempt_query.all()

        total_attempts = len(attempts)
        completed_attempts = sum(1 for a in attempts if a.status in ["completed", "evaluated"])
        evaluated_attempts = [a for a in attempts if a.status == "evaluated"]
        evaluated_count = len(evaluated_attempts)

        avg_score = 0.0
        if evaluated_count > 0:
            total_score = sum(a.score_percentage or 0.0 for a in evaluated_attempts)
            avg_score = round(total_score / evaluated_count, 1)

        # 2. Query Answers for evaluated attempts
        eval_attempt_ids = [a.id for a in evaluated_attempts]
        total_answered = 0
        total_correct = 0
        total_incorrect = 0
        total_unanswered = 0

        if eval_attempt_ids:
            answers = (
                self.db.query(QuizAttemptAnswer)
                .filter(QuizAttemptAnswer.attempt_id.in_(eval_attempt_ids))
                .all()
            )
            for ans in answers:
                if ans.is_correct is None:
                    total_unanswered += 1
                elif ans.is_correct:
                    total_answered += 1
                    total_correct += 1
                else:
                    total_answered += 1
                    total_incorrect += 1

        overall_correct_rate = 0.0
        if total_answered > 0:
            overall_correct_rate = round((total_correct / total_answered) * 100.0, 1)

        # 3. Concepts Assessed & BKT Sufficiency
        concepts_assessed_count = 0
        sufficient_bkt_count = 0
        if eval_attempt_ids:
            concepts_assessed_query = (
                self.db.query(QuestionConceptMapping.concept_id)
                .join(QuizAttemptAnswer, QuestionConceptMapping.question_id == QuizAttemptAnswer.question_id)
                .filter(
                    QuizAttemptAnswer.attempt_id.in_(eval_attempt_ids),
                    QuizAttemptAnswer.is_correct.is_not(None),
                    QuestionConceptMapping.workspace_id == workspace_id,
                    QuestionConceptMapping.validation_status == "validated",
                )
                .distinct()
            )
            concepts_assessed_count = concepts_assessed_query.count()

        # Count concepts with >= 3 observations in learner_concept_mastery
        sufficient_bkt_count = (
            self.db.query(LearnerConceptMastery)
            .filter(
                LearnerConceptMastery.workspace_id == workspace_id,
                LearnerConceptMastery.user_id == user_id,
                LearnerConceptMastery.observation_count >= 3,
            )
            .count()
        )

        # 4. Pending Recommendations
        pending_recs = (
            self.db.query(RevisionRecommendation)
            .filter(
                RevisionRecommendation.workspace_id == workspace_id,
                RevisionRecommendation.user_id == user_id,
                RevisionRecommendation.status == "suggested",
            )
            .count()
        )

        return AnalyticsOverviewResponse(
            total_quiz_attempts=total_attempts,
            completed_attempts=completed_attempts,
            evaluated_attempts=evaluated_count,
            average_quiz_score=avg_score,
            overall_correct_rate=overall_correct_rate,
            total_questions_answered=total_answered,
            total_correct_answers=total_correct,
            total_incorrect_answers=total_incorrect,
            total_unanswered=total_unanswered,
            concepts_assessed=concepts_assessed_count,
            concepts_with_sufficient_bkt=sufficient_bkt_count,
            pending_recommendations_count=pending_recs,
            date_filter=date_filter,
        )

    # =========================================================================
    # Quiz Performance & Score Trend
    # =========================================================================

    def get_quiz_performance(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        date_filter: str = "all",
    ) -> QuizPerformanceResponse:
        """Aggregates quiz performance metrics."""
        since_dt = self._resolve_date_cutoff(date_filter)
        query = self.db.query(QuizAttempt).filter(
            QuizAttempt.workspace_id == workspace_id,
            QuizAttempt.user_id == user_id,
            QuizAttempt.status == "evaluated",
        )
        if since_dt:
            query = query.filter(QuizAttempt.created_at >= since_dt)

        attempts = query.order_by(QuizAttempt.submitted_at.desc(), QuizAttempt.created_at.desc()).all()
        total_attempts = len(attempts)

        if total_attempts == 0:
            return QuizPerformanceResponse(
                total_attempts=0,
                average_score=0.0,
                highest_score=0.0,
                recent_score=None,
                recent_attempt_id=None,
                recent_attempt_date=None,
                total_answered=0,
                total_correct=0,
                total_incorrect=0,
                total_unanswered=0,
                correct_rate=0.0,
            )

        scores = [a.score_percentage or 0.0 for a in attempts]
        avg_score = round(sum(scores) / total_attempts, 1)
        highest_score = round(max(scores), 1)
        recent_attempt = attempts[0]
        recent_score = round(recent_attempt.score_percentage or 0.0, 1)
        recent_date = recent_attempt.submitted_at or recent_attempt.created_at

        # Compute answers distribution
        eval_ids = [a.id for a in attempts]
        answers = (
            self.db.query(QuizAttemptAnswer)
            .filter(QuizAttemptAnswer.attempt_id.in_(eval_ids))
            .all()
        )
        total_answered = 0
        total_correct = 0
        total_incorrect = 0
        total_unanswered = 0
        for ans in answers:
            if ans.is_correct is None:
                total_unanswered += 1
            elif ans.is_correct:
                total_answered += 1
                total_correct += 1
            else:
                total_answered += 1
                total_incorrect += 1

        correct_rate = round((total_correct / total_answered * 100.0), 1) if total_answered > 0 else 0.0

        return QuizPerformanceResponse(
            total_attempts=total_attempts,
            average_score=avg_score,
            highest_score=highest_score,
            recent_score=recent_score,
            recent_attempt_id=recent_attempt.id,
            recent_attempt_date=recent_date,
            total_answered=total_answered,
            total_correct=total_correct,
            total_incorrect=total_incorrect,
            total_unanswered=total_unanswered,
            correct_rate=correct_rate,
        )

    def get_score_history(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        date_filter: str = "all",
    ) -> ScoreHistoryResponse:
        """Returns chronological series of evaluated quiz attempts for trend visualization."""
        since_dt = self._resolve_date_cutoff(date_filter)
        query = self.db.query(QuizAttempt).filter(
            QuizAttempt.workspace_id == workspace_id,
            QuizAttempt.user_id == user_id,
            QuizAttempt.status == "evaluated",
        )
        if since_dt:
            query = query.filter(QuizAttempt.created_at >= since_dt)

        attempts = query.order_by(
            func.coalesce(QuizAttempt.submitted_at, QuizAttempt.created_at).asc()
        ).all()

        points: List[ScoreHistoryPoint] = []
        for a in attempts:
            tstamp = a.submitted_at or a.created_at
            score_val = round(a.score_percentage or 0.0, 1)
            points.append(
                ScoreHistoryPoint(
                    attempt_id=a.id,
                    attempt_date=tstamp,
                    score_percentage=score_val,
                    passed=(score_val >= 70.0),
                    total_questions=a.total_questions or (len(a.answers) if hasattr(a, "answers") else 0),
                    correct_count=a.correct_answers_count or 0,
                )
            )

        return ScoreHistoryResponse(
            points=points,
            total_points=len(points),
        )

    # =========================================================================
    # Concept-Level Performance & Mastery
    # =========================================================================

    def get_concept_analytics(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        date_filter: str = "all",
    ) -> ConceptAnalyticsResponse:
        """Aggregates question-level accuracy and BKT mastery for each canonical concept."""
        since_dt = self._resolve_date_cutoff(date_filter)

        # 1. Fetch concepts in workspace
        concepts = (
            self.db.query(KnowledgeNode)
            .filter(KnowledgeNode.workspace_id == workspace_id)
            .order_by(KnowledgeNode.name.asc())
            .all()
        )

        # 2. Query evaluated answers mapped to concepts
        query = (
            self.db.query(
                QuestionConceptMapping.concept_id,
                QuizAttemptAnswer.is_correct,
                func.coalesce(QuizAttempt.submitted_at, QuizAttemptAnswer.created_at).label("ans_date"),
            )
            .join(QuizAttempt, QuizAttemptAnswer.attempt_id == QuizAttempt.id)
            .join(
                QuestionConceptMapping,
                (QuestionConceptMapping.question_id == QuizAttemptAnswer.question_id)
                & (QuestionConceptMapping.workspace_id == workspace_id),
            )
            .filter(
                QuizAttempt.workspace_id == workspace_id,
                QuizAttempt.user_id == user_id,
                QuizAttempt.status == "evaluated",
                QuestionConceptMapping.validation_status == "validated",
            )
        )
        if since_dt:
            query = query.filter(QuizAttempt.created_at >= since_dt)

        records = query.all()

        concept_stats: Dict[uuid.UUID, Dict[str, Any]] = defaultdict(
            lambda: {
                "attempted": 0,
                "answered": 0,
                "correct": 0,
                "incorrect": 0,
                "unanswered": 0,
                "last_activity": None,
            }
        )

        for cid, is_corr, ans_date in records:
            c = concept_stats[cid]
            c["attempted"] += 1
            if is_corr is None:
                c["unanswered"] += 1
            elif is_corr:
                c["answered"] += 1
                c["correct"] += 1
            else:
                c["answered"] += 1
                c["incorrect"] += 1

            if ans_date:
                if c["last_activity"] is None or ans_date > c["last_activity"]:
                    c["last_activity"] = ans_date

        # 3. Fetch BKT mastery states
        mastery_map: Dict[uuid.UUID, LearnerConceptMastery] = {
            m.concept_id: m
            for m in self.db.query(LearnerConceptMastery)
            .filter(
                LearnerConceptMastery.workspace_id == workspace_id,
                LearnerConceptMastery.user_id == user_id,
            )
            .all()
        }

        items: List[ConceptAnalyticsItem] = []
        for concept in concepts:
            cid = concept.id
            stats = concept_stats.get(cid, {
                "attempted": 0,
                "answered": 0,
                "correct": 0,
                "incorrect": 0,
                "unanswered": 0,
                "last_activity": None,
            })
            mastery = mastery_map.get(cid)

            obs_count = mastery.observation_count if mastery else stats["answered"]
            if obs_count >= 3:
                sufficiency = "sufficient"
            elif obs_count >= 1:
                sufficiency = "sparse"
            else:
                sufficiency = "unobserved"

            rate = round((stats["correct"] / stats["answered"]) * 100.0, 1) if stats["answered"] > 0 else 0.0

            items.append(
                ConceptAnalyticsItem(
                    concept_id=cid,
                    concept_name=concept.name,
                    category=concept.category,
                    questions_attempted=stats["attempted"],
                    questions_answered=stats["answered"],
                    correct_answers=stats["correct"],
                    incorrect_answers=stats["incorrect"],
                    unanswered=stats["unanswered"],
                    correct_rate=rate,
                    evidence_sufficiency=sufficiency,
                    bkt_mastery_probability=round(mastery.posterior_mastery_probability, 4) if mastery else None,
                    bkt_status=mastery.status if mastery else "insufficient_data",
                    last_activity_at=stats["last_activity"] or (mastery.last_updated_at if mastery else None),
                )
            )

        # Sort: Concepts with activity first, then by lowest correct rate
        items.sort(key=lambda x: (x.questions_attempted == 0, x.correct_rate))

        return ConceptAnalyticsResponse(
            concepts=items,
            total_count=len(items),
        )

    def get_mastery_overview(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MasteryAnalyticsResponse:
        """Returns BKT mastery projections with explicit model validation gating status."""
        active_model = (
            self.db.query(BKTModelVersion)
            .filter(
                BKTModelVersion.workspace_id == workspace_id,
                BKTModelVersion.status == "active",
            )
            .order_by(BKTModelVersion.created_at.desc())
            .first()
        )

        readiness_status = "not_evaluated"
        is_validated = False
        if active_model:
            eval_run = (
                self.db.query(BKTEvaluationRun)
                .filter(
                    BKTEvaluationRun.model_version_id == active_model.id,
                    BKTEvaluationRun.readiness_status == "evaluation_passed",
                )
                .first()
            )
            if eval_run:
                readiness_status = "evaluation_passed"
                is_validated = True
            else:
                readiness_status = "candidate_experimental"

        masteries = (
            self.db.query(LearnerConceptMastery)
            .filter(
                LearnerConceptMastery.workspace_id == workspace_id,
                LearnerConceptMastery.user_id == user_id,
            )
            .order_by(LearnerConceptMastery.posterior_mastery_probability.asc())
            .all()
        )

        items: List[MasteryAnalyticsItem] = []
        for m in masteries:
            cname = m.concept.name if m.concept else "Unknown Concept"
            ccat = m.concept.category if m.concept else None
            items.append(
                MasteryAnalyticsItem(
                    concept_id=m.concept_id,
                    concept_name=cname,
                    category=ccat,
                    prior_mastery=round(m.posterior_mastery_probability, 4),  # previous step
                    posterior_mastery=round(m.posterior_mastery_probability, 4),
                    predicted_next_mastery=round(m.predicted_next_mastery_probability, 4),
                    observation_count=m.observation_count,
                    correct_count=m.observation_count - (0 if m.last_observation_correct else 1),
                    bkt_status=m.status,
                    model_version=active_model.model_version if active_model else "default-baseline",
                    is_model_validated=is_validated,
                    last_updated_at=m.last_updated_at,
                )
            )

        return MasteryAnalyticsResponse(
            masteries=items,
            total_concepts_tracked=len(items),
            model_readiness_status=readiness_status,
            active_model_version=active_model.model_version if active_model else None,
        )

    # =========================================================================
    # Activity Timeline
    # =========================================================================

    def get_activity_timeline(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 30,
    ) -> ActivityTimelineResponse:
        """Retrieves chronological timeline of educationally meaningful interaction events."""
        meaningful_events = [
            "quiz_submitted",
            "quiz_resumed",
            "answer_selected",
            "answer_revised",
            "hint_opened",
            "explanation_opened",
            "study_note_viewed",
            "flashcard_flipped",
        ]

        events = (
            self.db.query(LearnerInteractionEvent)
            .filter(
                LearnerInteractionEvent.workspace_id == workspace_id,
                LearnerInteractionEvent.user_id == user_id,
                LearnerInteractionEvent.event_type.in_(meaningful_events),
            )
            .order_by(LearnerInteractionEvent.occurred_at.desc())
            .limit(limit)
            .all()
        )

        items: List[ActivityTimelineItem] = []
        for ev in events:
            title, desc = self._format_event_description(ev)
            cname = None
            if ev.concept_id:
                concept = self.db.query(KnowledgeNode).filter(KnowledgeNode.id == ev.concept_id).first()
                if concept:
                    cname = concept.name

            items.append(
                ActivityTimelineItem(
                    event_id=ev.id,
                    event_type=ev.event_type,
                    occurred_at=ev.occurred_at,
                    title=title,
                    description=desc,
                    concept_id=ev.concept_id,
                    concept_name=cname,
                    attempt_id=ev.attempt_id,
                    metadata=ev.event_metadata or {},
                )
            )

        return ActivityTimelineResponse(
            events=items,
            total_events=len(items),
        )

    # =========================================================================
    # Helpers
    # =========================================================================

    def _resolve_date_cutoff(self, date_filter: str) -> Optional[datetime]:
        """Maps filter string to UTC datetime cutoff."""
        now = datetime.now(timezone.utc)
        filter_norm = (date_filter or "all").lower()
        if filter_norm == "7d":
            return now - timedelta(days=7)
        elif filter_norm == "30d":
            return now - timedelta(days=30)
        elif filter_norm == "90d":
            return now - timedelta(days=90)
        return None

    def _format_event_description(self, ev: LearnerInteractionEvent) -> Tuple[str, str]:
        """Produces clean human-readable titles and descriptions for educational events."""
        etype = ev.event_type
        meta = ev.event_metadata or {}

        if etype == "quiz_submitted":
            score = meta.get("score_percentage")
            title = "Completed Quiz Assessment"
            desc = f"Submitted quiz attempt with score {score:.1f}%." if score is not None else "Submitted quiz assessment."
        elif etype == "hint_opened":
            title = "Opened Question Hint"
            desc = "Consulted conceptual hint during quiz practice."
        elif etype == "explanation_opened":
            title = "Inspected Source Explanation"
            desc = "Reviewed source-grounded explanation for answer rationale."
        elif etype == "answer_selected":
            title = "Submitted Question Answer"
            desc = "Recorded answer option for evaluation."
        elif etype == "answer_revised":
            title = "Revised Answer Selection"
            desc = "Modified selected answer prior to quiz submission."
        elif etype == "study_note_viewed":
            title = "Reviewed Revision Note"
            desc = "Engaged with structured conceptual study notes."
        elif etype == "flashcard_flipped":
            title = "Practiced Flashcard"
            desc = "Reviewed active-recall flashcard prompt and answer."
        else:
            title = etype.replace("_", " ").title()
            desc = f"Learner interaction recorded."

        return title, desc
