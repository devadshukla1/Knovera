"""Tests for Quiz History, Performance Analytics, and Retakes (Phase 8: C8.9)."""

from datetime import datetime, timezone
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.core.auth import create_access_token
from backend.app.models.study_material import (
    MCQOption,
    MCQQuestion,
    QuizAttempt,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.repositories.study_material_repository import StudyMaterialRepository


@pytest.fixture
def auth_context(db_session):
    """Sets up primary user, workspace, and bearer auth headers."""
    user = User(
        id=uuid.uuid4(),
        email=f"c89_user_{uuid.uuid4().hex[:6]}@knovera.test",
        password_hash="pw_hash_test",
        display_name="C8.9 Tester",
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    workspace = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name="C8.9 History Workspace",
    )
    db_session.add(workspace)
    db_session.flush()

    token = create_access_token(user_id=str(user.id))
    headers = {"Authorization": f"Bearer {token}"}
    return {"user": user, "workspace": workspace, "headers": headers}


@pytest.fixture
def seeded_history_attempts(db_session, auth_context):
    """Seeds multiple evaluated and in-progress attempts with differing scores and titles."""
    user = auth_context["user"]
    ws = auth_context["workspace"]
    repo = StudyMaterialRepository(db_session)

    # Question for attempts
    mcq = MCQQuestion(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        question_text="Sample history question",
        difficulty="easy",
        correct_option_id="A",
        explanation="Sample history explanation",
        is_active=True,
    )
    db_session.add(mcq)
    db_session.flush()

    now = datetime.now(timezone.utc)

    # Attempt 1: Evaluated 100%
    att1 = repo.create_quiz_attempt(
        workspace_id=ws.id,
        user_id=user.id,
        title="Calculus Quiz Alpha",
        total_questions=1,
        questions_order=[{"id": str(mcq.id), "type": "mcq"}],
    )
    repo.finalize_quiz_attempt(
        attempt_id=att1.id,
        correct_count=1,
        score_percentage=100.0,
        evaluation_summary={"results": []},
    )

    # Attempt 2: Evaluated 50%
    att2 = repo.create_quiz_attempt(
        workspace_id=ws.id,
        user_id=user.id,
        title="Physics Mechanics Quiz",
        total_questions=2,
        questions_order=[{"id": str(mcq.id), "type": "mcq"}],
    )
    repo.finalize_quiz_attempt(
        attempt_id=att2.id,
        correct_count=1,
        score_percentage=50.0,
        evaluation_summary={"results": []},
    )

    # Attempt 3: In-Progress
    att3 = repo.create_quiz_attempt(
        workspace_id=ws.id,
        user_id=user.id,
        title="Chemistry Bonding Quiz",
        total_questions=3,
        questions_order=[{"id": str(mcq.id), "type": "mcq"}],
    )

    return {
        "mcq": mcq,
        "att1": att1,
        "att2": att2,
        "att3": att3,
    }


def test_list_quiz_history_filtering_and_sorting(
    test_client: TestClient,
    auth_context,
    seeded_history_attempts,
):
    """Tests filtering by status, search string, and sorting by score/date."""
    ws = auth_context["workspace"]
    headers = auth_context["headers"]

    # 1. List all attempts (3 total)
    resp = test_client.get(f"/api/v1/workspaces/{ws.id}/quiz-history", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # 2. Filter by status: evaluated (2 total)
    resp_eval = test_client.get(
        f"/api/v1/workspaces/{ws.id}/quiz-history?status=evaluated",
        headers=headers,
    )
    assert resp_eval.status_code == 200
    assert resp_eval.json()["total"] == 2

    # 3. Filter by search: "Calculus" (1 total)
    resp_search = test_client.get(
        f"/api/v1/workspaces/{ws.id}/quiz-history?search=Calculus",
        headers=headers,
    )
    assert resp_search.status_code == 200
    assert resp_search.json()["total"] == 1
    assert resp_search.json()["items"][0]["title"] == "Calculus Quiz Alpha"

    # 4. Sort by score_percentage desc
    resp_sort = test_client.get(
        f"/api/v1/workspaces/{ws.id}/quiz-history?status=evaluated&sort_by=score_percentage&sort_order=desc",
        headers=headers,
    )
    assert resp_sort.status_code == 200
    items = resp_sort.json()["items"]
    assert items[0]["score_percentage"] == 100.0
    assert items[1]["score_percentage"] == 50.0


def test_quiz_history_summary_metrics(
    test_client: TestClient,
    auth_context,
    seeded_history_attempts,
):
    """Tests summary computation: averages, accuracy rates, and attempt breakdown."""
    ws = auth_context["workspace"]
    headers = auth_context["headers"]

    resp = test_client.get(
        f"/api/v1/workspaces/{ws.id}/quiz-history/summary",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_attempts"] == 3
    assert data["completed_attempts"] == 2
    assert data["in_progress_attempts"] == 1
    # Average of 100.0 and 50.0 = 75.0
    assert data["average_score"] == 75.0
    # Total questions answered = 1 (from att1) + 2 (from att2) = 3
    # Total correct = 1 (from att1) + 1 (from att2) = 2
    # Overall correct rate = (2 / 3) * 100 = 66.67%
    assert data["total_questions_answered"] == 3
    assert data["total_correct_answers"] == 2
    assert data["overall_correct_rate"] == 66.67


def test_quiz_history_trends(
    test_client: TestClient,
    auth_context,
    seeded_history_attempts,
):
    """Tests extraction of chronological score points for progress graphing."""
    ws = auth_context["workspace"]
    headers = auth_context["headers"]

    resp = test_client.get(
        f"/api/v1/workspaces/{ws.id}/quiz-history/trends",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "trends" in data
    trends = data["trends"]
    assert len(trends) == 2  # Only evaluated attempts are plotted
    scores = [t["score_percentage"] for t in trends]
    assert 100.0 in scores
    assert 50.0 in scores


def test_retake_quiz_attempt_creates_fresh_session(
    test_client: TestClient,
    auth_context,
    seeded_history_attempts,
):
    """Tests that retaking a quiz clones questions without modifying original attempt."""
    ws = auth_context["workspace"]
    headers = auth_context["headers"]
    original_att = seeded_history_attempts["att1"]

    resp = test_client.post(
        f"/api/v1/workspaces/{ws.id}/quiz-attempts/{original_att.id}/retake",
        headers=headers,
    )
    assert resp.status_code == 201
    new_att = resp.json()

    # Brand new attempt ID
    assert new_att["id"] != str(original_att.id)
    assert new_att["title"] == "Retake: Calculus Quiz Alpha"
    assert new_att["status"] == "in_progress"
    assert new_att["total_questions"] == original_att.total_questions
    assert new_att["answered_count"] == 0

    # Verify original attempt remains completed and intact
    resp_orig = test_client.get(
        f"/api/v1/workspaces/{ws.id}/quiz-attempts/{original_att.id}/results",
        headers=headers,
    )
    assert resp_orig.status_code == 200
    assert resp_orig.json()["score_percentage"] == 100.0
    assert resp_orig.json()["status"] == "evaluated"
