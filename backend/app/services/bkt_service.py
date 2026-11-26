"""Bayesian Knowledge Tracing Service (Phase 9 Chunks C9.4, C9.5, C9.6).

Orchestrates:
- C9.4: Probabilistic BKT inference with standard 4 parameters
- C9.5: Historical observation sequence extraction & Baum-Welch EM parameter fitting
- C9.6: Online mastery updates upon quiz evaluation, concurrency locking, and idempotency
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.ml.bkt.estimation import BKTEstimationResult, BKTParameterEstimator
from backend.app.ml.bkt.evaluation import (
    BKTEvaluationDataset,
    BKTEvaluationEngine,
    ObservationStep,
)
from backend.app.ml.bkt.inference import (
    DEFAULT_BKT_PARAMETERS,
    BKTParameters,
    BayesianKnowledgeTracer,
)
from backend.app.models.bkt import (
    BKTEstimationRun,
    BKTEvaluationRun,
    BKTModelVersion,
    LearnerConceptMastery,
    LearnerConceptMasteryHistory,
)
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.learner_intelligence import QuestionConceptMapping
from backend.app.models.study_material import QuizAttempt, QuizAttemptAnswer
from backend.app.schemas.bkt import (
    BKTEstimationRunCreate,
    BKTEvaluationRunCreate,
    BKTModelRollbackRequest,
    BKTModelScope,
    BKTSplitMethod,
    LearnerConceptMasteryHistoryResponse,
    LearnerConceptMasteryResponse,
    LearnerMasteryStatus,
    LearnerMasterySummaryResponse,
)

logger = get_logger("knovera.services.bkt")


class BKTService:
    """Service handling BKT parameter estimation, model versions, and live mastery updates."""

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Model Resolution & Registry (C9.5)
    # =========================================================================

    def resolve_active_parameters(
        self,
        workspace_id: uuid.UUID,
        concept_id: Optional[uuid.UUID] = None,
    ) -> Tuple[BKTParameters, Optional[BKTModelVersion]]:
        """Resolves active BKT parameters following the hierarchical fallback rule:

        1. Concept-specific active model
        2. Workspace global active model
        3. System baseline default (DEFAULT_BKT_PARAMETERS)
        """
        # 1. Concept-specific model
        if concept_id:
            concept_model = (
                self.db.query(BKTModelVersion)
                .filter(
                    BKTModelVersion.workspace_id == workspace_id,
                    BKTModelVersion.concept_id == concept_id,
                    BKTModelVersion.status == "active",
                )
                .order_by(BKTModelVersion.created_at.desc())
                .first()
            )
            if concept_model:
                params = BKTParameters(
                    p_init=concept_model.p_init,
                    p_transit=concept_model.p_transit,
                    p_guess=concept_model.p_guess,
                    p_slip=concept_model.p_slip,
                    version=concept_model.model_version,
                )
                return params, concept_model

        # 2. Workspace global model
        global_model = (
            self.db.query(BKTModelVersion)
            .filter(
                BKTModelVersion.workspace_id == workspace_id,
                BKTModelVersion.model_scope == "global",
                BKTModelVersion.status == "active",
            )
            .order_by(BKTModelVersion.created_at.desc())
            .first()
        )
        if global_model:
            params = BKTParameters(
                p_init=global_model.p_init,
                p_transit=global_model.p_transit,
                p_guess=global_model.p_guess,
                p_slip=global_model.p_slip,
                version=global_model.model_version,
            )
            return params, global_model

        # 3. Defensible baseline fallback
        return DEFAULT_BKT_PARAMETERS, None

    def list_model_versions(
        self,
        workspace_id: uuid.UUID,
        scope: Optional[str] = None,
        concept_id: Optional[uuid.UUID] = None,
    ) -> List[BKTModelVersion]:
        """Lists persisted BKT model versions in a workspace."""
        query = self.db.query(BKTModelVersion).filter(
            (BKTModelVersion.workspace_id == workspace_id) | (BKTModelVersion.workspace_id.is_(None))
        )
        if scope:
            query = query.filter(BKTModelVersion.model_scope == scope)
        if concept_id:
            query = query.filter(BKTModelVersion.concept_id == concept_id)

        return query.order_by(BKTModelVersion.created_at.desc()).all()

    def activate_model_version(
        self,
        workspace_id: uuid.UUID,
        model_version_id: uuid.UUID,
        force: bool = False,
    ) -> BKTModelVersion:
        """Promotes a candidate/evaluated BKT model version to active, archiving the prior active version.

        Enforces model readiness gate: Models that failed statistical evaluation cannot be promoted unless force=True.
        """
        target_model = (
            self.db.query(BKTModelVersion)
            .filter(
                BKTModelVersion.id == model_version_id,
                BKTModelVersion.workspace_id == workspace_id,
            )
            .first()
        )
        if not target_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"BKT model version {model_version_id} not found in workspace.",
            )

        # Check offline evaluation readiness gate (C9.9)
        failed_eval = (
            self.db.query(BKTEvaluationRun)
            .filter(
                BKTEvaluationRun.model_version_id == model_version_id,
                BKTEvaluationRun.readiness_status == "evaluation_failed",
            )
            .order_by(BKTEvaluationRun.created_at.desc())
            .first()
        )
        if failed_eval and not force:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot activate BKT model version {target_model.model_version}: "
                    f"model failed statistical evaluation gates ({failed_eval.readiness_notes})."
                ),
            )

        # Archive currently active model of the same scope and concept
        active_query = self.db.query(BKTModelVersion).filter(
            BKTModelVersion.workspace_id == workspace_id,
            BKTModelVersion.model_scope == target_model.model_scope,
            BKTModelVersion.status == "active",
        )
        if target_model.concept_id:
            active_query = active_query.filter(BKTModelVersion.concept_id == target_model.concept_id)
        else:
            active_query = active_query.filter(BKTModelVersion.concept_id.is_(None))

        current_active = active_query.all()
        for m in current_active:
            m.status = "archived"

        target_model.status = "active"
        self.db.commit()
        self.db.refresh(target_model)
        return target_model

    def rollback_model_version(
        self,
        workspace_id: uuid.UUID,
        req: BKTModelRollbackRequest,
    ) -> BKTModelVersion:
        """Rolls back from the active model version to a previous or specified archived version (C9.9)."""
        current_active = (
            self.db.query(BKTModelVersion)
            .filter(
                BKTModelVersion.workspace_id == workspace_id,
                BKTModelVersion.status == "active",
            )
            .order_by(BKTModelVersion.created_at.desc())
            .first()
        )

        if req.target_version_id:
            target_model = (
                self.db.query(BKTModelVersion)
                .filter(
                    BKTModelVersion.id == req.target_version_id,
                    BKTModelVersion.workspace_id == workspace_id,
                )
                .first()
            )
            if not target_model:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Rollback target model version {req.target_version_id} not found.",
                )
        else:
            # Find the most recently archived model version
            target_model = (
                self.db.query(BKTModelVersion)
                .filter(
                    BKTModelVersion.workspace_id == workspace_id,
                    BKTModelVersion.status == "archived",
                )
                .order_by(BKTModelVersion.updated_at.desc())
                .first()
            )
            if not target_model:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No previous archived BKT model version available to rollback to.",
                )

        if current_active:
            current_active.status = "archived"

        target_model.status = "active"
        self.db.commit()
        self.db.refresh(target_model)
        return target_model

    # =========================================================================
    # Offline Model Evaluation & Validation (C9.9)
    # =========================================================================

    def extract_evaluation_steps(
        self,
        workspace_id: uuid.UUID,
        concept_id: Optional[uuid.UUID] = None,
    ) -> List[List[ObservationStep]]:
        """Extracts ordered observation steps for offline BKT evaluation."""
        query = (
            self.db.query(
                QuizAttempt.user_id,
                QuestionConceptMapping.concept_id,
                QuizAttemptAnswer.question_id,
                QuizAttemptAnswer.is_correct,
                func.coalesce(QuizAttempt.submitted_at, QuizAttemptAnswer.created_at).label("timestamp"),
                QuizAttemptAnswer.id,
            )
            .join(QuizAttempt, QuizAttemptAnswer.attempt_id == QuizAttempt.id)
            .join(
                QuestionConceptMapping,
                (QuestionConceptMapping.question_id == QuizAttemptAnswer.question_id)
                & (QuestionConceptMapping.workspace_id == workspace_id),
            )
            .filter(
                QuizAttempt.workspace_id == workspace_id,
                QuizAttempt.status == "evaluated",
                QuizAttemptAnswer.is_correct.is_not(None),
                QuestionConceptMapping.validation_status == "validated",
            )
        )
        if concept_id:
            query = query.filter(QuestionConceptMapping.concept_id == concept_id)

        records = query.order_by(
            QuizAttempt.user_id,
            QuestionConceptMapping.concept_id,
            func.coalesce(QuizAttempt.submitted_at, QuizAttemptAnswer.created_at).asc(),
            QuizAttemptAnswer.id.asc(),
        ).all()

        grouped_steps: Dict[Tuple[str, str], List[ObservationStep]] = defaultdict(list)
        for uid, cid, qid, is_corr, tstamp, _ in records:
            step_idx = len(grouped_steps[(str(uid), str(cid))]) + 1
            step = ObservationStep(
                learner_id=str(uid),
                concept_id=str(cid),
                question_id=str(qid),
                is_correct=bool(is_corr),
                step_index=step_idx,
                timestamp=tstamp.isoformat() if tstamp else None,
            )
            grouped_steps[(str(uid), str(cid))].append(step)

        return list(grouped_steps.values())

    def run_offline_evaluation(
        self,
        workspace_id: uuid.UUID,
        req: BKTEvaluationRunCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> BKTEvaluationRun:
        """Executes offline evaluation of a BKT model version against held-out observations."""
        model_ver = (
            self.db.query(BKTModelVersion)
            .filter(
                BKTModelVersion.id == req.model_version_id,
                BKTModelVersion.workspace_id == workspace_id,
            )
            .first()
        )
        if not model_ver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"BKT model version {req.model_version_id} not found in workspace.",
            )

        params = BKTParameters(
            p_init=model_ver.p_init,
            p_transit=model_ver.p_transit,
            p_guess=model_ver.p_guess,
            p_slip=model_ver.p_slip,
            version=model_ver.model_version,
        )

        all_steps = self.extract_evaluation_steps(
            workspace_id=workspace_id,
            concept_id=model_ver.concept_id if model_ver.model_scope == "concept_specific" else None,
        )

        engine = BKTEvaluationEngine()

        if req.split_method == BKTSplitMethod.LEARNER_HOLDOUT:
            train_seqs, test_seqs = engine.split_learner_holdout(
                all_steps,
                test_ratio=req.test_ratio,
                random_seed=req.random_seed,
            )
        else:
            train_seqs, test_seqs = engine.split_temporal_holdout(
                all_steps,
                test_ratio=req.test_ratio,
            )

        eval_result = engine.evaluate_model(
            params=params,
            test_sequences=test_seqs,
            train_sequences=train_seqs,
        )

        eval_run = BKTEvaluationRun(
            workspace_id=workspace_id,
            model_version_id=model_ver.id,
            split_method=req.split_method.value,
            status="completed",
            readiness_status=eval_result["readiness_status"],
            num_learners=eval_result["num_learners"],
            num_sequences=eval_result["num_sequences"],
            num_observations=eval_result["num_observations"],
            log_loss=eval_result["log_loss"],
            brier_score=eval_result["brier_score"],
            accuracy=eval_result["accuracy"],
            auc_roc=eval_result["auc_roc"],
            calibration_metrics=eval_result["calibration_metrics"],
            baseline_metrics=eval_result["baseline_metrics"],
            parameter_stability=eval_result["parameter_stability"],
            readiness_notes=eval_result["readiness_notes"],
            evaluated_by_user_id=user_id,
            completed_at=datetime.now(timezone.utc),
        )
        self.db.add(eval_run)

        # Update model version qualification status
        if eval_result["readiness_status"] == "evaluation_passed" and model_ver.status in ["candidate", "estimated"]:
            model_ver.status = "approved"
        elif model_ver.status == "candidate":
            model_ver.status = "evaluated"

        self.db.commit()
        self.db.refresh(eval_run)
        return eval_run

    def list_evaluation_runs(
        self,
        workspace_id: uuid.UUID,
        model_version_id: Optional[uuid.UUID] = None,
    ) -> List[BKTEvaluationRun]:
        """Lists offline evaluation runs for models in a workspace."""
        query = self.db.query(BKTEvaluationRun).filter(
            BKTEvaluationRun.workspace_id == workspace_id
        )
        if model_version_id:
            query = query.filter(BKTEvaluationRun.model_version_id == model_version_id)

        return query.order_by(BKTEvaluationRun.created_at.desc()).all()

    def get_evaluation_run(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> BKTEvaluationRun:
        """Retrieves a single evaluation run."""
        run = (
            self.db.query(BKTEvaluationRun)
            .filter(
                BKTEvaluationRun.id == run_id,
                BKTEvaluationRun.workspace_id == workspace_id,
            )
            .first()
        )
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"BKT evaluation run {run_id} not found in workspace.",
            )
        return run

    # =========================================================================
    # Training Data Extraction & Parameter Fitting (C9.5)
    # =========================================================================

    def extract_observation_sequences(
        self,
        workspace_id: uuid.UUID,
        concept_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[List[bool]], int, int]:
        """Extracts ordered binary observation sequences from authorized, evaluated attempts.

        Rules:
        - Only evaluated attempts (QuizAttempt.status == 'evaluated')
        - Answers must have a definitive boolean result (is_correct in [True, False])
        - Strictly excludes unanswered/skipped questions (is_correct is None)
        - Must have a validated concept mapping (QuestionConceptMapping.validation_status == 'validated')
        - Chronologically ordered per learner and concept
        """
        query = (
            self.db.query(
                QuizAttempt.user_id,
                QuestionConceptMapping.concept_id,
                QuizAttemptAnswer.is_correct,
                QuizAttempt.submitted_at,
                QuizAttemptAnswer.created_at,
                QuizAttemptAnswer.id,
            )
            .join(QuizAttempt, QuizAttemptAnswer.attempt_id == QuizAttempt.id)
            .join(
                QuestionConceptMapping,
                (QuestionConceptMapping.question_id == QuizAttemptAnswer.question_id)
                & (QuestionConceptMapping.workspace_id == workspace_id),
            )
            .filter(
                QuizAttempt.workspace_id == workspace_id,
                QuizAttempt.status == "evaluated",
                QuizAttemptAnswer.is_correct.is_not(None),
                QuestionConceptMapping.validation_status == "validated",
            )
        )

        if concept_id:
            query = query.filter(QuestionConceptMapping.concept_id == concept_id)

        # Chronological sort per learner-concept sequence
        records = query.order_by(
            QuizAttempt.user_id,
            QuestionConceptMapping.concept_id,
            func.coalesce(QuizAttempt.submitted_at, QuizAttemptAnswer.created_at).asc(),
            QuizAttemptAnswer.id.asc(),
        ).all()

        grouped_seqs: Dict[Tuple[uuid.UUID, uuid.UUID], List[bool]] = defaultdict(list)
        learners = set()
        for uid, cid, is_corr, _, _, _ in records:
            grouped_seqs[(uid, cid)].append(bool(is_corr))
            learners.add(uid)

        sequences = list(grouped_seqs.values())
        return sequences, len(learners), len(grouped_seqs)

    def run_parameter_estimation(
        self,
        workspace_id: uuid.UUID,
        req: BKTEstimationRunCreate,
    ) -> BKTEstimationRun:
        """Executes Baum-Welch EM parameter estimation and records the run in the model registry."""
        sequences, num_learners, num_sequences = self.extract_observation_sequences(
            workspace_id=workspace_id,
            concept_id=req.concept_id if req.model_scope == BKTModelScope.CONCEPT_SPECIFIC else None,
        )

        num_obs = sum(len(s) for s in sequences)

        # Create execution run log in database
        run_record = BKTEstimationRun(
            workspace_id=workspace_id,
            concept_id=req.concept_id if req.model_scope == BKTModelScope.CONCEPT_SPECIFIC else None,
            status="running",
            num_learners=num_learners,
            num_sequences=num_sequences,
            num_observations=num_obs,
        )
        self.db.add(run_record)
        self.db.commit()
        self.db.refresh(run_record)

        try:
            estimator = BKTParameterEstimator(
                max_iter=req.max_iter,
                tol=req.tol,
                n_restarts=req.n_restarts,
                random_seed=req.random_seed,
            )

            version_str = f"bkt_{req.model_scope.value}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            fit_result: BKTEstimationResult = estimator.fit(sequences, model_version=version_str)

            # Determine initial status
            should_activate = req.auto_activate and fit_result.is_statistically_supported
            model_status = "active" if should_activate else "candidate"

            # Archive prior active model if auto-activating
            if should_activate:
                prior_active = (
                    self.db.query(BKTModelVersion)
                    .filter(
                        BKTModelVersion.workspace_id == workspace_id,
                        BKTModelVersion.model_scope == req.model_scope.value,
                        BKTModelVersion.status == "active",
                    )
                )
                if req.concept_id and req.model_scope == BKTModelScope.CONCEPT_SPECIFIC:
                    prior_active = prior_active.filter(BKTModelVersion.concept_id == req.concept_id)
                else:
                    prior_active = prior_active.filter(BKTModelVersion.concept_id.is_(None))
                for m in prior_active.all():
                    m.status = "archived"

            # Create model version record
            metrics_dict = {
                "log_likelihood": fit_result.metrics.log_likelihood,
                "negative_log_likelihood": fit_result.metrics.negative_log_likelihood,
                "brier_score": fit_result.metrics.brier_score,
                "accuracy": fit_result.metrics.accuracy,
                "is_statistically_supported": fit_result.is_statistically_supported,
                "data_quality_notes": fit_result.data_quality_notes,
            }

            model_ver = BKTModelVersion(
                workspace_id=workspace_id,
                model_version=version_str,
                model_scope=req.model_scope.value,
                concept_id=req.concept_id if req.model_scope == BKTModelScope.CONCEPT_SPECIFIC else None,
                p_init=fit_result.parameters.p_init,
                p_transit=fit_result.parameters.p_transit,
                p_guess=fit_result.parameters.p_guess,
                p_slip=fit_result.parameters.p_slip,
                status=model_status,
                training_observation_count=num_obs,
                training_sequence_count=num_sequences,
                validation_metrics=metrics_dict,
            )
            self.db.add(model_ver)
            self.db.flush()

            # Finalize run record
            run_record.model_version_id = model_ver.id
            run_record.status = "completed"
            run_record.converged = fit_result.metrics.converged
            run_record.iterations_count = fit_result.metrics.iterations
            run_record.final_log_likelihood = fit_result.metrics.log_likelihood
            run_record.initial_params = {
                "p_init": fit_result.initial_parameters.p_init,
                "p_transit": fit_result.initial_parameters.p_transit,
                "p_guess": fit_result.initial_parameters.p_guess,
                "p_slip": fit_result.initial_parameters.p_slip,
            }
            run_record.fitted_params = {
                "p_init": fit_result.parameters.p_init,
                "p_transit": fit_result.parameters.p_transit,
                "p_guess": fit_result.parameters.p_guess,
                "p_slip": fit_result.parameters.p_slip,
            }
            run_record.metrics = metrics_dict
            run_record.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(run_record)
            return run_record

        except Exception as exc:
            logger.exception("BKT parameter estimation failed", exc_info=exc)
            run_record.status = "failed"
            run_record.error_message = str(exc)
            run_record.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(run_record)
            return run_record

    # =========================================================================
    # Online Mastery Updates & Provenance Logging (C9.6)
    # =========================================================================

    def process_attempt_evaluation(
        self,
        workspace_id: uuid.UUID,
        attempt_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> List[LearnerConceptMasteryHistory]:
        """Atomically updates learner concept mastery states from an authoritative quiz attempt evaluation.

        Guarantees:
        - Strict idempotency (unique constraint per user_id, attempt_id, question_id, concept_id)
        - Row-level concurrency locking
        - Excludes unanswered questions
        - Strictly requires validated question-concept mappings
        - Persists posterior and predicted-next probabilities separately
        """
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

        # Retrieve evaluated answers for this attempt
        answers = (
            self.db.query(QuizAttemptAnswer)
            .filter(
                QuizAttemptAnswer.attempt_id == attempt_id,
                QuizAttemptAnswer.is_correct.is_not(None),  # Must be evaluated, never unanswered
            )
            .all()
        )

        history_records: List[LearnerConceptMasteryHistory] = []
        now = datetime.now(timezone.utc)

        for ans in answers:
            # Find all validated concept mappings for this question
            mappings = (
                self.db.query(QuestionConceptMapping)
                .filter(
                    QuestionConceptMapping.question_id == ans.question_id,
                    QuestionConceptMapping.workspace_id == workspace_id,
                    QuestionConceptMapping.validation_status == "validated",
                )
                .all()
            )

            for m in mappings:
                concept_id = m.concept_id

                # Idempotency check: if already recorded for this attempt/question/concept, skip
                existing_history = (
                    self.db.query(LearnerConceptMasteryHistory)
                    .filter(
                        LearnerConceptMasteryHistory.user_id == user_id,
                        LearnerConceptMasteryHistory.attempt_id == attempt_id,
                        LearnerConceptMasteryHistory.question_id == ans.question_id,
                        LearnerConceptMasteryHistory.concept_id == concept_id,
                    )
                    .first()
                )
                if existing_history:
                    history_records.append(existing_history)
                    continue

                # Concurrency safety: fetch existing mastery state
                mastery_record = (
                    self.db.query(LearnerConceptMastery)
                    .filter(
                        LearnerConceptMastery.workspace_id == workspace_id,
                        LearnerConceptMastery.user_id == user_id,
                        LearnerConceptMastery.concept_id == concept_id,
                    )
                    .first()
                )

                # Resolve applicable BKT parameters
                params, model_ver = self.resolve_active_parameters(workspace_id, concept_id)
                tracer = BayesianKnowledgeTracer(params)

                if not mastery_record:
                    # First observation for this learner-concept pair
                    prior_mastery = params.p_init
                    sequence_index = 1
                    mastery_record = LearnerConceptMastery(
                        workspace_id=workspace_id,
                        user_id=user_id,
                        concept_id=concept_id,
                        model_version_id=model_ver.id if model_ver else None,
                        posterior_mastery_probability=prior_mastery,
                        predicted_next_mastery_probability=prior_mastery,
                        observation_count=0,
                        status=LearnerMasteryStatus.INSUFFICIENT_DATA.value,
                    )
                    self.db.add(mastery_record)
                    self.db.flush()
                else:
                    prior_mastery = mastery_record.predicted_next_mastery_probability
                    sequence_index = mastery_record.observation_count + 1

                # Perform Bayesian update step
                step_result = tracer.update_mastery(
                    current_mastery=prior_mastery,
                    observation=bool(ans.is_correct),
                    custom_params=params,
                )

                # Status thresholding for presentation
                if sequence_index < 3:
                    mastery_status = LearnerMasteryStatus.INSUFFICIENT_DATA.value
                elif step_result.predicted_next_mastery >= 0.80:
                    mastery_status = LearnerMasteryStatus.MASTERED.value
                else:
                    mastery_status = LearnerMasteryStatus.DEVELOPING.value

                # Update current mastery projection
                mastery_record.posterior_mastery_probability = step_result.posterior_mastery
                mastery_record.predicted_next_mastery_probability = step_result.predicted_next_mastery
                mastery_record.observation_count = sequence_index
                mastery_record.last_attempt_id = attempt_id
                mastery_record.last_question_id = ans.question_id
                mastery_record.last_observation_correct = bool(ans.is_correct)
                mastery_record.status = mastery_status
                mastery_record.model_version_id = model_ver.id if model_ver else None
                mastery_record.last_updated_at = now

                # Create immutable history record
                hist = LearnerConceptMasteryHistory(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    concept_id=concept_id,
                    mastery_id=mastery_record.id,
                    attempt_id=attempt_id,
                    question_id=ans.question_id,
                    observation_correct=bool(ans.is_correct),
                    prior_mastery=prior_mastery,
                    posterior_mastery=step_result.posterior_mastery,
                    predicted_next_mastery=step_result.predicted_next_mastery,
                    p_init=params.p_init,
                    p_transit=params.p_transit,
                    p_guess=params.p_guess,
                    p_slip=params.p_slip,
                    model_version=params.version,
                    sequence_index=sequence_index,
                    occurred_at=attempt.submitted_at or now,
                    created_at=now,
                )
                self.db.add(hist)
                history_records.append(hist)

        self.db.commit()
        return history_records

    # =========================================================================
    # Learner Mastery Queries (C9.6)
    # =========================================================================

    def get_learner_masteries(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> List[LearnerConceptMasteryResponse]:
        """Returns current mastery states for all evaluated concepts for a learner."""
        records = (
            self.db.query(LearnerConceptMastery)
            .join(KnowledgeNode, LearnerConceptMastery.concept_id == KnowledgeNode.id)
            .filter(
                LearnerConceptMastery.workspace_id == workspace_id,
                LearnerConceptMastery.user_id == user_id,
            )
            .order_by(LearnerConceptMastery.predicted_next_mastery_probability.desc())
            .all()
        )

        return [
            LearnerConceptMasteryResponse(
                id=r.id,
                workspace_id=r.workspace_id,
                user_id=r.user_id,
                concept_id=r.concept_id,
                concept_name=r.concept.name if r.concept else None,
                concept_category=r.concept.category if r.concept else None,
                model_version_id=r.model_version_id,
                posterior_mastery_probability=round(r.posterior_mastery_probability, 4),
                predicted_next_mastery_probability=round(r.predicted_next_mastery_probability, 4),
                observation_count=r.observation_count,
                last_attempt_id=r.last_attempt_id,
                last_question_id=r.last_question_id,
                last_observation_correct=r.last_observation_correct,
                status=r.status,
                last_updated_at=r.last_updated_at,
                created_at=r.created_at,
            )
            for r in records
        ]

    def get_concept_mastery(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> LearnerConceptMasteryResponse:
        """Returns the current mastery state for a specific concept."""
        record = (
            self.db.query(LearnerConceptMastery)
            .join(KnowledgeNode, LearnerConceptMastery.concept_id == KnowledgeNode.id)
            .filter(
                LearnerConceptMastery.workspace_id == workspace_id,
                LearnerConceptMastery.user_id == user_id,
                LearnerConceptMastery.concept_id == concept_id,
            )
            .first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mastery state not found for this concept.",
            )

        return LearnerConceptMasteryResponse(
            id=record.id,
            workspace_id=record.workspace_id,
            user_id=record.user_id,
            concept_id=record.concept_id,
            concept_name=record.concept.name if record.concept else None,
            concept_category=record.concept.category if record.concept else None,
            model_version_id=record.model_version_id,
            posterior_mastery_probability=round(record.posterior_mastery_probability, 4),
            predicted_next_mastery_probability=round(record.predicted_next_mastery_probability, 4),
            observation_count=record.observation_count,
            last_attempt_id=record.last_attempt_id,
            last_question_id=record.last_question_id,
            last_observation_correct=record.last_observation_correct,
            status=record.status,
            last_updated_at=record.last_updated_at,
            created_at=record.created_at,
        )

    def get_concept_mastery_history(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> List[LearnerConceptMasteryHistoryResponse]:
        """Returns the chronological history of Bayesian updates for a concept."""
        records = (
            self.db.query(LearnerConceptMasteryHistory)
            .filter(
                LearnerConceptMasteryHistory.workspace_id == workspace_id,
                LearnerConceptMasteryHistory.user_id == user_id,
                LearnerConceptMasteryHistory.concept_id == concept_id,
            )
            .order_by(LearnerConceptMasteryHistory.sequence_index.asc())
            .all()
        )

        return [
            LearnerConceptMasteryHistoryResponse(
                id=r.id,
                workspace_id=r.workspace_id,
                user_id=r.user_id,
                concept_id=r.concept_id,
                mastery_id=r.mastery_id,
                attempt_id=r.attempt_id,
                question_id=r.question_id,
                observation_correct=r.observation_correct,
                prior_mastery=round(r.prior_mastery, 4),
                posterior_mastery=round(r.posterior_mastery, 4),
                predicted_next_mastery=round(r.predicted_next_mastery, 4),
                p_init=r.p_init,
                p_transit=r.p_transit,
                p_guess=r.p_guess,
                p_slip=r.p_slip,
                model_version=r.model_version,
                sequence_index=r.sequence_index,
                occurred_at=r.occurred_at,
                created_at=r.created_at,
            )
            for r in records
        ]

    def get_mastery_summary(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> LearnerMasterySummaryResponse:
        """Returns aggregate concept mastery counts and averages for a learner."""
        items = self.get_learner_masteries(workspace_id, user_id)

        mastered = sum(1 for item in items if item.status == LearnerMasteryStatus.MASTERED.value)
        developing = sum(1 for item in items if item.status == LearnerMasteryStatus.DEVELOPING.value)
        insufficient = sum(1 for item in items if item.status == LearnerMasteryStatus.INSUFFICIENT_DATA.value)
        avg_prob = (
            sum(item.predicted_next_mastery_probability for item in items) / len(items)
            if items
            else 0.0
        )

        return LearnerMasterySummaryResponse(
            workspace_id=workspace_id,
            user_id=user_id,
            total_concepts_evaluated=len(items),
            mastered_count=mastered,
            developing_count=developing,
            insufficient_data_count=insufficient,
            average_mastery_probability=round(avg_prob, 4),
            items=items,
        )
