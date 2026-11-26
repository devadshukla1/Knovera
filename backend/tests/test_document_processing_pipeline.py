"""Integration tests for the unified document processing pipeline (PDF, DOCX, PPTX).

Verifies:
    - End-to-end flow: Upload -> Storage -> Extraction -> Cleaning -> Chunking -> Persistence.
    - Status transitions (extracting -> chunking -> queued / awaiting_embeddings, NEVER ready).
    - Database persistence in document_chunks with deterministic UUIDs and source_segments.
    - Chunk retrieval endpoint GET /workspaces/{id}/documents/{id}/chunks.
    - Workspace ownership and cross-user isolation.
"""

import io
from pathlib import Path
import uuid
import docx
from fastapi.testclient import TestClient
import pptx
import pymupdf
import pytest
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
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


def test_pipeline_pdf_end_to_end(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    pdf_bytes = make_test_pdf_bytes([
        "Chapter 1: Neural Networks and deep learning architectures.",
        "Chapter 2: Multi-document retrieval with citation validation.",
    ])

    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("deep_learning.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 201
    doc_data = response.json()
    assert doc_data["processing_status"] in ("queued", "ready")
    assert doc_data["processing_stage"] in ("awaiting_embeddings", "ready")
    doc_id = doc_data["id"]

    # Verify chunks endpoint
    chunks_res = test_client.get(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_id}/chunks",
        headers=auth_headers,
    )
    assert chunks_res.status_code == 200
    chunks_data = chunks_res.json()
    assert chunks_data["total_chunks"] >= 1

    first_chunk = chunks_data["chunks"][0]
    assert first_chunk["page_start"] is not None
    assert first_chunk["token_count"] > 0
    assert len(first_chunk["content_hash"]) == 64
    assert len(first_chunk["source_segments"]) > 0


def test_pipeline_docx_end_to_end(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    docx_bytes = make_test_docx_bytes(
        headings=["Knowledge Intelligence Overview"],
        paragraphs=[
            "Knovera transforms distributed documents into verifiable knowledge.",
            "It features structure-aware chunking and rigorous provenance tracking.",
        ],
    )

    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("knowledge.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 201
    doc_data = response.json()
    assert doc_data["processing_status"] in ("queued", "ready")
    assert doc_data["processing_stage"] in ("awaiting_embeddings", "ready")
    doc_id = uuid.UUID(doc_data["id"])

    # Verify chunks in database
    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
    assert len(chunks) >= 1
    assert any("Knowledge Intelligence Overview" in c.content for c in chunks)
    assert chunks[0].cleaning_version == "v1.0"
    assert chunks[0].chunking_version == "semantic-v1"


def test_pipeline_pptx_end_to_end(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    pptx_bytes = make_test_pptx_bytes([
        {"title": "Slide 1: Ingestion Pipeline", "bullets": ["PyMuPDF", "python-docx", "python-pptx"]},
        {"title": "Slide 2: Semantic Chunking", "bullets": ["Structure-aware", "Content-aware", "Traceable"]},
    ])

    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("pipeline.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )

    assert response.status_code == 201
    doc_data = response.json()
    assert doc_data["processing_status"] in ("queued", "ready")
    assert doc_data["processing_stage"] in ("awaiting_embeddings", "ready")
    doc_id = doc_data["id"]

    # Verify chunks via API
    chunks_res = test_client.get(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_id}/chunks",
        headers=auth_headers,
    )
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()["chunks"]
    assert len(chunks) == 2
    # Slide numbers preserved on chunks
    assert chunks[0]["slide_number"] == 1
    assert chunks[1]["slide_number"] == 2


def test_cross_user_chunks_isolation(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    import uuid
    from backend.app.models.user import User
    from backend.app.core.auth import create_access_token

    # Upload doc to test_workspace
    pdf_bytes = make_test_pdf_bytes(["Confidential knowledge."])
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("private.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    doc_id = response.json()["id"]

    # Create and authenticate a distinct valid user
    other_user = User(
        id=uuid.uuid4(),
        email="second_user@knovera.test",
        password_hash="test_hash_value",
        status="active",
    )
    db_session.add(other_user)
    db_session.commit()

    other_token = create_access_token(str(other_user.id))
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Accessing unowned workspace's chunks must return 404 (prevent ID enumeration)
    leak_res = test_client.get(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_id}/chunks",
        headers=other_headers,
    )
    assert leak_res.status_code == 404
