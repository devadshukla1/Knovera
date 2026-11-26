"""Tests for Knovera conversation management, message history, and idempotency (Phase 3 C3.9)."""

from datetime import datetime, timedelta, timezone
import json
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from backend.app.core.auth import create_access_token
from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.llm.registry import LLMProviderRegistry
from backend.app.models.conversation import Conversation
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.message import Message
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.rag.orchestration.answer_generator import GroundedAnswerService


import io
import pymupdf


def make_test_pdf_bytes(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        p = doc.new_page(width=595, height=842)
        p.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def ingest_test_pdf(test_client: TestClient, workspace_id: uuid.UUID, auth_headers: dict[str, str], text: str) -> None:
    pdf_bytes = make_test_pdf_bytes([text])
    res = test_client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=auth_headers,
        files={"file": ("sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res.status_code == 201


def test_create_and_list_conversations(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    other_user: User,
):
    """Verifies conversation creation, listing, pagination, and workspace isolation."""
    ws_id = test_workspace.id

    # 1. Create conversation with custom title
    res_create = test_client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers=auth_headers,
        json={"title": "Reinforcement Learning Chat", "source_scope": {}},
    )
    assert res_create.status_code == 201
    conv_data = res_create.json()
    assert conv_data["title"] == "Reinforcement Learning Chat"
    conv_id = conv_data["id"]

    # 2. List conversations in workspace
    res_list = test_client.get(
        f"/api/v1/workspaces/{ws_id}/conversations?limit=10&offset=0",
        headers=auth_headers,
    )
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] >= 1
    assert any(c["id"] == conv_id for c in list_data["items"])

    # 3. Other user cannot list or view conversations (Security boundary -> 404)
    other_token = create_access_token(other_user.id)
    other_headers = {"Authorization": f"Bearer {other_token}"}
    res_other = test_client.get(f"/api/v1/workspaces/{ws_id}/conversations", headers=other_headers)
    assert res_other.status_code == 404


def test_submit_message_chat_turn_lifecycle_and_auto_title(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """Verifies message submission, grounded answer generation, citations, and first-query auto-title."""
    ingest_test_pdf(test_client, test_workspace.id, auth_headers, "Reinforcement learning agents optimize expected cumulative reward using policy gradients.")

    # 1. Create conversation with default title
    res_conv = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/conversations",
        headers=auth_headers,
        json={},
    )
    assert res_conv.status_code == 201
    conv_id = res_conv.json()["id"]

    # 2. Configure mock provider for generation
    mock_resp = json.dumps({
        "answer": "Reinforcement learning optimizes cumulative reward [S1].",
        "claims": [{"text": "Reinforcement learning optimizes cumulative reward.", "source_ids": ["S1"]}],
        "limitations": [],
        "insufficient_evidence": False,
    })
    mock_provider = MockLLMProvider(default_response=mock_resp)
    LLMManager.get_instance().registry.register("mock", mock_provider)

    # 3. Submit question
    req_id = str(uuid.uuid4())
    res_msg = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={
            "content": "How do reinforcement learning agents learn?",
            "client_request_id": req_id,
        },
    )
    assert res_msg.status_code == 200
    turn_data = res_msg.json()
    assert turn_data["conversation_id"] == conv_id
    assert turn_data["user_message"]["content"] == "How do reinforcement learning agents learn?"
    assert turn_data["user_message"]["status"] == "complete"
    assert turn_data["assistant_message"]["status"] == "complete"
    assert "cumulative reward" in turn_data["assistant_message"]["content"]
    assert len(turn_data["citations"]) >= 1

    # 4. Check conversation title updated automatically from first query
    res_detail = test_client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert "reinforcement learning" in detail["conversation"]["title"].lower()
    assert len(detail["messages"]) == 2  # 1 user + 1 assistant


