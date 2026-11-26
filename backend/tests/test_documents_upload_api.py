"""Integration and security tests for C2.1 File Upload API and C2.2 PDF Extraction."""

import hashlib
import io
from pathlib import Path
import uuid
from fastapi.testclient import TestClient
import pymupdf
from sqlalchemy.orm import Session

from backend.app.models.document import Document, DocumentPage
from backend.app.models.workspace import Workspace
from backend.app.storage.local import LocalStorageService


def make_pdf_bytes(
    pages_text: list[str],
    password: str | None = None,
) -> bytes:
    """Helper to generate in-memory PDF bytes."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page(width=595, height=842)
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=12)

    if password:
        pdf_bytes = doc.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw=password,
            owner_pw=password,
        )
    else:
        pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_valid_pdf_upload_and_extraction(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
    storage_service: LocalStorageService,
):
    """Verifies complete upload, hashing, storage, and page extraction flow."""
    pdf_bytes = make_pdf_bytes([
        "Page 1: Attention mechanisms and transformers in deep learning.",
        "Page 2: Multi-document retrieval with citation grounding.",
    ])
    expected_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("transformers.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["original_filename"] == "transformers.pdf"
    assert data["file_size_bytes"] == len(pdf_bytes)
    assert data["media_type"] == "application/pdf"
    assert data["page_count"] == 2
    assert data["processing_status"] in ("queued", "ready")
    assert data["processing_stage"] in ("extraction_complete_awaiting_chunking", "awaiting_embeddings", "ready")
    assert data["error_code"] is None

    # Never expose storage keys or absolute paths in public responses
    assert "storage_key" not in data
    assert "resolved_storage_root" not in data

    doc_id = uuid.UUID(data["id"])

    # Verify database persistence
    db_doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert db_doc is not None
    assert db_doc.sha256 == expected_sha256
    assert db_doc.processing_status in ("queued", "ready")
    assert storage_service.exists(db_doc.storage_key)

    # Verify document_pages persistence with 1-based indexing
    pages = (
        db_session.query(DocumentPage)
        .filter(DocumentPage.document_id == doc_id)
        .order_by(DocumentPage.page_number.asc())
        .all()
    )
    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert "Attention mechanisms" in pages[0].extracted_text
    assert pages[1].page_number == 2
    assert "citation grounding" in pages[1].extracted_text


def test_get_document_pages_endpoint(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
):
    """Verifies GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/pages."""
    pdf_bytes = make_pdf_bytes(["Page 1 Content", "Page 2 Content", "Page 3 Content"])

    upload_resp = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("test_pages.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    # Fetch pages
    pages_resp = test_client.get(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_id}/pages",
        headers=auth_headers,
    )
    assert pages_resp.status_code == 200
    pages_data = pages_resp.json()
    assert pages_data["total_pages"] == 3
    assert len(pages_data["pages"]) == 3
    assert pages_data["pages"][0]["page_number"] == 1
    assert pages_data["pages"][1]["page_number"] == 2
    assert pages_data["pages"][2]["page_number"] == 3


def test_unauthenticated_upload_succeeds(
    test_client: TestClient,
    test_workspace: Workspace,
):
    """In local single-user mode, unauthenticated uploads succeed without token."""
    pdf_bytes = make_pdf_bytes(["Sample text"])
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 201
    assert "id" in response.json()


def test_local_single_user_workspace_upload_accessible(
    test_client: TestClient,
    test_workspace: Workspace,
    other_auth_headers: dict[str, str],
):
    """In local single-user mode, workspace permission checks are removed."""
    pdf_bytes = make_pdf_bytes(["Local insertion"])
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=other_auth_headers,
        files={"file": ("local.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 201
    assert "id" in response.json()


def test_local_single_user_document_pages_accessible(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
):
    """In local single-user mode, documents within a valid workspace are accessible."""
    pdf_bytes = make_pdf_bytes(["Research Data"])
    upload_resp = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]

    # In local mode, document detail is accessible
    detail_resp = test_client.get(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_id}",
        headers=other_auth_headers,
    )
    assert detail_resp.status_code == 200

    # In local mode, pages are accessible
    pages_resp = test_client.get(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_id}/pages",
        headers=other_auth_headers,
    )
    assert pages_resp.status_code == 200


def test_unsupported_file_extension_rejected(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
):
    """Files that are not supported formats (.txt, .xlsx) are rejected with HTTP 415."""
    txt_bytes = b"Just plain text notes that are not supported yet."
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("notes.txt", io.BytesIO(txt_bytes), "text/plain")},
    )
    assert response.status_code == 415
    assert response.json()["detail"]["error_code"] == "unsupported_file_type"


def test_fake_pdf_with_invalid_signature_rejected(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
):
    """File named .pdf without %PDF- magic bytes rejected with HTTP 415."""
    fake_bytes = b"Plain text disguised with a .pdf extension"
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("fake.pdf", io.BytesIO(fake_bytes), "application/pdf")},
    )
    assert response.status_code == 415
    assert response.json()["detail"]["error_code"] == "invalid_pdf_signature"


def test_empty_file_upload_rejected(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
):
    """0-byte file rejected with HTTP 400."""
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "empty_file"


def test_oversized_file_rejected_with_413(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    monkeypatch,
):
    """Files exceeding size limit are rejected with HTTP 413."""
    # Temporarily set max upload to 500 bytes for test
    from backend.app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 500)

    pdf_bytes = make_pdf_bytes(["A large page with lots of content that will easily exceed five hundred bytes threshold." * 5])
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("large.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 413
    assert response.json()["detail"]["error_code"] == "file_too_large"


def test_path_traversal_filename_sanitized(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """Filename containing directory traversal characters is sanitized safely."""
    pdf_bytes = make_pdf_bytes(["Safe content inside traversal attempt."])
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("../../etc/passwd.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 201
    clean_name = response.json()["original_filename"]
    assert ".." not in clean_name
    assert "/" not in clean_name
    assert "\\" not in clean_name
    assert clean_name == "passwd.pdf"


def test_unicode_filename_supported(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
):
    """Unicode filenames are preserved practical for display."""
    pdf_bytes = make_pdf_bytes(["Quantum Computing in Chinese"])
    unicode_name = "量子計算研究論文.pdf"
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": (unicode_name, io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 201
    assert response.json()["original_filename"] == unicode_name


def test_scanned_pdf_marked_failed(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """PDF with 0 extractable text returns 422, marks document as failed, retains file."""
    pdf_bytes = make_pdf_bytes(["", ""])  # 2 blank pages (simulating scanned document)
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("scanned.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 422
    data = response.json()["detail"]
    assert data["error_code"] == "no_extractable_text"

    doc_id = uuid.UUID(data["document_id"])
    db_doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert db_doc is not None
    assert db_doc.processing_status == "failed"
    assert db_doc.error_code == "no_extractable_text"
    assert db_doc.error_summary is not None


def test_encrypted_pdf_marked_failed(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """Encrypted PDF returns 422, marks document as failed, retains file."""
    pdf_bytes = make_pdf_bytes(["Encrypted text"], password="mypassword123")
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("protected.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 422
    data = response.json()["detail"]
    assert data["error_code"] == "pdf_encrypted"

    doc_id = uuid.UUID(data["document_id"])
    db_doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert db_doc is not None
    assert db_doc.processing_status == "failed"
    assert db_doc.error_code == "pdf_encrypted"


def test_private_storage_isolation(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    storage_service: LocalStorageService,
):
    """Verifies that uploaded files are placed in storage root and never in public web paths."""
    pdf_bytes = make_pdf_bytes(["Confidential Data"])
    response = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("confidential.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 201

    # Check storage service root is private
    assert "public" not in str(storage_service.root_dir).lower()
    assert "frontend" not in str(storage_service.root_dir).lower()
