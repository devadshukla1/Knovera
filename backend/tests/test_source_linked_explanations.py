"""Tests for Source-Linked Explanations and Anti-Cheat Shielding (Phase 8: C8.8)."""

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.core.auth import create_access_token
from backend.app.main import app
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.study_material import (
    MCQOption,
    MCQQuestion,
    QuizAttempt,
    QuizAttemptAnswer,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.repositories.study_material_repository import StudyMaterialRepository


@pytest.fixture
def auth_context(db_session):
    """Sets up primary user, workspace, and bearer auth headers."""
    user = User(
        id=uuid.uuid4(),
        email=f"c88_user_{uuid.uuid4().hex[:6]}@knovera.test",
        password_hash="pw_hash_test",
        display_name="C8.8 Tester",
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    workspace = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name="C8.8 Workspace",
    )
    db_session.add(workspace)
    db_session.flush()

    token = create_access_token(user_id=str(user.id))
    headers = {"Authorization": f"Bearer {token}"}
    return {"user": user, "workspace": workspace, "headers": headers}


@pytest.fixture
def seeded_quiz_with_sources(db_session, auth_context):
    """Seeds document, chunk, MCQ with source references, and an active in-progress quiz attempt."""
    user = auth_context["user"]
    ws = auth_context["workspace"]

    doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="neural_networks_guide.pdf",
        storage_key=f"storage/{uuid.uuid4().hex}/nn.pdf",
        media_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=10240,
        sha256=uuid.uuid4().hex,
        processing_status="completed",
    )
    db_session.add(doc)
    db_session.flush()

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc.id,
        chunk_index=0,
        page_start=3,
        page_end=3,
        content="Backpropagation calculates the gradient of the loss function with respect to weights using the chain rule.",
        content_hash=uuid.uuid4().hex,
        token_count=18,
        parser_version="1.0.0",
        cleaning_version="1.0.0",
        chunking_version="1.0.0",
    )
    db_session.add(chunk)
    db_session.flush()

    mcq = MCQQuestion(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        question_text="What does backpropagation compute?",
        difficulty="medium",
        correct_option_id="A",
        explanation="Backpropagation calculates weight gradients using the chain rule.",
        source_references=[
            {
                "document_id": str(doc.id),
                "document_title": doc.original_filename,
                "chunk_id": str(chunk.id),
                "chunk_index": 0,
                "page_number": 3,
                "excerpt": "Backpropagation calculates the gradient of the loss function...",
                "start_char_offset": 0,
                "end_char_offset": 60,
            }
        ],
        is_active=True,
    )
    db_session.add(mcq)
    db_session.flush()

    opt_a = MCQOption(
        id=uuid.uuid4(),
        question_id=mcq.id,
        option_id="A",
        option_text="Gradients of the loss function",
        is_correct=True,
    )
    opt_b = MCQOption(
        id=uuid.uuid4(),
        question_id=mcq.id,
        option_id="B",
        option_text="Number of neurons",
        is_correct=False,
    )
    db_session.add_all([opt_a, opt_b])
    db_session.flush()

    repo = StudyMaterialRepository(db_session)
    attempt = repo.create_quiz_attempt(
        workspace_id=ws.id,
        user_id=user.id,
        title="Neural Networks Assessment",
        total_questions=1,
        questions_order=[{"id": str(mcq.id), "type": "mcq"}],
    )

    return {
        "doc": doc,
        "chunk": chunk,
        "mcq": mcq,
        "attempt": attempt,
    }


def test_anti_cheat_shielding_blocks_explanations_during_quiz(
    test_client: TestClient,
    auth_context,
    seeded_quiz_with_sources,
):
    """Enforces 403 Forbidden when requesting explanation or sources while attempt is in progress."""
    ws = auth_context["workspace"]
    headers = auth_context["headers"]
    attempt = seeded_quiz_with_sources["attempt"]
    mcq = seeded_quiz_with_sources["mcq"]

    # Request explanation while in_progress -> MUST FAIL 403
    resp_expl = test_client.get(
        f"/api/v1/workspaces/{ws.id}/quiz-attempts/{attempt.id}/questions/{mcq.id}/explanation",
        headers=headers,
    )
    assert resp_expl.status_code == 403
    assert "Anti-cheat shield active" in resp_expl.json()["detail"]

    # Request sources while in_progress -> MUST FAIL 403
    resp_sources = test_client.get(
        f"/api/v1/workspaces/{ws.id}/quiz-attempts/{attempt.id}/questions/{mcq.id}/sources",
        headers=headers,
    )
    assert resp_sources.status_code == 403
    assert "Anti-cheat shield active" in resp_sources.json()["detail"]


def test_source_linked_explanations_after_evaluation(
    test_client: TestClient,
    auth_context,
    seeded_quiz_with_sources,
):
    """Validates explanation and source citation retrieval after quiz submission."""
    ws = auth_context["workspace"]
    headers = auth_context["headers"]
    attempt = seeded_quiz_with_sources["attempt"]
    mcq = seeded_quiz_with_sources["mcq"]

    # Submit quiz attempt
    submit_payload = {
        "answers": [
            {
                "question_id": str(mcq.id),
                "question_type": "mcq",
                "selected_answer": "A",
            }
        ]
    }
    submit_resp = test_client.post(
        f"/api/v1/workspaces/{ws.id}/quiz-attempts/{attempt.id}/submit",
        json=submit_payload,
        headers=headers,
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "evaluated"

    # Now request explanation -> 200 OK
    resp_expl = test_client.get(
        f"/api/v1/workspaces/{ws.id}/quiz-attempts/{attempt.id}/questions/{mcq.id}/explanation",
        headers=headers,
    )
    assert resp_expl.status_code == 200
    data_expl = resp_expl.json()
    assert data_expl["question_id"] == str(mcq.id)
    assert data_expl["correct_answer"] == "A"
    assert data_expl["learner_answer"] == "A"
    assert data_expl["is_correct"] is True
    assert "chain rule" in data_expl["explanation"]

    # Now request source citations -> 200 OK
    resp_sources = test_client.get(
        f"/api/v1/workspaces/{ws.id}/quiz-attempts/{attempt.id}/questions/{mcq.id}/sources",
        headers=headers,
    )
    assert resp_sources.status_code == 200
    data_sources = resp_sources.json()
    assert data_sources["question_id"] == str(mcq.id)
    assert len(data_sources["source_references"]) == 1
    ref = data_sources["source_references"][0]
    assert ref["document_title"] == "neural_networks_guide.pdf"
    assert ref["page_number"] == 3
    assert "Backpropagation" in ref["excerpt"]


def test_explanation_non_existent_question(
    test_client: TestClient,
    auth_context,
    seeded_quiz_with_sources,
):
    """Validates 404 when querying explanation for a question not in the attempt."""
    ws = auth_context["workspace"]
    headers = auth_context["headers"]
    attempt = seeded_quiz_with_sources["attempt"]

    # Submit attempt first
    test_client.post(
        f"/api/v1/workspaces/{ws.id}/quiz-attempts/{attempt.id}/submit",
        headers=headers,
    )

    non_existent_qid = uuid.uuid4()
    resp = test_client.get(
        f"/api/v1/workspaces/{ws.id}/quiz-attempts/{attempt.id}/questions/{non_existent_qid}/explanation",
        headers=headers,
    )
    assert resp.status_code == 404
