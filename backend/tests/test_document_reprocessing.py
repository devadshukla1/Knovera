"""Tests for idempotent document reprocessing and job history API (Chunk C2.7 & C2.8)."""

from datetime import datetime, timezone
import io
import uuid
import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.workspace import Workspace


def make_pdf_bytes(pages: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_reprocess_document_idempotency_and_chunk_replacement(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """Reprocessing a document regenerates chunks idempotently without duplicates."""
    pdf_bytes = make_pdf_bytes([
        "Section 1: Initial introduction to Knovera intelligence pipeline.",
        "Section 2: Detailed architecture of document extraction and chunking.",
    ])

    # 1. Initial upload
    upload_res = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("reprocess_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Check initial chunks count
    initial_chunks = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == uuid.UUID(doc_id))
        .all()
    )
    initial_chunk_count = len(initial_chunks)
    assert initial_chunk_count > 0

    # 2. Trigger Reprocess API
    reprocess_res = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_id}/reprocess",
        headers=auth_headers,
    )
    assert reprocess_res.status_code == 200
    reprocess_data = reprocess_res.json()
    assert reprocess_data["processing_status"] in ("queued", "ready")
    assert reprocess_data["processing_stage"] in ("awaiting_embeddings", "ready")

    # Check chunks count after reprocess -> MUST NOT DUPLICATE
    after_chunks = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == uuid.UUID(doc_id))
        .all()
    )
    assert len(after_chunks) == initial_chunk_count

    # 3. Trigger Reprocess API a second time -> idempotent
    reprocess_res_2 = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_id}/reprocess",
        headers=auth_headers,
    )
    assert reprocess_res_2.status_code == 200

    after_chunks_2 = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == uuid.UUID(doc_id))
        .all()
    )
    assert len(after_chunks_2) == initial_chunk_count


def test_document_jobs_endpoint(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
):
    """GET /jobs returns complete execution history and stage metrics."""
    pdf_bytes = make_pdf_bytes(["Test document content for jobs endpoint verification."])

    # Upload document
    upload_res = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("jobs_api.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Reprocess once to create a second job entry
    reprocess_res = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_id}/reprocess",
        headers=auth_headers,
    )
    assert reprocess_res.status_code == 200

    # Query jobs endpoint
    jobs_res = test_client.get(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_id}/jobs",
        headers=auth_headers,
    )
    assert jobs_res.status_code == 200
    jobs_data = jobs_res.json()
    assert jobs_data["document_id"] == doc_id
    assert jobs_data["total_jobs"] >= 2
    assert len(jobs_data["jobs"]) >= 2

    latest_job = jobs_data["jobs"][0]
    assert latest_job["status"] == "completed"
    assert latest_job["stage"] in ("awaiting_embeddings", "ready")
    assert latest_job["pipeline_version"] == "v1.0"
    assert "total_duration_ms" in latest_job["processing_metrics"]


def test_reprocess_nonexistent_document_returns_404(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
):
    """Reprocessing a non-existent document ID returns HTTP 404."""
    random_id = uuid.uuid4()
    res = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{random_id}/reprocess",
        headers=auth_headers,
    )
    assert res.status_code == 404
