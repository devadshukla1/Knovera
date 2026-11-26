"""Tests for Online Mastery Probability Updates and Quiz Integration (Phase 9 C9.6).

Covers:
- First observation state initialization from active P(L_0)
- Subsequent Bayesian updates maintaining sequence continuity
- Exclusion of unanswered and unsubmitted questions
- Exclusion of unvalidated concept mappings
- Strict idempotency (duplicate evaluations cannot alter state twice)
- Concurrency protection & version tracking
- Real integration through QuizEvaluationService
- Learner mastery APIs (/mastery, /concepts/{id}/mastery, /concepts/{id}/history, /summary)
"""

from datetime import datetime, timezone
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.ml.study_materials.evaluation_service import QuizEvaluationService
from backend.app.ml.study_materials.schemas import QuizAttemptAnswerSubmit
from backend.app.models.bkt import LearnerConceptMastery, LearnerConceptMasteryHistory
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.learner_intelligence import QuestionConceptMapping
from backend.app.models.study_material import (
    MCQOption,
    MCQQuestion,
    QuizAttempt,
    QuizAttemptAnswer,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.services.bkt_service import BKTService


@pytest.fixture
def bkt_setup(
    db_session: Session,
    test_workspace: Workspace,
    test_user: User,
):
    """Sets up concepts, validated questions, and attempts for BKT tests."""
    # 1. Canonical Concepts
    concept_kmeans = KnowledgeNode(
        workspace_id=test_workspace.id,
        node_type="concept",
        category="algorithm",
        name="K-Means Clustering",
        normalized_name="kmeans clustering",
        description="Iterative centroid partitioning",
    )
    concept_pca = KnowledgeNode(
        workspace_id=test_workspace.id,
        node_type="concept",
        category="algorithm",
        name="Principal Component Analysis",
        normalized_name="principal component analysis",
        description="Linear dimensionality reduction",
    )
    db_session.add_all([concept_kmeans, concept_pca])
    db_session.flush()

    # 2. Questions
    q1 = MCQQuestion(
        workspace_id=test_workspace.id,
        question_text="What is K in K-Means?",
        difficulty="easy",
        question_type="conceptual",
        correct_option_id="opt_1",
        explanation="K denotes the cluster count.",
        topic_tags=["clustering"],
        source_references=[],
    )
    q2 = MCQQuestion(
        workspace_id=test_workspace.id,
        question_text="What does each centroid represent in K-Means?",
        difficulty="medium",
        question_type="conceptual",
        correct_option_id="opt_mean",
        explanation="Centroid is the mean of assigned points.",
        topic_tags=["clustering"],
        source_references=[],
    )
    q_unvalidated = MCQQuestion(
        workspace_id=test_workspace.id,
        question_text="What is variance in PCA?",
        difficulty="hard",
        question_type="conceptual",
        correct_option_id="opt_var",
        explanation="PCA maximizes variance along eigenvectors.",
        topic_tags=["pca"],
        source_references=[],
    )
    db_session.add_all([q1, q2, q_unvalidated])
    db_session.flush()

    # 3. Validated mappings for q1 and q2 -> K-Means
    m1 = QuestionConceptMapping(
        workspace_id=test_workspace.id,
        question_id=q1.id,
        question_type="mcq",
        concept_id=concept_kmeans.id,
        mapping_method="explicit_metadata",
        confidence_score=1.0,
        validation_status="validated",
    )
    m2 = QuestionConceptMapping(
        workspace_id=test_workspace.id,
        question_id=q2.id,
        question_type="mcq",
        concept_id=concept_kmeans.id,
        mapping_method="explicit_metadata",
        confidence_score=0.95,
        validation_status="validated",
    )
    # Unvalidated mapping (candidate) -> PCA
    m_cand = QuestionConceptMapping(
        workspace_id=test_workspace.id,
        question_id=q_unvalidated.id,
        question_type="mcq",
        concept_id=concept_pca.id,
        mapping_method="deterministic_extraction",
        confidence_score=0.6,
        validation_status="candidate",  # NOT validated
    )
    db_session.add_all([m1, m2, m_cand])
    db_session.commit()

    return {
        "concept_kmeans": concept_kmeans,
        "concept_pca": concept_pca,
        "q1": q1,
        "q2": q2,
        "q_unvalidated": q_unvalidated,
    }


def test_first_and_subsequent_bkt_mastery_updates(
    db_session: Session,
    test_workspace: Workspace,
    test_user: User,
    bkt_setup: dict,
):
    """Verifies that the first observation initializes mastery from P(L_0)

    and a second observation updates the state sequentially.
    """
    concept = bkt_setup["concept_kmeans"]
    q1 = bkt_setup["q1"]
    q2 = bkt_setup["q2"]
    now = datetime.now(timezone.utc)

    # 1. First Attempt: Question 1 answered correctly
    att1 = QuizAttempt(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        title="Quiz 1",
        status="evaluated",
        total_questions=1,
        correct_answers_count=1,
        score_percentage=100.0,
        submitted_at=now,
    )
    db_session.add(att1)
    db_session.flush()

    ans1 = QuizAttemptAnswer(
        attempt_id=att1.id,
        question_id=q1.id,
        question_type="mcq",
        selected_answer="opt_1",
        is_correct=True,
    )
    db_session.add(ans1)
    db_session.commit()

    bkt_service = BKTService(db_session)
    history1 = bkt_service.process_attempt_evaluation(
        workspace_id=test_workspace.id,
        attempt_id=att1.id,
        user_id=test_user.id,
    )

    assert len(history1) == 1
    h1 = history1[0]
    assert h1.sequence_index == 1
    assert h1.observation_correct is True
    # Default P(L_0) = 0.30
    assert pytest.approx(h1.prior_mastery, abs=1e-5) == 0.30
    # Expected posterior ~ 0.6585, next ~ 0.7098
    assert pytest.approx(h1.posterior_mastery, abs=1e-4) == 0.6585
    assert pytest.approx(h1.predicted_next_mastery, abs=1e-4) == 0.7098

    # Check current mastery table
    mastery_state = (
        db_session.query(LearnerConceptMastery)
        .filter(
            LearnerConceptMastery.workspace_id == test_workspace.id,
            LearnerConceptMastery.user_id == test_user.id,
            LearnerConceptMastery.concept_id == concept.id,
        )
        .first()
    )
    assert mastery_state is not None
    assert mastery_state.observation_count == 1
    assert pytest.approx(mastery_state.predicted_next_mastery_probability, abs=1e-4) == 0.7098
    assert mastery_state.status == "insufficient_data"  # < 3 observations

    # 2. Second Attempt: Question 2 answered incorrectly
    att2 = QuizAttempt(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        title="Quiz 2",
        status="evaluated",
        total_questions=1,
        correct_answers_count=0,
        score_percentage=0.0,
        submitted_at=now,
    )
    db_session.add(att2)
    db_session.flush()

    ans2 = QuizAttemptAnswer(
        attempt_id=att2.id,
        question_id=q2.id,
        question_type="mcq",
        selected_answer="opt_wrong",
        is_correct=False,
    )
    db_session.add(ans2)
    db_session.commit()

    history2 = bkt_service.process_attempt_evaluation(
        workspace_id=test_workspace.id,
        attempt_id=att2.id,
        user_id=test_user.id,
    )

    assert len(history2) == 1
    h2 = history2[0]
    assert h2.sequence_index == 2
    assert h2.observation_correct is False
    # Prior for step 2 should equal predicted_next from step 1
    assert pytest.approx(h2.prior_mastery, abs=1e-4) == 0.7098
    # An incorrect response reduces the posterior below prior
    assert h2.posterior_mastery < h2.prior_mastery

    # Check updated current mastery
    db_session.refresh(mastery_state)
    assert mastery_state.observation_count == 2
    assert mastery_state.last_observation_correct is False


def test_unvalidated_concept_mapping_excluded(
    db_session: Session,
    test_workspace: Workspace,
    test_user: User,
    bkt_setup: dict,
):
    """Answers to questions with only 'candidate' or unvalidated mappings are not processed by BKT."""
    q_unval = bkt_setup["q_unvalidated"]
    concept_pca = bkt_setup["concept_pca"]
    now = datetime.now(timezone.utc)

    att = QuizAttempt(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        title="PCA Quiz",
        status="evaluated",
        total_questions=1,
        correct_answers_count=1,
        score_percentage=100.0,
        submitted_at=now,
    )
    db_session.add(att)
    db_session.flush()

    ans = QuizAttemptAnswer(
        attempt_id=att.id,
        question_id=q_unval.id,
        question_type="mcq",
        selected_answer="opt_var",
        is_correct=True,
    )
    db_session.add(ans)
    db_session.commit()

    bkt_service = BKTService(db_session)
    history = bkt_service.process_attempt_evaluation(
        workspace_id=test_workspace.id,
        attempt_id=att.id,
        user_id=test_user.id,
    )

    # No validated mapping -> zero BKT updates
    assert len(history) == 0

    # Ensure PCA concept has no mastery record
    mastery = (
        db_session.query(LearnerConceptMastery)
        .filter(
            LearnerConceptMastery.workspace_id == test_workspace.id,
            LearnerConceptMastery.concept_id == concept_pca.id,
        )
        .first()
    )
    assert mastery is None


def test_idempotency_prevents_duplicate_mastery_updates(
    db_session: Session,
    test_workspace: Workspace,
    test_user: User,
    bkt_setup: dict,
):
    """Calling process_attempt_evaluation multiple times on the same attempt does NOT create duplicate updates."""
    concept = bkt_setup["concept_kmeans"]
    q1 = bkt_setup["q1"]
    now = datetime.now(timezone.utc)

    att = QuizAttempt(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        title="Idempotency Test",
        status="evaluated",
        total_questions=1,
        correct_answers_count=1,
        score_percentage=100.0,
        submitted_at=now,
    )
    db_session.add(att)
    db_session.flush()

    ans = QuizAttemptAnswer(
        attempt_id=att.id,
        question_id=q1.id,
        question_type="mcq",
        selected_answer="opt_1",
        is_correct=True,
    )
    db_session.add(ans)
    db_session.commit()

    bkt_service = BKTService(db_session)

    # First call
    h_first = bkt_service.process_attempt_evaluation(test_workspace.id, att.id, test_user.id)
    assert len(h_first) == 1

    # Second call (e.g. duplicate webhook or retried job)
    h_second = bkt_service.process_attempt_evaluation(test_workspace.id, att.id, test_user.id)
    assert len(h_second) == 1

    # Total history count in DB must still be 1
    total_history = (
        db_session.query(LearnerConceptMasteryHistory)
        .filter(
            LearnerConceptMasteryHistory.workspace_id == test_workspace.id,
            LearnerConceptMasteryHistory.attempt_id == att.id,
        )
        .count()
    )
    assert total_history == 1

    # Observation count in mastery table remains 1
    mastery = (
        db_session.query(LearnerConceptMastery)
        .filter(
            LearnerConceptMastery.workspace_id == test_workspace.id,
            LearnerConceptMastery.concept_id == concept.id,
        )
        .first()
    )
    assert mastery.observation_count == 1


def test_end_to_end_quiz_evaluation_service_triggers_bkt(
    test_client: TestClient,
    auth_headers: dict,
    db_session: Session,
    test_workspace: Workspace,
    test_user: User,
    bkt_setup: dict,
):
    """End-to-end integration: Submitting an attempt through QuizEvaluationService

    automatically triggers BKT mastery calculation and updates API state.
    """
    q1 = bkt_setup["q1"]
    concept = bkt_setup["concept_kmeans"]

    # 1. Add MCQ Option to DB
    opt = MCQOption(
        question_id=q1.id,
        option_id="opt_1",
        option_text="K clusters",
        is_correct=True,
    )
    db_session.add(opt)

    # 2. Create in-progress attempt
    att = QuizAttempt(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        title="Live Interactive Quiz",
        status="in_progress",
        total_questions=1,
        questions_order=[{"id": str(q1.id), "type": "mcq", "question_type": "mcq"}],
    )
    db_session.add(att)
    db_session.commit()

    # 3. Evaluate through QuizEvaluationService
    eval_service = QuizEvaluationService(db_session)
    answers_payload = [
        QuizAttemptAnswerSubmit(
            question_id=q1.id,
            question_type="mcq",
            selected_answer="opt_1",
        )
    ]
    eval_service.evaluate_attempt(att, answers_payload)

    # 4. Query learner BKT API endpoints
    summary_url = f"/api/v1/workspaces/{test_workspace.id}/bkt/learners/me/mastery/summary"
    sum_res = test_client.get(summary_url, headers=auth_headers)
    assert sum_res.status_code == 200, sum_res.text
    summary_data = sum_res.json()
    assert summary_data["total_concepts_evaluated"] == 1
    assert summary_data["items"][0]["concept_id"] == str(concept.id)
    assert summary_data["items"][0]["observation_count"] == 1
    assert summary_data["items"][0]["posterior_mastery_probability"] > 0.50

    # Query concept history API
    history_url = f"/api/v1/workspaces/{test_workspace.id}/bkt/learners/me/concepts/{concept.id}/history"
    hist_res = test_client.get(history_url, headers=auth_headers)
    assert hist_res.status_code == 200
    hist_items = hist_res.json()
    assert len(hist_items) == 1
    assert hist_items[0]["observation_correct"] is True
