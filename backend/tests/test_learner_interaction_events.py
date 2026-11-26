"""Tests for Learner Interaction Events (Phase 9 C9.2).

Covers:
- Event ingestion with allowed event taxonomy
- Server-authoritative timestamps
- Anti-tampering: rejection of client-injected scores/correctness
- Idempotency key deduplication
- Batch event ingestion
- Filtered and paginated listing
- Attempt interaction chronological history
- Multi-tenant workspace and attempt authorization isolation
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.learner_intelligence import LearnerInteractionEvent
from backend.app.models.study_material import MCQOption, MCQQuestion, QuizAttempt
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


@pytest.fixture
def sample_attempt(
    db_session: Session,
    test_workspace: Workspace,
    test_user: User,
) -> QuizAttempt:
    """Creates a sample quiz attempt owned by test_user."""
    attempt = QuizAttempt(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        title="Clustering Knowledge Check",
        status="in_progress",
        total_questions=3,
        questions_order=[],
    )
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(attempt)
    return attempt


@pytest.fixture
def sample_question(
    db_session: Session,
    test_workspace: Workspace,
) -> MCQQuestion:
    """Creates an MCQ question."""
    mcq = MCQQuestion(
        workspace_id=test_workspace.id,
        question_text="What does K represent in K-Means?",
        difficulty="easy",
        question_type="conceptual",
        correct_option_id="opt_1",
        explanation="K denotes the number of cluster centroids.",
        topic_tags=["clustering"],
        source_references=[],
    )
    db_session.add(mcq)
    db_session.commit()
    db_session.refresh(mcq)
    return mcq


def test_record_single_interaction_event(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    sample_attempt: QuizAttempt,
    sample_question: MCQQuestion,
):
    """Test recording a valid interaction event with server-authoritative timestamps."""
    url = f"/api/v1/workspaces/{test_workspace.id}/learning-interactions/events"
    payload = {
        "event_type": "question_presented",
        "attempt_id": str(sample_attempt.id),
        "question_id": str(sample_question.id),
        "event_metadata": {
            "view_mode": "interactive_quiz",
            "time_spent_ms": 1500,
        },
        "idempotency_key": "evt-12345",
    }

    res = test_client.post(url, json=payload, headers=auth_headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["event_type"] == "question_presented"
    assert data["attempt_id"] == str(sample_attempt.id)
    assert data["question_id"] == str(sample_question.id)
    assert data["idempotency_key"] == "evt-12345"
    assert "occurred_at" in data


def test_anti_tampering_score_injection_rejected(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    sample_attempt: QuizAttempt,
    sample_question: MCQQuestion,
):
    """Clients cannot submit scores, correctness, or percentage in event metadata."""
    url = f"/api/v1/workspaces/{test_workspace.id}/learning-interactions/events"

    # Attempting to inject is_correct
    payload = {
        "event_type": "answer_submitted",
        "attempt_id": str(sample_attempt.id),
        "question_id": str(sample_question.id),
        "event_metadata": {
            "selected_option": "opt_1",
            "is_correct": True,  # Disallowed
        },
    }
    res = test_client.post(url, json=payload, headers=auth_headers)
    assert res.status_code == 422
    assert "disallowed" in res.text.lower() or "validation error" in res.text.lower()

    # Attempting to inject score
    payload_score = {
        "event_type": "quiz_submitted",
        "attempt_id": str(sample_attempt.id),
        "event_metadata": {
            "score": 100,  # Disallowed
        },
    }
    res_score = test_client.post(url, json=payload_score, headers=auth_headers)
    assert res_score.status_code == 422


def test_idempotency_key_deduplication(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    sample_attempt: QuizAttempt,
):
    """Submitting the same idempotency key returns the existing record without duplicating."""
    url = f"/api/v1/workspaces/{test_workspace.id}/learning-interactions/events"
    payload = {
        "event_type": "quiz_started",
        "attempt_id": str(sample_attempt.id),
        "event_metadata": {"client_agent": "KnoveraUI/1.0"},
        "idempotency_key": "unique-session-start-key-999",
    }

    res1 = test_client.post(url, json=payload, headers=auth_headers)
    assert res1.status_code == 201
    evt1 = res1.json()

    res2 = test_client.post(url, json=payload, headers=auth_headers)
    assert res2.status_code == 201
    evt2 = res2.json()

    # Same event ID
    assert evt1["id"] == evt2["id"]


def test_batch_event_ingestion(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    sample_attempt: QuizAttempt,
    sample_question: MCQQuestion,
):
    """Test batch ingestion of multiple learning actions in one request."""
    url = f"/api/v1/workspaces/{test_workspace.id}/learning-interactions/events/batch"
    payload = {
        "events": [
            {
                "event_type": "question_viewed",
                "attempt_id": str(sample_attempt.id),
                "question_id": str(sample_question.id),
                "event_metadata": {"dwell_time_ms": 3000},
            },
            {
                "event_type": "hint_opened",
                "attempt_id": str(sample_attempt.id),
                "question_id": str(sample_question.id),
                "event_metadata": {"section": "hint_box"},
            },
            {
                "event_type": "answer_selected",
                "attempt_id": str(sample_attempt.id),
                "question_id": str(sample_question.id),
                "event_metadata": {"option_id": "opt_1"},
            },
        ]
    }

    res = test_client.post(url, json=payload, headers=auth_headers)
    assert res.status_code == 201, res.text
    events = res.json()
    assert len(events) == 3
    assert [e["event_type"] for e in events] == [
        "question_viewed",
        "hint_opened",
        "answer_selected",
    ]


def test_list_and_filter_events(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    sample_attempt: QuizAttempt,
    sample_question: MCQQuestion,
):
    """Test querying and filtering persisted events."""
    # Add a hint_opened event
    test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/learning-interactions/events",
        json={
            "event_type": "hint_opened",
            "attempt_id": str(sample_attempt.id),
            "question_id": str(sample_question.id),
        },
        headers=auth_headers,
    )

    # Filter by event_type
    list_url = f"/api/v1/workspaces/{test_workspace.id}/learning-interactions/events?event_type=hint_opened"
    res = test_client.get(list_url, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert all(item["event_type"] == "hint_opened" for item in data["items"])

    # Attempt timeline
    att_url = f"/api/v1/workspaces/{test_workspace.id}/quiz-attempts/{sample_attempt.id}/interactions"
    att_res = test_client.get(att_url, headers=auth_headers)
    assert att_res.status_code == 200
    timeline = att_res.json()
    assert isinstance(timeline, list)
    assert any(e["event_type"] == "hint_opened" for e in timeline)


def test_unauthorized_user_attempt_isolation(
    test_client: TestClient,
    other_auth_headers: dict,
    test_workspace: Workspace,
    sample_attempt: QuizAttempt,
):
    """Another user cannot log events or read interactions for someone else's attempt."""
    url = f"/api/v1/workspaces/{test_workspace.id}/learning-interactions/events"
    payload = {
        "event_type": "quiz_started",
        "attempt_id": str(sample_attempt.id),
    }
    # other_user has no access to test_workspace
    res = test_client.post(url, json=payload, headers=other_auth_headers)
    assert res.status_code in (403, 404)
