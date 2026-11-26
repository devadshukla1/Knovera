import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.models.workspace import Workspace

client = TestClient(app)

def test_workspace_crud_lifecycle_and_deletion():
    # 1. Create workspace
    unique_name = f"Pytest Workspace {uuid4().hex[:8]}"
    create_payload = {
        "name": unique_name,
        "description": "Lifecycle and deletion test"
    }
    create_res = client.post("/api/v1/workspaces", json=create_payload)
    assert create_res.status_code == 201, create_res.text
    ws_data = create_res.json()
    ws_id = ws_data["id"]
    assert ws_data["name"] == unique_name

    # 2. Verify in PostgreSQL
    with SessionLocal() as session:
        ws_in_db = session.query(Workspace).filter(Workspace.id == ws_id).first()
        assert ws_in_db is not None
        assert ws_in_db.name == unique_name

    # 3. Update / Rename workspace
    renamed_name = f"{unique_name} Renamed"
    update_res = client.patch(f"/api/v1/workspaces/{ws_id}", json={"name": renamed_name})
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["name"] == renamed_name

    # 4. Delete workspace
    delete_res = client.delete(f"/api/v1/workspaces/{ws_id}")
    assert delete_res.status_code in (200, 204), delete_res.text

    # 5. Verify gone from PostgreSQL
    with SessionLocal() as session:
        ws_deleted = session.query(Workspace).filter(Workspace.id == ws_id).first()
        assert ws_deleted is None

    # 6. Verify 404 on get
    get_res = client.get(f"/api/v1/workspaces/{ws_id}")
    assert get_res.status_code == 404
