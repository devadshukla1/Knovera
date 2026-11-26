"""End-to-End integration test for Knovera Grounded RAG, Citations, and Conversations (Phase 3 C3.7–C3.9).

Verifies the complete flow across multi-format documents (PDF, DOCX, PPTX):
    1. Authenticated user uploads PDF, DOCX, and PPTX documents into a workspace.
    2. User starts a conversation.
    3. User asks questions targeting PDF, DOCX, and PPTX content:
       - Answers are grounded strictly in retrieved context.
       - Citations provide 1-based PDF pages, DOCX sections (no fake pages), and PPTX slides.
       - Citations and messages are committed to PostgreSQL.
    4. Historical conversation and citations are reopened and validated.
    5. A second user is strictly denied access (404) to conversations and citations.
"""

import io
import json
import uuid
import docx
from fastapi.testclient import TestClient
import pptx
import pymupdf
import pytest
from sqlalchemy.orm import Session

from backend.app.core.auth import create_access_token
from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.llm.registry import LLMProviderRegistry
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


def make_test_pdf_bytes(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        p = doc.new_page(width=595, height=842)
        p.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_test_docx_bytes(headings: list[str], paragraphs: list[str]) -> bytes:
    doc = docx.Document()
    for h in headings:
        doc.add_heading(h, level=1)
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_test_pptx_bytes(slides: list[dict]) -> bytes:
    prs = pptx.Presentation()
    blank = prs.slide_layouts[6]
    for s in slides:
        slide = prs.slides.add_slide(blank)
        tx = slide.shapes.add_textbox(pptx.util.Inches(1), pptx.util.Inches(1), pptx.util.Inches(8), pptx.util.Inches(4))
        tf = tx.text_frame
        tf.text = s.get("title", "")
        for b in s.get("bullets", []):
            p = tf.add_paragraph()
            p.text = b
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def test_e2e_multi_format_grounded_conversation_and_citations(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    other_user: User,
    db_session: Session,
):
    ws_id = test_workspace.id

    # 1. Ingest PDF Document
    pdf_bytes = make_test_pdf_bytes([
        "Superconducting qubits operate at cryogenic temperatures near absolute zero to preserve quantum coherence.",
    ])
    res_pdf = test_client.post(
        f"/api/v1/workspaces/{ws_id}/documents",
        headers=auth_headers,
        files={"file": ("quantum_computing.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res_pdf.status_code == 201

    # 2. Ingest DOCX Document
    docx_bytes = make_test_docx_bytes(
        headings=["Feature Store Architecture"],
        paragraphs=["Feature stores serve unified online and offline features for training and real-time inference."],
    )
    res_docx = test_client.post(
        f"/api/v1/workspaces/{ws_id}/documents",
        headers=auth_headers,
        files={"file": ("ml_engineering.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res_docx.status_code == 201

    # 3. Ingest PPTX Document
    pptx_bytes = make_test_pptx_bytes([
        {
            "title": "Systolic Array Computing",
            "bullets": ["Tensor Processing Units accelerate matrix multiplication using systolic array architectures."],
        }
    ])
    res_pptx = test_client.post(
        f"/api/v1/workspaces/{ws_id}/documents",
        headers=auth_headers,
        files={"file": ("ai_hardware.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert res_pptx.status_code == 201

    # 4. Create Conversation
    res_conv = test_client.post(
        f"/api/v1/workspaces/{ws_id}/conversations",
        headers=auth_headers,
        json={"title": "Multi-Document Research Chat"},
    )
    assert res_conv.status_code == 201
    conv_id = res_conv.json()["id"]

    # 5. Query 1: Ask about PDF content
    pdf_id = res_pdf.json()["id"]
    pdf_answer_json = json.dumps({
        "answer": "Superconducting qubits operate at cryogenic temperatures near absolute zero [S1].",
        "claims": [{"text": "Superconducting qubits operate near absolute zero.", "source_ids": ["S1"]}],
        "limitations": [],
        "insufficient_evidence": False,
    })
    mock_provider = MockLLMProvider(default_response=pdf_answer_json)
    LLMManager.get_instance().registry.register("mock", mock_provider)

    res_turn1 = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={
            "content": "At what temperatures do superconducting qubits operate?",
            "document_ids": [pdf_id],
        },
    )
    assert res_turn1.status_code == 200
    turn1_data = res_turn1.json()
    assert "[S1]" in turn1_data["assistant_message"]["content"]
    assert len(turn1_data["citations"]) >= 1
    cit1 = turn1_data["citations"][0]
    assert cit1["document_name"] == "quantum_computing.pdf"
    assert cit1["location_type"] == "pdf_pages"
    assert cit1["location_label"] == "Page 1"
    assert cit1["page_start"] == 1
    pdf_citation_id = cit1["citation_id"]

    # 6. Query 2: Ask about DOCX content
    docx_id = res_docx.json()["id"]
    docx_answer_json = json.dumps({
        "answer": "Feature stores serve unified online and offline features for training and inference [S1].",
        "claims": [{"text": "Feature stores serve unified online and offline features.", "source_ids": ["S1"]}],
        "limitations": [],
        "insufficient_evidence": False,
    })
    mock_provider.set_response(docx_answer_json)

    res_turn2 = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={
            "content": "What is the function of a feature store?",
            "document_ids": [docx_id],
        },
    )
    assert res_turn2.status_code == 200
    turn2_data = res_turn2.json()
    assert len(turn2_data["citations"]) >= 1
    cit2 = turn2_data["citations"][0]
    assert cit2["document_name"] == "ml_engineering.docx"
    assert cit2["location_type"] == "docx_section"
    assert "Section" in cit2["location_label"]
    assert cit2["page_start"] is None  # Verifies DOCX never invents fake page numbers!

    # 7. Query 3: Ask about PPTX content
    pptx_id = res_pptx.json()["id"]
    pptx_answer_json = json.dumps({
        "answer": "Tensor Processing Units use systolic arrays to accelerate matrix multiplication [S1].",
        "claims": [{"text": "TPUs use systolic array architectures.", "source_ids": ["S1"]}],
        "limitations": [],
        "insufficient_evidence": False,
    })
    mock_provider.set_response(pptx_answer_json)

    res_turn3 = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={
            "content": "How do Tensor Processing Units accelerate matrix multiplication?",
            "document_ids": [pptx_id],
        },
    )
    assert res_turn3.status_code == 200
    turn3_data = res_turn3.json()
    assert len(turn3_data["citations"]) >= 1
    cit3 = turn3_data["citations"][0]
    assert cit3["document_name"] == "ai_hardware.pptx"
    assert cit3["location_type"] == "pptx_slide"
    assert cit3["location_label"] == "Slide 1"
    assert cit3["slide_number"] == 1

    # 8. Reopen Conversation Detail & Verify Chronological History
    res_hist = test_client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert hist_data["conversation"]["title"] == "Multi-Document Research Chat"
    messages = hist_data["messages"]
    assert len(messages) == 6  # 3 user messages + 3 assistant responses

    # Check strict alternating chronological user/assistant turns
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[3]["role"] == "assistant"
    assert messages[4]["role"] == "user"
    assert messages[5]["role"] == "assistant"
    assert len(messages[1]["citations"]) >= 1
    assert len(messages[3]["citations"]) >= 1
    assert len(messages[5]["citations"]) >= 1

    # 9. Reopen Citation via GET /api/v1/citations/{id}
    res_cit = test_client.get(f"/api/v1/citations/{pdf_citation_id}", headers=auth_headers)
    assert res_cit.status_code == 200
    cit_detail = res_cit.json()
    assert cit_detail["citation_id"] == pdf_citation_id
    assert cit_detail["document_name"] == "quantum_computing.pdf"
    assert "cryogenic temperatures" in cit_detail["excerpt"]

    # 10. Security Boundary: Second User Cannot Access Conversation or Citation
    other_token = create_access_token(other_user.id)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Attempt to access User 1's conversation
    res_unauth_conv = test_client.get(f"/api/v1/conversations/{conv_id}", headers=other_headers)
    assert res_unauth_conv.status_code == 404

    # Attempt to access User 1's citation
    res_unauth_cit = test_client.get(f"/api/v1/citations/{pdf_citation_id}", headers=other_headers)
    assert res_unauth_cit.status_code == 404

    # Attempt to submit message to User 1's conversation
    res_unauth_msg = test_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=other_headers,
        json={"content": "Malicious intrusion attempt"},
    )
    assert res_unauth_msg.status_code == 404