def test_idempotency_returns_existing_turn_without_regenerating(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """Verifies submitting identical client_request_id returns the existing response."""
    ingest_test_pdf(test_client, test_workspace.id, auth_headers, "Reinforcement learning agents optimize expected cumulative reward using policy gradients.")

    res_conv = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/conversations",
        headers=auth_headers,
        json={"title": "Idempotency Test"},
    )
    conv_id = res_conv.json()["id"]

    mock_resp = json.dumps({
        "answer": "Answer text [S1].",
        "claims": [{"text": "Answer text.", "source_ids": ["S1"]}],
        "limitations": [],
        "insufficient_evidence": False,
    })
    mock_provider = MockLLMProvider(default_response=mock_resp)
    LLMManager.get_instance().registry.register("mock", mock_provider)

    client_req_id = str(uuid.uuid4())

    # 1. First submission
    res_1 = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"content": "Reinforcement learning policy gradients", "client_request_id": client_req_id},
    )
    assert res_1.status_code == 200
    calls_after_first = len(mock_provider.call_history)
    assert calls_after_first >= 1

    # 2. Second submission with SAME client_request_id
    res_2 = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"content": "Reinforcement learning policy gradients", "client_request_id": client_req_id},
    )
    assert res_2.status_code == 200
    assert len(mock_provider.call_history) == calls_after_first  # Zero additional LLM calls!
    assert res_1.json()["assistant_message"]["id"] == res_2.json()["assistant_message"]["id"]


def test_preserves_user_message_on_generation_failure(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """Verifies user query is saved with assistant marked 'failed' if LLM fails."""
    ingest_test_pdf(test_client, test_workspace.id, auth_headers, "Reinforcement learning agents optimize expected cumulative reward using policy gradients.")

    res_conv = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/conversations",
        headers=auth_headers,
        json={"title": "Failure Resilience Test"},
    )
    conv_id = res_conv.json()["id"]

    # Configure mock provider to simulate authentication failure
    mock_provider = MockLLMProvider(simulate_error="auth")
    LLMManager.get_instance().registry.register("mock", mock_provider)

    # Submit message expecting failure
    res = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"content": "Reinforcement learning agents query that fails LLM"},
    )
    assert res.status_code == 500

    # Verify user message was preserved and assistant marked failed
    res_hist = test_client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
    assert res_hist.status_code == 200
    messages = res_hist.json()["messages"]
    assert len(messages) == 2
    user_msg = messages[0]
    assist_msg = messages[1]
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "Reinforcement learning agents query that fails LLM"
    assert user_msg["status"] == "complete"
    assert assist_msg["role"] == "assistant"
    assert assist_msg["status"] == "failed"
    assert assist_msg["failure_code"] is not None


def test_concurrent_generation_guard_and_stale_recovery(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """Verifies that active pending message raises 409 Conflict, but stale pending message (>300s) is recovered."""
    ingest_test_pdf(test_client, test_workspace.id, auth_headers, "Reinforcement learning agents optimize expected cumulative reward using policy gradients.")

    # 1. Create conversation with an active pending message
    conv = Conversation(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        created_by_user_id=test_workspace.owner_user_id,
        title="Pending Guard Test",
    )
    recent_pending = Message(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        conversation_id=conv.id,
        role="assistant",
        content="",
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([conv, recent_pending])
    db_session.commit()

    # 2. Submitting while generation is pending returns 409 Conflict
    res_conflict = test_client.post(
        f"/api/v1/conversations/{conv.id}/messages",
        headers=auth_headers,
        json={"content": "Another question while pending"},
    )
    assert res_conflict.status_code == 409
    assert "currently in progress" in res_conflict.json()["detail"]

    # 3. Simulate stale pending message (>300 seconds old)
    recent_pending.created_at = datetime.now(timezone.utc) - timedelta(seconds=350)
    db_session.commit()

    mock_resp = json.dumps({
        "answer": "Recovered answer [S1].",
        "claims": [{"text": "Recovered answer.", "source_ids": ["S1"]}],
        "limitations": [],
        "insufficient_evidence": False,
    })
    mock_provider = MockLLMProvider(default_response=mock_resp)
    LLMManager.get_instance().registry.register("mock", mock_provider)

    # 4. Submission recovers stale message and succeeds
    res_recovered = test_client.post(
        f"/api/v1/conversations/{conv.id}/messages",
        headers=auth_headers,
        json={"content": "Question after stale recovery"},
    )
    assert res_recovered.status_code == 200
    assert res_recovered.json()["assistant_message"]["status"] == "complete"
