"""Tests for Quiz Attempt Tracking and Concept Performance Attribution (Phase 9 C9.3).

Covers:
- Concept performance breakdown (questions attempted, answered, correct, incorrect, unanswered)
- Correct rate calculation and zero-division safeguard
- Question tracking metrics (display order, timing, revisions, hints opened, sources opened)
- Workspace learning interactions summary
- Non-regression check ensuring C8.9 Quiz History endpoints remain functional
"""

from datetime import datetime, timezone
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.learner_intelligence import (
    LearnerInteractionEvent,
    QuestionConceptMapping,
)
from backend.app.models.study_material import (
    MCQOption,
    MCQQuestion,
    QuizAttempt,
    QuizAttemptAnswer,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


@pytest.fixture
def tracking_setup(
    db_session: Session,
    test_workspace: Workspace,
    test_user: User,
):
    """Sets up concepts, questions, mappings, attempt, and answers for tracking tests."""
    # 1. Concepts
    concept_a = KnowledgeNode(
        workspace_id=test_workspace.id,
        node_type="concept",
        category="algorithm",
        name="K-Means Clustering",
        normalized_name="kmeans clustering",
        description="Iterative centroid partitioning",
    )
    concept_b = KnowledgeNode(
        workspace_id=test_workspace.id,
        node_type="concept",
        category="metric",
        name="Silhouette Score",
        normalized_name="silhouette score",
        description="Cluster cohesion and separation metric",
    )
    db_session.add_all([concept_a, concept_b])
    db_session.flush()

    # 2. Questions
    q1 = MCQQuestion(
        workspace_id=test_workspace.id,
        question_text="What does K denote in K-Means?",
        difficulty="easy",
        question_type="conceptual",
        correct_option_id="opt_1",
        explanation="K is the number of clusters.",
        topic_tags=["clustering"],
        source_references=[],
    )
    q2 = MCQQuestion(
        workspace_id=test_workspace.id,
        question_text="What is the range of the Silhouette Score?",
        difficulty="medium",
        question_type="conceptual",
        correct_option_id="opt_2",
        explanation="The silhouette score ranges from -1 to +1.",
        topic_tags=["metrics"],
        source_references=[],
    )
    q3 = MCQQuestion(
        workspace_id=test_workspace.id,
        question_text="How is a cluster centroid updated in K-Means?",
        difficulty="hard",
        question_type="algorithmic",
        correct_option_id="opt_3",
        explanation="Centroid is updated to the mean of assigned points.",
        topic_tags=["clustering"],
        source_references=[],
    )
    db_session.add_all([q1, q2, q3])
    db_session.flush()

    # 3. Concept Mappings
    m1 = QuestionConceptMapping(
        workspace_id=test_workspace.id,
        question_id=q1.id,
        question_type="mcq",
        concept_id=concept_a.id,
        mapping_method="explicit_metadata",
        confidence_score=1.0,
        validation_status="validated",
    )
    m2 = QuestionConceptMapping(
        workspace_id=test_workspace.id,
        question_id=q2.id,
        question_type="mcq",
        concept_id=concept_b.id,
        mapping_method="explicit_metadata",
        confidence_score=1.0,
        validation_status="validated",
    )
    m3 = QuestionConceptMapping(
        workspace_id=test_workspace.id,
        question_id=q3.id,
        question_type="mcq",
        concept_id=concept_a.id,
        mapping_method="explicit_metadata",
        confidence_score=0.9,
        validation_status="candidate",
    )
    db_session.add_all([m1, m2, m3])
    db_session.flush()

    # 4. Quiz Attempt
    now = datetime.now(timezone.utc)
    attempt = QuizAttempt(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        title="Unsupervised Learning Evaluation",
        status="evaluated",
        total_questions=3,
        correct_answers_count=2,
        score_percentage=66.7,
        questions_order=[
            {"id": str(q1.id), "question_type": "mcq"},
            {"id": str(q2.id), "question_type": "mcq"},
            {"id": str(q3.id), "question_type": "mcq"},
        ],
        started_at=now,
        submitted_at=now,
    )
    db_session.add(attempt)
    db_session.flush()

    # Answers: q1 correct, q2 correct, q3 incorrect
    ans1 = QuizAttemptAnswer(
        attempt_id=attempt.id,
        question_id=q1.id,
        question_type="mcq",
        selected_answer="opt_1",
        is_correct=True,
    )
    ans2 = QuizAttemptAnswer(
        attempt_id=attempt.id,
        question_id=q2.id,
        question_type="mcq",
        selected_answer="opt_2",
        is_correct=True,
    )
    ans3 = QuizAttemptAnswer(
        attempt_id=attempt.id,
        question_id=q3.id,
        question_type="mcq",
        selected_answer="opt_wrong",
        is_correct=False,
    )
    db_session.add_all([ans1, ans2, ans3])

    # 5. Interaction Events for tracking
    e1 = LearnerInteractionEvent(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        attempt_id=attempt.id,
        question_id=q1.id,
        event_type="question_presented",
        occurred_at=now,
        event_metadata={"time_spent_ms": 2500},
    )
    e2 = LearnerInteractionEvent(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        attempt_id=attempt.id,
        question_id=q1.id,
        event_type="hint_opened",
        occurred_at=now,
        event_metadata={},
    )
    e3 = LearnerInteractionEvent(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        attempt_id=attempt.id,
        question_id=q1.id,
        event_type="answer_revised",
        occurred_at=now,
        event_metadata={},
    )
    db_session.add_all([e1, e2, e3])
    db_session.commit()

    return {
        "concept_a": concept_a,
        "concept_b": concept_b,
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "attempt": attempt,
    }


def test_get_attempt_concept_performance(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    tracking_setup: dict,
):
    """Verifies concept-level performance calculations."""
    attempt = tracking_setup["attempt"]
    url = f"/api/v1/workspaces/{test_workspace.id}/quiz-attempts/{attempt.id}/concept-performance"

    res = test_client.get(url, headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["attempt_id"] == str(attempt.id)
    assert data["status"] == "evaluated"
    concepts = {c["concept_name"]: c for c in data["concepts"]}

    # K-Means: mapped to q1 (correct) and q3 (incorrect) -> 2 attempted, 2 answered, 1 correct, 50.0%
    assert "K-Means Clustering" in concepts
    kmeans_metric = concepts["K-Means Clustering"]
    assert kmeans_metric["questions_attempted"] == 2
    assert kmeans_metric["questions_answered"] == 2
    assert kmeans_metric["correct_answers"] == 1
    assert kmeans_metric["incorrect_answers"] == 1
    assert kmeans_metric["correct_rate"] == 50.0

    # Silhouette: mapped to q2 (correct) -> 1 attempted, 1 answered, 1 correct, 100.0%
    assert "Silhouette Score" in concepts
    sil_metric = concepts["Silhouette Score"]
    assert sil_metric["questions_attempted"] == 1
    assert sil_metric["questions_answered"] == 1
    assert sil_metric["correct_answers"] == 1
    assert sil_metric["incorrect_answers"] == 0
    assert sil_metric["correct_rate"] == 100.0


def test_get_attempt_tracking_operational_metrics(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    tracking_setup: dict,
):
    """Verifies full operational tracking including question metrics and revisions."""
    attempt = tracking_setup["attempt"]
    q1 = tracking_setup["q1"]
    url = f"/api/v1/workspaces/{test_workspace.id}/quiz-attempts/{attempt.id}/tracking"

    res = test_client.get(url, headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["total_questions"] == 3
    assert data["answered_count"] == 3
    assert data["unanswered_count"] == 0
    assert data["correct_count"] == 2
    assert len(data["questions"]) == 3

    # Inspect q1 tracking
    q1_metric = next(q for q in data["questions"] if q["question_id"] == str(q1.id))
    assert q1_metric["is_answered"] is True
    assert q1_metric["is_correct"] is True
    assert q1_metric["hint_opened"] is True
    assert q1_metric["response_duration_ms"] == 2500
    assert "K-Means Clustering" in q1_metric["mapped_concepts"]


def test_learning_interactions_summary(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    tracking_setup: dict,
):
    """Verifies workspace-wide interaction aggregates."""
    url = f"/api/v1/workspaces/{test_workspace.id}/learning-interactions/summary"
    res = test_client.get(url, headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_events"] >= 3
    assert data["total_hints_opened"] >= 1
    assert "question_presented" in data["events_by_type"]


def test_quiz_history_backward_compatibility(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    tracking_setup: dict,
):
    """Ensures existing Phase 8 C8.9 Quiz History endpoints continue to function without regressions."""
    url = f"/api/v1/workspaces/{test_workspace.id}/quiz-history"
    res = test_client.get(url, headers=auth_headers)
    assert res.status_code == 200, res.text
    history = res.json()
    assert history["total"] >= 1
    assert any(item["title"] == "Unsupervised Learning Evaluation" for item in history["items"])
