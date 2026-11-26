"""Tests for workspace-scoped duplicate document detection and handling (Chunk C2.8)."""

from datetime import datetime, timezone
import hashlib
import io
import uuid
import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.ingestion.errors.taxonomy import DuplicateDocumentError
from backend.app.ingestion.services.duplicate_service import DuplicateDetectionService
from backend.app.models.document import Document
from backend.app.models.workspace import Workspace


def make_pdf_bytes(pages: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_duplicate_upload_in_same_workspace_returns_409(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
):
    """Uploading the exact same file twice into the same workspace returns HTTP 409 Conflict."""
    pdf_bytes = make_pdf_bytes(["Knovera Duplicate Detection Test - Content A"])

    # First upload -> 201 Created
    res1 = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("report_v1.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res1.status_code == 201
    doc1_id = res1.json()["id"]

    # Second upload with different filename but identical content -> 409 Conflict
    res2 = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("report_copy.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res2.status_code == 409
    err_body = res2.json()
    assert err_body["detail"]["error_code"] == "duplicate_document"
    assert err_body["detail"]["details"]["existing_document_id"] == doc1_id


def test_duplicate_file_in_different_workspace_succeeds(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """The same file uploaded to two distinct workspaces succeeds (workspace-scoped uniqueness)."""
    # Create second workspace for the same user
    ws2 = Workspace(
        id=uuid.uuid4(),
        owner_user_id=test_workspace.owner_user_id,
        name="Workspace 2 - Research",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(ws2)
    db_session.commit()

    pdf_bytes = make_pdf_bytes(["Knovera Cross-Workspace Isolation Test Content"])

    # Upload to workspace 1
    res1 = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("shared_paper.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res1.status_code == 201

    # Upload to workspace 2 -> MUST SUCCEED (201 Created)
    res2 = test_client.post(
        f"/api/v1/workspaces/{ws2.id}/documents",
        headers=auth_headers,
        files={"file": ("shared_paper.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res2.status_code == 201
    assert res1.json()["id"] != res2.json()["id"]


def test_duplicate_allowed_if_previous_document_soft_deleted(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """A file can be re-uploaded if the previously matching document has been soft-deleted."""
    pdf_bytes = make_pdf_bytes(["Knovera Soft-Delete Re-upload Test Content"])

    res1 = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("to_delete.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res1.status_code == 201
    doc1_id = uuid.UUID(res1.json()["id"])

    # Soft delete the document
    doc1 = db_session.query(Document).filter(Document.id == doc1_id).first()
    assert doc1 is not None
    doc1.deleted_at = datetime.now(timezone.utc)
    db_session.commit()

    # Re-upload the exact same file -> MUST SUCCEED
    res2 = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("re_uploaded.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res2.status_code == 201
    assert res2.json()["id"] != str(doc1_id)


def test_duplicate_service_unit_logic(db_session: Session, test_workspace: Workspace):
    """Unit tests for DuplicateDetectionService direct methods."""
    service = DuplicateDetectionService()
    test_hash = hashlib.sha256(b"unit-test-hash").hexdigest()

    # Verify initially none
    assert service.check_duplicate(db_session, test_workspace.id, test_hash) is None

    # Insert a document with test_hash
    now = datetime.now(timezone.utc)
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_workspace.owner_user_id,
        original_filename="test.pdf",
        storage_key="test/key",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100,
        sha256=test_hash,
        processing_status="queued",
        extraction_metadata={},
        created_at=now,
        updated_at=now,
    )
    db_session.add(doc)
    db_session.commit()

    # Check duplicate finds it
    found = service.check_duplicate(db_session, test_workspace.id, test_hash)
    assert found is not None
    assert found.id == doc.id

    # Check excluding doc id works (used during reprocess)
    assert service.check_duplicate(db_session, test_workspace.id, test_hash, exclude_document_id=doc.id) is None

    # Ensure not duplicate raises DuplicateDocumentError
    with pytest.raises(DuplicateDocumentError) as exc_info:
        service.ensure_not_duplicate(db_session, test_workspace.id, test_hash)
    assert exc_info.value.existing_document_id == doc.id
