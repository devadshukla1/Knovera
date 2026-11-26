"""Local single-user execution and security boundary tests.

Verifies:
1. Unauthenticated requests succeed without token in local single-user mode.
2. Malformed or invalid tokens safely fall back to local owner without crashing.
3. Access to non-existent workspaces returns 404.
4. Workspace listing, creation, and document operations work cleanly.
5. Password hashing and security standards remain sound for extensibility.
"""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.auth import hash_password, verify_password
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


@pytest.mark.security
@pytest.mark.api
def test_unauthenticated_request_succeeds_in_local_mode(test_client: TestClient, test_workspace: Workspace):
    """Verifies that accessing resources without authorization succeeds in local mode."""
    response = test_client.get(f"/api/v1/workspaces/{test_workspace.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(test_workspace.id)


@pytest.mark.security
@pytest.mark.api
def test_tampered_or_malformed_token_falls_back_safely(test_client: TestClient, test_workspace: Workspace):
    """Verifies that an invalid JWT or altered signature safely falls back to local owner."""
    # Malformed token
    bad_headers = {"Authorization": "Bearer completely.invalid.jwttoken"}
    response = test_client.get(f"/api/v1/workspaces/{test_workspace.id}", headers=bad_headers)
    assert response.status_code == 200

    # Missing Bearer prefix
    bad_prefix = {"Authorization": "Token somevalidlookingstring"}
    response = test_client.get(f"/api/v1/workspaces/{test_workspace.id}", headers=bad_prefix)
    assert response.status_code == 200


@pytest.mark.security
@pytest.mark.api
def test_nonexistent_workspace_returns_404(
    test_client: TestClient,
):
    """Verifies that non-existent workspaces return 404."""
    random_id = uuid.uuid4()
    get_res = test_client.get(f"/api/v1/workspaces/{random_id}")
    assert get_res.status_code == 404

    patch_res = test_client.patch(
        f"/api/v1/workspaces/{random_id}",
        json={"name": "Hacked Workspace"},
    )
    assert patch_res.status_code == 404

    del_res = test_client.delete(f"/api/v1/workspaces/{random_id}")
    assert del_res.status_code == 404


@pytest.mark.security
@pytest.mark.api
def test_workspace_listing_in_local_mode(
    test_client: TestClient,
    test_user: User,
    db_session: Session,
):
    """Verifies workspace listings contain available workspaces."""
    ws = Workspace(owner_user_id=test_user.id, name="Local Research Projects")
    db_session.add(ws)
    db_session.commit()

    res = test_client.get("/api/v1/workspaces")
    assert res.status_code == 200
    names = [w["name"] for w in res.json()]
    assert "Local Research Projects" in names


@pytest.mark.security
@pytest.mark.api
def test_document_upload_and_read_in_local_mode(
    test_client: TestClient,
    test_workspace: Workspace,
):
    """Verifies document upload and reading works without credentials."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), "Valid Local Single User PDF", fontsize=14)
    dummy_pdf = doc.tobytes()
    doc.close()

    upload_res = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        files={"file": ("doc.pdf", io.BytesIO(dummy_pdf), "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    list_res = test_client.get(f"/api/v1/workspaces/{test_workspace.id}/documents")
    assert list_res.status_code == 200
    assert any(d["id"] == doc_id for d in list_res.json())


@pytest.mark.security
@pytest.mark.unit
def test_password_hashing_and_verification():
    """Verifies password hashing generates distinct salts and validates matches correctly."""
    pwd = "CorrectHorseBatteryStaple123!"
    hash1 = hash_password(pwd)
    hash2 = hash_password(pwd)

    # Distinct hashes due to salting
    assert hash1 != hash2
    assert hash1 != pwd
    assert not hash1.startswith("plain:")

    # Verification
    assert verify_password(pwd, hash1) is True
    assert verify_password("WrongPassword!", hash1) is False
    assert verify_password("", hash1) is False
