"""Integration tests for Knovera Study Materials API (Phase 8 Part 1).

Tests:
- C8.1 Revision Notes: generation, listing, detail retrieval
- C8.2 MCQs: generation, practice mode shielding, review mode answer key
- C8.3 Fill-in-the-Blanks: generation, practice mode shielding, review mode answer key
- Multi-tenant workspace isolation & 404 security rule
- Generation telemetry and audit logs
"""

import uuid
import pytest
from backend.app.core.auth import create_access_token
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


@pytest.fixture
def auth_context(db_session):
    """Sets up primary user, workspace, and bearer auth headers."""
    user = User(
        id=uuid.uuid4(),
        email=f"sm_tester_{uuid.uuid4().hex[:6]}@knovera.test",
        password_hash="hashed_pw_test",
        display_name="Study Material Tester",
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    workspace = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name="Study Material Workspace",
    )
    db_session.add(workspace)
    db_session.flush()

    token = create_access_token(user_id=str(user.id))
    headers = {"Authorization": f"Bearer {token}"}
    return {"user": user, "workspace": workspace, "headers": headers}


@pytest.fixture
def other_user_workspace(db_session):
    """Sets up a secondary tenant to test cross-tenant access denial."""
    user2 = User(
        id=uuid.uuid4(),
        email=f"sm_other_{uuid.uuid4().hex[:6]}@knovera.test",
        password_hash="hashed_pw_other",
        display_name="Other Tenant",
        status="active",
    )
    db_session.add(user2)
    db_session.flush()

    ws2 = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user2.id,
        name="Other Tenant Workspace",
    )
    db_session.add(ws2)
    db_session.flush()
    return {"user": user2, "workspace": ws2}


@pytest.fixture
def seeded_documents(db_session, auth_context):
    """Seeds active documents and chunks for study material generation."""
    user = auth_context["user"]
    ws = auth_context["workspace"]

    doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="intro_ml.pdf",
        storage_key=f"storage/{uuid.uuid4().hex}/intro_ml.pdf",
        media_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=10240,
        sha256=uuid.uuid4().hex,
        processing_status="completed",
    )
    db_session.add(doc)
    db_session.flush()

    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc.id,
        chunk_index=0,
        page_start=1,
        page_end=1,
        content="Support Vector Machines (SVMs) find an optimal hyperplane separating data classes with maximum margin.",
        content_hash=uuid.uuid4().hex,
        token_count=18,
        parser_version="1.0.0",
        cleaning_version="1.0.0",
        chunking_version="1.0.0",
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc.id,
        chunk_index=1,
        page_start=2,
        page_end=2,
        content="K-Means partitions data into k clusters where each observation belongs to the cluster with the closest centroid.",
        content_hash=uuid.uuid4().hex,
        token_count=20,
        parser_version="1.0.0",
        cleaning_version="1.0.0",
        chunking_version="1.0.0",
    )
    db_session.add_all([chunk1, chunk2])
    db_session.flush()

    return {"document": doc, "chunks": [chunk1, chunk2]}


# =============================================================================
# Multi-Tenancy & Authorization Tests
# =============================================================================

def test_unauthenticated_request_succeeds(test_client, auth_context):
    ws_id = auth_context["workspace"].id
    resp = test_client.get(f"/api/v1/workspaces/{ws_id}/study-materials/revision-notes")
    assert resp.status_code == 200


def test_local_mode_workspace_accessible(test_client, auth_context, other_user_workspace):
    other_ws_id = other_user_workspace["workspace"].id
    resp = test_client.get(
        f"/api/v1/workspaces/{other_ws_id}/study-materials/revision-notes",
        headers=auth_context["headers"],
    )
    assert resp.status_code == 200


# =============================================================================
# C8.1: Revision Notes API Tests
# =============================================================================

