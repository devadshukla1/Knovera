"""Revision Recommendation Service for Knovera (Phase 9 C9.7).

Provides explainable, actionable revision recommendations using:
- Validated BKT mastery estimates (when active model is verified and qualified)
- Descriptive quiz evidence (when BKT is unvalidated or unavailable)
- Evidence sufficiency rules (distinguishing sparse observations from poor mastery)
- Material-to-concept linking (connecting concepts to revision notes, flashcards, questions, and sources)
- Full lifecycle tracking (suggested -> viewed -> started -> completed -> dismissed)
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.bkt import (
    BKTEvaluationRun,
    BKTModelVersion,
    LearnerConceptMastery,
)
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_mention import KnowledgeMention
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.learner_intelligence import (
    QuestionConceptMapping,
    RevisionRecommendation,
)
from backend.app.models.study_material import (
    FillBlankExercise,
    Flashcard,
    MCQQuestion,
    QuizAttempt,
    QuizAttemptAnswer,
    RevisionNote,
    TrueFalseQuestion,
)
from backend.app.schemas.recommendation import (
    ConceptRevisionResourcesResponse,
    RecommendationPriority,
    RecommendationStatus,
    RecommendationType,
    RevisionRecommendationGenerateRequest,
    RevisionRecommendationResponse,
    RevisionRecommendationStatusUpdate,
)

logger = get_logger("knovera.services.recommendation")


class RevisionRecommendationService:
    """Service generating, updating, and serving explainable revision recommendations."""

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Recommendation Generation (C9.7)
    # =========================================================================

    def generate_recommendations(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        req: Optional[RevisionRecommendationGenerateRequest] = None,
    ) -> List[RevisionRecommendation]:
        """Generates deterministic, explainable revision recommendations for a learner."""
        if req is None:
            req = RevisionRecommendationGenerateRequest()
        # 1. Check active BKT model qualification status in workspace
        active_model, is_bkt_qualified = self._get_active_model_and_qualification(workspace_id)

        # 2. Load learner concept masteries
        mastery_map: Dict[uuid.UUID, LearnerConceptMastery] = {
            m.concept_id: m
            for m in self.db.query(LearnerConceptMastery)
            .filter(
                LearnerConceptMastery.workspace_id == workspace_id,
                LearnerConceptMastery.user_id == user_id,
            )
            .all()
        }

        # 3. Load concept-level quiz performance attribution
        performance_map = self._compute_learner_concept_performance(workspace_id, user_id)

        # 4. Fetch all canonical concepts present in workspace
        concepts = (
            self.db.query(KnowledgeNode)
            .filter(KnowledgeNode.workspace_id == workspace_id)
            .all()
        )

        candidates: List[Dict[str, Any]] = []

        for concept in concepts:
            cid = concept.id
            perf = performance_map.get(cid, {
                "questions_attempted": 0,
                "questions_answered": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "unanswered": 0,
                "correct_rate": 0.0,
            })
            mastery = mastery_map.get(cid)

            obs_count = mastery.observation_count if mastery else perf["questions_answered"]
            post_mastery = mastery.posterior_mastery_probability if mastery else None

            # Evidence Sufficiency Rule
            is_sufficient = obs_count >= 3
            is_unobserved = obs_count == 0

            # Policy Decision
            rec_type, priority, explanation = self._apply_recommendation_policy(
                concept_name=concept.name,
                is_bkt_qualified=is_bkt_qualified,
                posterior_mastery=post_mastery,
                obs_count=obs_count,
                perf=perf,
                is_sufficient=is_sufficient,
                is_unobserved=is_unobserved,
            )

            # Skip concepts that need no action unless user has very few recommendations
            if rec_type == RecommendationType.NO_ACTION_NEEDED:
                continue

            # Link available study materials
            linked = self._resolve_learning_materials(workspace_id, cid, concept.name)

            evidence_summary = {
                "observation_count": obs_count,
                "evidence_sufficiency": "sufficient" if is_sufficient else ("sparse" if not is_unobserved else "unobserved"),
                "questions_answered": perf["questions_answered"],
                "correct_answers": perf["correct_answers"],
                "incorrect_answers": perf["incorrect_answers"],
                "correct_rate": perf["correct_rate"],
                "bkt_posterior_mastery": post_mastery,
                "bkt_model_qualified": is_bkt_qualified,
                "bkt_status": mastery.status if mastery else "insufficient_data",
            }

            # Numeric ranking score for sorting: High priority first, then lowest mastery/accuracy
            priority_weight = 3 if priority == RecommendationPriority.HIGH else (2 if priority == RecommendationPriority.MEDIUM else 1)
            rank_score = (priority_weight * 100.0) - (post_mastery * 50.0 if post_mastery is not None else (perf["correct_rate"] / 2.0))

            candidates.append({
                "concept_id": cid,
                "concept_name": concept.name,
                "concept_description": concept.description,
                "recommendation_type": rec_type,
                "priority": priority,
                "explanation": explanation,
                "evidence_summary": evidence_summary,
                "linked_resources": linked,
                "model_version_id": active_model.id if active_model else None,
                "rank_score": rank_score,
            })

        # Sort candidates deterministically by priority rank score descending
        candidates.sort(key=lambda c: c["rank_score"], reverse=True)
        top_candidates = candidates[: req.max_recommendations]

        # 5. Idempotent persistence: Update or insert recommendations
        if req.force_regenerate:
            # Mark existing suggested recommendations as expired
            self.db.query(RevisionRecommendation).filter(
                RevisionRecommendation.workspace_id == workspace_id,
                RevisionRecommendation.user_id == user_id,
                RevisionRecommendation.status == "suggested",
            ).update({"status": "expired"})

        persisted: List[RevisionRecommendation] = []
        for cand in top_candidates:
            existing = (
                self.db.query(RevisionRecommendation)
                .filter(
                    RevisionRecommendation.workspace_id == workspace_id,
                    RevisionRecommendation.user_id == user_id,
                    RevisionRecommendation.concept_id == cand["concept_id"],
                    RevisionRecommendation.status.in_(["suggested", "viewed", "started"]),
                )
                .first()
            )
            if existing:
                existing.recommendation_type = cand["recommendation_type"].value
                existing.priority = cand["priority"].value
                existing.explanation = cand["explanation"]
                existing.evidence_summary = cand["evidence_summary"]
                existing.linked_resources = cand["linked_resources"]
                existing.model_version_id = cand["model_version_id"]
                persisted.append(existing)
            else:
                new_rec = RevisionRecommendation(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    concept_id=cand["concept_id"],
                    recommendation_type=cand["recommendation_type"].value,
                    priority=cand["priority"].value,
                    explanation=cand["explanation"],
                    evidence_summary=cand["evidence_summary"],
                    linked_resources=cand["linked_resources"],
                    model_version_id=cand["model_version_id"],
                    status="suggested",
                )
                self.db.add(new_rec)
                persisted.append(new_rec)

        self.db.commit()
        for rec in persisted:
            self.db.refresh(rec)

        return persisted

    # =========================================================================
    # Recommendation Retrieval & Updates
    # =========================================================================

    def list_recommendations(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        priority: Optional[str] = None,
        rec_type: Optional[str] = None,
        rec_status: Optional[str] = None,
    ) -> List[RevisionRecommendation]:
        """Lists revision recommendations for the authenticated learner."""
        query = (
            self.db.query(RevisionRecommendation)
            .filter(
                RevisionRecommendation.workspace_id == workspace_id,
                RevisionRecommendation.user_id == user_id,
            )
        )
        if priority:
            query = query.filter(RevisionRecommendation.priority == priority)
        if rec_type:
            query = query.filter(RevisionRecommendation.recommendation_type == rec_type)
        if rec_status:
            query = query.filter(RevisionRecommendation.status == rec_status)
        else:
            # By default exclude expired and dismissed
            query = query.filter(RevisionRecommendation.status.in_(["suggested", "viewed", "started"]))

        return query.order_by(
            RevisionRecommendation.priority.desc(),
            RevisionRecommendation.created_at.desc(),
        ).all()

    def get_recommendation(
        self,
        workspace_id: uuid.UUID,
        recommendation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> RevisionRecommendation:
        """Retrieves a single recommendation ensuring workspace and user tenancy."""
        rec = (
            self.db.query(RevisionRecommendation)
            .filter(
                RevisionRecommendation.id == recommendation_id,
                RevisionRecommendation.workspace_id == workspace_id,
            )
            .first()
        )
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation {recommendation_id} not found.",
            )
        if rec.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access recommendation belonging to another user.",
            )
        return rec

    def update_recommendation_status(
        self,
        workspace_id: uuid.UUID,
        recommendation_id: uuid.UUID,
        user_id: uuid.UUID,
        update: RevisionRecommendationStatusUpdate,
    ) -> RevisionRecommendation:
        """Updates lifecycle status of a recommendation."""
        rec = self.get_recommendation(workspace_id, recommendation_id, user_id)
        rec.status = update.status.value
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def get_concept_revision_resources(
        self,
        workspace_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> ConceptRevisionResourcesResponse:
        """Resolves all available study materials for a specific canonical concept."""
        concept = (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.id == concept_id,
                KnowledgeNode.workspace_id == workspace_id,
            )
            .first()
        )
        if not concept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Concept {concept_id} not found in workspace.",
            )

        linked = self._resolve_learning_materials(workspace_id, concept_id, concept.name)

        return ConceptRevisionResourcesResponse(
            concept_id=concept.id,
            concept_name=concept.name,
            revision_notes=linked.get("revision_notes", []),
            flashcards=linked.get("flashcards", []),
            practice_questions=linked.get("practice_questions", []),
            source_documents=linked.get("source_chunks", []),
        )

    # =========================================================================
    # Internal Helpers: Readiness, Attributions, Policy & Material Resolution
    # =========================================================================

    def _get_active_model_and_qualification(
        self,
        workspace_id: uuid.UUID,
    ) -> Tuple[Optional[BKTModelVersion], bool]:
        """Resolves active BKT model and checks whether it passed offline evaluation gates."""
        active_model = (
            self.db.query(BKTModelVersion)
            .filter(
                BKTModelVersion.workspace_id == workspace_id,
                BKTModelVersion.status == "active",
            )
            .order_by(BKTModelVersion.created_at.desc())
            .first()
        )
        if not active_model:
            return None, False

        # Verify offline evaluation readiness
        eval_run = (
            self.db.query(BKTEvaluationRun)
            .filter(
                BKTEvaluationRun.model_version_id == active_model.id,
                BKTEvaluationRun.readiness_status == "evaluation_passed",
            )
            .order_by(BKTEvaluationRun.created_at.desc())
            .first()
        )
        is_qualified = eval_run is not None
        return active_model, is_qualified

    def _compute_learner_concept_performance(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Dict[uuid.UUID, Dict[str, Any]]:
        """Aggregates evaluated answers across canonical concepts."""
        records = (
            self.db.query(
                QuestionConceptMapping.concept_id,
                QuizAttemptAnswer.is_correct,
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
            .all()
        )

        perf_map: Dict[uuid.UUID, Dict[str, Any]] = defaultdict(
            lambda: {
                "questions_attempted": 0,
                "questions_answered": 0,
                "correct_answers": 0,
                "incorrect_answers": 0,
                "unanswered": 0,
                "correct_rate": 0.0,
            }
        )

        for cid, is_corr in records:
            p = perf_map[cid]
            p["questions_attempted"] += 1
            if is_corr is None:
                p["unanswered"] += 1
            elif is_corr:
                p["questions_answered"] += 1
                p["correct_answers"] += 1
            else:
                p["questions_answered"] += 1
                p["incorrect_answers"] += 1

        for p in perf_map.values():
            if p["questions_answered"] > 0:
                p["correct_rate"] = round((p["correct_answers"] / p["questions_answered"]) * 100.0, 1)
            else:
                p["correct_rate"] = 0.0

        return perf_map

    def _apply_recommendation_policy(
        self,
        concept_name: str,
        is_bkt_qualified: bool,
        posterior_mastery: Optional[float],
        obs_count: int,
        perf: Dict[str, Any],
        is_sufficient: bool,
        is_unobserved: bool,
    ) -> Tuple[RecommendationType, RecommendationPriority, str]:
        """Applies transparent, explainable recommendation policy."""
        # 1. Unobserved concept
        if is_unobserved:
            return (
                RecommendationType.INSUFFICIENT_EVIDENCE,
                RecommendationPriority.LOW,
                f"No evaluated practice questions have been completed for '{concept_name}'. Try introductory questions to build initial learning evidence.",
            )

        # 2. Sparse observations (< 3)
        if not is_sufficient:
            return (
                RecommendationType.PRACTICE_CONCEPT,
                RecommendationPriority.MEDIUM,
                f"You have completed {obs_count} question(s) on '{concept_name}'. Additional practice is needed to evaluate your mastery reliably.",
            )

        # 3. Sufficient observations with Qualified BKT Model
        if is_bkt_qualified and posterior_mastery is not None:
            if posterior_mastery < 0.40:
                return (
                    RecommendationType.REVISE_CONCEPT,
                    RecommendationPriority.HIGH,
                    f"Estimated BKT mastery for '{concept_name}' is currently low (P={posterior_mastery:.2f}). Review key definitions and source material to bridge knowledge gaps.",
                )
            elif posterior_mastery < 0.70 or perf["incorrect_answers"] >= 2:
                return (
                    RecommendationType.PRACTICE_CONCEPT,
                    RecommendationPriority.MEDIUM,
                    f"Knowledge of '{concept_name}' is developing (P={posterior_mastery:.2f}), but recent errors suggest targeted practice will reinforce understanding.",
                )
            else:
                return (
                    RecommendationType.REINFORCE_CONCEPT,
                    RecommendationPriority.LOW,
                    f"Strong estimated mastery of '{concept_name}' (P={posterior_mastery:.2f}). Light reinforcement with flashcards is recommended.",
                )

        # 4. Fallback to descriptive quiz evidence (when BKT model is not qualified or unavailable)
        correct_rate = perf["correct_rate"]
        incorrect = perf["incorrect_answers"]

        if correct_rate < 50.0 or incorrect >= 3:
            return (
                RecommendationType.REVISE_CONCEPT,
                RecommendationPriority.HIGH,
                f"Observed quiz accuracy on '{concept_name}' is {correct_rate:.1f}% ({perf['correct_answers']}/{perf['questions_answered']} correct). We recommend revising concept notes and reading source material.",
            )
        elif correct_rate < 75.0:
            return (
                RecommendationType.PRACTICE_CONCEPT,
                RecommendationPriority.MEDIUM,
                f"Observed quiz accuracy on '{concept_name}' is {correct_rate:.1f}%. Practicing additional questions will help build consistent recall.",
            )
        else:
            return (
                RecommendationType.REINFORCE_CONCEPT,
                RecommendationPriority.LOW,
                f"Demonstrating {correct_rate:.1f}% accuracy on '{concept_name}'. Practice flashcards periodically to maintain long-term retention.",
            )

    def _resolve_learning_materials(
        self,
        workspace_id: uuid.UUID,
        concept_id: uuid.UUID,
        concept_name: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Discovers existing revision notes, flashcards, questions, and sources for a concept."""
        # 1. Revision Notes
        notes = (
            self.db.query(RevisionNote)
            .filter(RevisionNote.workspace_id == workspace_id)
            .limit(5)
            .all()
        )
        matched_notes = []
        name_lower = concept_name.lower()
        for note in notes:
            kcs = [str(k).lower() for k in (note.key_concepts or [])]
            if name_lower in note.title.lower() or any(name_lower in k for k in kcs):
                overview_text = getattr(note, "overview", None) or getattr(note, "summary", "")
                matched_notes.append({
                    "resource_type": "revision_note",
                    "resource_id": str(note.id),
                    "title": note.title,
                    "preview": overview_text[:200] if overview_text else None,
                    "document_id": str(getattr(note, "document_id", None)) if getattr(note, "document_id", None) else None,
                })

        # 2. Flashcards
        flashcards = (
            self.db.query(Flashcard)
            .filter(Flashcard.workspace_id == workspace_id)
            .limit(10)
            .all()
        )
        matched_fc = []
        for fc in flashcards:
            f_front = getattr(fc, "front", None) or getattr(fc, "front_prompt", "") or ""
            f_back = getattr(fc, "back", None) or getattr(fc, "back_answer", "") or ""
            if name_lower in f_front.lower() or name_lower in f_back.lower():
                matched_fc.append({
                    "resource_type": "flashcard",
                    "resource_id": str(fc.id),
                    "title": f_front[:120],
                    "preview": f_back[:200],
                })

        # 3. Practice Questions via QuestionConceptMapping
        mappings = (
            self.db.query(QuestionConceptMapping)
            .filter(
                QuestionConceptMapping.workspace_id == workspace_id,
                QuestionConceptMapping.concept_id == concept_id,
                QuestionConceptMapping.validation_status == "validated",
            )
            .limit(10)
            .all()
        )
        matched_questions = []
        for m in mappings:
            matched_questions.append({
                "resource_type": "question",
                "resource_id": str(m.question_id),
                "title": f"Practice {m.question_type.upper()}",
                "preview": m.evidence_excerpt[:200] if m.evidence_excerpt else None,
            })

        # 4. Source Chunks via KnowledgeMention
        mentions = (
            self.db.query(KnowledgeMention)
            .filter(KnowledgeMention.node_id == concept_id)
            .limit(5)
            .all()
        )
        matched_chunks = []
        for men in mentions:
            chunk = (
                self.db.query(DocumentChunk)
                .filter(DocumentChunk.id == men.chunk_id)
                .first()
            )
            if chunk:
                chunk_text = getattr(chunk, "content", None) or getattr(chunk, "text", "")
                matched_chunks.append({
                    "resource_type": "document_chunk",
                    "resource_id": str(chunk.id),
                    "title": f"Source Chunk (Page {getattr(chunk, 'page_start', 1) or 1})",
                    "preview": chunk_text[:200] if chunk_text else None,
                    "document_id": str(chunk.document_id),
                    "page_number": getattr(chunk, "page_start", 1) or 1,
                })

        return {
            "revision_notes": matched_notes,
            "flashcards": matched_fc,
            "practice_questions": matched_questions,
            "source_chunks": matched_chunks,
        }


# Alias
RecommendationService = RevisionRecommendationService

