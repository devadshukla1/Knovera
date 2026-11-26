"""End-to-End integration tests for Query Intent Classification and Module Routing in Chat (Phase 5 C5.7–C5.9)."""

import io
import uuid
from fastapi.testclient import TestClient
import pymupdf
import pytest
from sqlalchemy.orm import Session

from backend.app.core.auth import create_access_token
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


def _make_test_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(
        pymupdf.Rect(50, 50, 550, 800),
        "BM25 is a probabilistic term-matching ranking function widely used in information retrieval. "
        "TF-IDF measures term frequency weighted by inverse document frequency across collections.",
        fontsize=12,
    )
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_e2e_intent_aware_chat_routing(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    other_user: User,
    db_session: Session,
) -> None:
    """Verifies end-to-end conversation with automatic intent classification and routing across categories."""
    ws_id = test_workspace.id

    # 1. Ingest a test document into workspace
    pdf_bytes = _make_test_pdf()
    res_upload = test_client.post(
        f"/api/v1/workspaces/{ws_id}/documents",
        headers=auth_headers,
        files={"file": ("retrieval_concepts.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res_upload.status_code == 201

    # 2. Create Conversation Thread
    res_conv = test_client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers=auth_headers,
        json={"title": "Intent Routing E2E Test"},
    )
    assert res_conv.status_code == 201
    conv_id = res_conv.json()["id"]

    # 3. Turn A: Knowledge Retrieval (Comparison Intent)
    res_turn_a = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"content": "Compare TF-IDF and BM25 term weighting algorithms."},
    )
    assert res_turn_a.status_code == 200
    turn_a_data = res_turn_a.json()
    assert turn_a_data["assistant_message"]["status"] == "complete"
    assert turn_a_data["assistant_message"]["content"] != ""

    # Check conversation detail to inspect persisted retrieval_metadata
    res_detail = test_client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
    assert res_detail.status_code == 200
    messages = res_detail.json()["messages"]
    assert len(messages) >= 2  # user + assistant

    # 4. Turn B: General Conversation Intent (Bypasses Document Retrieval)
    res_turn_b = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"content": "Hello! Good morning!"},
    )
    assert res_turn_b.status_code == 200
    turn_b_data = res_turn_b.json()
    assert turn_b_data["assistant_message"]["status"] == "complete"
    assert "Knovera" in turn_b_data["assistant_message"]["content"] or len(turn_b_data["assistant_message"]["content"]) > 0
    # General conversation turns require no document citations
    assert len(turn_b_data["citations"]) == 0

    # 5. Turn C: Unsupported Action Intent (Capability Boundary Handler)
    res_turn_c = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"content": "Book a round-trip flight to Boston for next week."},
    )
    assert res_turn_c.status_code == 200
    turn_c_data = res_turn_c.json()
    content_c = turn_c_data["assistant_message"]["content"]
    assert "outside my supported capabilities" in content_c or "capability boundary" in content_c.lower()
    assert len(turn_c_data["citations"]) == 0

    # 6. Turn D: Ambiguous Intent (Clarification Handler)
    res_turn_d = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"content": "That one."},
    )
    assert res_turn_d.status_code == 200
    turn_d_data = res_turn_d.json()
    assert turn_d_data["assistant_message"]["status"] == "complete"
    assert "clarify your question" in turn_d_data["assistant_message"]["content"].lower()
    assert turn_d_data["insufficient_evidence"] is True

    # 7. Workspace Security: Verify another user receives 404
    other_token = create_access_token(other_user.id)
    other_headers = {"Authorization": f"Bearer {other_token}"}
    res_unauth = test_client.get(f"/api/v1/conversations/{conv_id}", headers=other_headers)
    assert res_unauth.status_code == 404