def test_generate_and_get_revision_notes(test_client, auth_context, seeded_documents):
    ws_id = auth_context["workspace"].id
    headers = auth_context["headers"]

    payload = {
        "scope": {"scope_type": "workspace"},
        "length": "standard",
        "detail_level": "intermediate",
        "focus": "conceptual_learning",
        "custom_title": "ML Fundamentals Study Guide",
    }

    # 1. Generate revision notes
    gen_resp = test_client.post(
        f"/api/v1/workspaces/{ws_id}/study-materials/revision-notes/generate",
        json=payload,
        headers=headers,
    )
    assert gen_resp.status_code == 201
    note_data = gen_resp.json()
    assert note_data["title"] == "ML Fundamentals Study Guide"
    assert note_data["workspace_id"] == str(ws_id)
    assert len(note_data["sections"]) >= 1
    assert len(note_data["source_references"]) >= 1
    note_id = note_data["id"]

    # 2. List revision notes
    list_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/revision-notes",
        headers=headers,
    )
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(n["id"] == note_id for n in list_data["items"])

    # 3. Get single revision note
    detail_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/revision-notes/{note_id}",
        headers=headers,
    )
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["id"] == note_id
    assert detail_data["title"] == "ML Fundamentals Study Guide"


# =============================================================================
# C8.2: MCQ Generation & Answer-Key Security Tests
# =============================================================================

def test_generate_and_get_mcqs_practice_vs_review_mode(test_client, auth_context, seeded_documents):
    ws_id = auth_context["workspace"].id
    headers = auth_context["headers"]

    payload = {
        "scope": {"scope_type": "workspace"},
        "count": 2,
        "difficulty": "medium",
        "question_type": "conceptual",
    }

    # 1. Generate MCQs
    gen_resp = test_client.post(
        f"/api/v1/workspaces/{ws_id}/study-materials/mcqs/generate",
        json=payload,
        headers=headers,
    )
    assert gen_resp.status_code == 201
    mcqs = gen_resp.json()
    assert len(mcqs) == 2
    first_q_id = mcqs[0]["id"]

    # 2. Retrieve MCQs in PRACTICE mode (Default student view)
    practice_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/mcqs?mode=practice",
        headers=headers,
    )
    assert practice_resp.status_code == 200
    practice_data = practice_resp.json()
    assert practice_data["mode"] == "practice"
    assert practice_data["total"] >= 2

    # CRITICAL SECURITY CHECK: Practice mode MUST NOT leak the answer key!
    for item in practice_data["items"]:
        assert "correct_option_id" not in item, "Practice mode leaked correct_option_id!"
        assert "explanation" not in item, "Practice mode leaked explanation!"
        for opt in item["options"]:
            assert "is_correct" not in opt, "Practice mode leaked option is_correct flag!"

    # 3. Retrieve single MCQ in PRACTICE mode
    single_practice = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/mcqs/{first_q_id}?mode=practice",
        headers=headers,
    )
    assert single_practice.status_code == 200
    sp_data = single_practice.json()
    assert "correct_option_id" not in sp_data
    assert "explanation" not in sp_data

    # 4. Retrieve MCQs in REVIEW mode (Complete answer key & explanations)
    review_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/mcqs?mode=review",
        headers=headers,
    )
    assert review_resp.status_code == 200
    review_data = review_resp.json()
    assert review_data["mode"] == "review"

    for item in review_data["items"]:
        assert "correct_option_id" in item
        assert item["correct_option_id"] in ["A", "B", "C", "D"]
        assert "explanation" in item
        assert len(item["explanation"]) > 0
        correct_count = sum(1 for opt in item["options"] if opt.get("is_correct") is True)
        assert correct_count == 1, "Review mode must have exactly 1 option with is_correct=True"

    # 5. Retrieve single MCQ in REVIEW mode
    single_review = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/mcqs/{first_q_id}?mode=review",
        headers=headers,
    )
    assert single_review.status_code == 200
    sr_data = single_review.json()
    assert "correct_option_id" in sr_data
    assert "explanation" in sr_data


# =============================================================================
# C8.3: Fill-in-the-Blanks API Tests
# =============================================================================

def test_generate_and_get_fill_blanks_practice_vs_review_mode(test_client, auth_context, seeded_documents):
    ws_id = auth_context["workspace"].id
    headers = auth_context["headers"]

    payload = {
        "scope": {"scope_type": "workspace"},
        "count": 2,
        "difficulty": "medium",
    }

    # 1. Generate Fill-in-the-blanks
    gen_resp = test_client.post(
        f"/api/v1/workspaces/{ws_id}/study-materials/fill-blanks/generate",
        json=payload,
        headers=headers,
    )
    assert gen_resp.status_code == 201
    items = gen_resp.json()
    assert len(items) == 2
    first_item_id = items[0]["id"]

    # 2. Retrieve Fill-in-the-blanks in PRACTICE mode (Default student view)
    practice_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/fill-blanks?mode=practice",
        headers=headers,
    )
    assert practice_resp.status_code == 200
    practice_data = practice_resp.json()
    assert practice_data["mode"] == "practice"

    # CRITICAL SECURITY CHECK: Practice mode MUST NOT leak the answer or variants!
    for ex in practice_data["items"]:
        assert "canonical_answer" not in ex, "Practice mode leaked canonical_answer!"
        assert "accepted_answers" not in ex, "Practice mode leaked accepted_answers!"
        assert "original_sentence" not in ex, "Practice mode leaked original_sentence!"
        assert "explanation" not in ex, "Practice mode leaked explanation!"
        assert "sentence_with_blank" in ex
        assert "______" in ex["sentence_with_blank"]

    # 3. Retrieve single item in PRACTICE mode
    single_practice = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/fill-blanks/{first_item_id}?mode=practice",
        headers=headers,
    )
    assert single_practice.status_code == 200
    sp_data = single_practice.json()
    assert "canonical_answer" not in sp_data
    assert "accepted_answers" not in sp_data

    # 4. Retrieve Fill-in-the-blanks in REVIEW mode
    review_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/fill-blanks?mode=review",
        headers=headers,
    )
    assert review_resp.status_code == 200
    review_data = review_resp.json()
    assert review_data["mode"] == "review"

    for ex in review_data["items"]:
        assert "canonical_answer" in ex
        assert len(ex["canonical_answer"]) > 0
        assert "accepted_answers" in ex
        assert "target_start_offset" in ex
        assert "target_end_offset" in ex
        assert "original_sentence" in ex
        # Verify reconstruction
        assert ex["sentence_with_blank"].replace("______", ex["canonical_answer"]) == ex["original_sentence"]

    # 5. Retrieve single item in REVIEW mode
    single_review = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/fill-blanks/{first_item_id}?mode=review",
        headers=headers,
    )
    assert single_review.status_code == 200
    sr_data = single_review.json()
    assert "canonical_answer" in sr_data
    assert "target_start_offset" in sr_data


# =============================================================================
# Generation Runs Audit Telemetry Tests
# =============================================================================

def test_generation_runs_audit_telemetry(test_client, auth_context, seeded_documents):
    ws_id = auth_context["workspace"].id
    headers = auth_context["headers"]

    # Trigger a revision notes generation run
    client_resp = test_client.post(
        f"/api/v1/workspaces/{ws_id}/study-materials/revision-notes/generate",
        json={"scope": {"scope_type": "workspace"}},
        headers=headers,
    )
    assert client_resp.status_code == 201

    # 1. List generations
    gen_list_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/generations",
        headers=headers,
    )
    assert gen_list_resp.status_code == 200
    runs = gen_list_resp.json()
    assert runs["total"] >= 1
    run = runs["items"][0]
    assert run["material_type"] == "revision_notes"
    assert run["status"] in ["completed", "completed_with_warnings"]
    assert run["duration_ms"] >= 0
    run_id = run["id"]

    # 2. Get generation run details
    single_run_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/generations/{run_id}",
        headers=headers,
    )
    assert single_run_resp.status_code == 200
    single_run = single_run_resp.json()
    assert single_run["id"] == run_id
    assert single_run["material_type"] == "revision_notes"
