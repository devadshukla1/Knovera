"""Integration tests for Knovera Study Materials API (C8.4, C8.5, C8.6).

Tests:
- C8.4 True/False Questions: generation, practice mode shielding, review mode answer key
- C8.5 Flashcards: generation, listing, category filtering, detail retrieval
- C8.6 Interactive Quiz Lifecycle: attempt creation, anti-cheat question shielding,
      intermediate answer saving, authoritative backend evaluation across heterogeneous
      question types (MCQ, True/False, Fill-Blank), and result reporting.
- Workspace tenancy isolation & security boundaries
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
        original_filename="machine_learning_fundamentals.pdf",
        storage_key=f"storage/{uuid.uuid4().hex}/ml.pdf",
        media_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=20480,
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
        content="Support Vector Machines find an optimal hyperplane separating data classes with maximum geometric margin.",
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
        content="K-Means is an unsupervised clustering algorithm partitioning n observations into k clusters with nearest mean centroids.",
        content_hash=uuid.uuid4().hex,
        token_count=19,
        parser_version="1.0.0",
        cleaning_version="1.0.0",
        chunking_version="1.0.0",
    )
    db_session.add_all([chunk1, chunk2])
    db_session.commit()
    return {"document": doc, "chunks": [chunk1, chunk2]}


# =============================================================================
# C8.4: True/False Questions API Tests
# =============================================================================

def test_true_false_generation_and_modes(test_client, auth_context, seeded_documents):
    ws_id = auth_context["workspace"].id
    headers = auth_context["headers"]

    # 1. Generate True/False questions
    gen_payload = {
        "scope": {"scope_type": "workspace"},
        "count": 4,
        "target_true_ratio": 0.5,
    }
    create_resp = test_client.post(
        f"/api/v1/workspaces/{ws_id}/study-materials/true-false/generate",
        json=gen_payload,
        headers=headers,
    )
    assert create_resp.status_code == 201
    created_items = create_resp.json()
    assert len(created_items) >= 2
    first_item_id = created_items[0]["id"]

    # 2. Practice Mode retrieval (Shields correct_answer and explanation)
    practice_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/true-false?mode=practice",
        headers=headers,
    )
    assert practice_resp.status_code == 200
    p_data = practice_resp.json()
    assert p_data["mode"] == "practice"
    assert len(p_data["items"]) >= 2
    for item in p_data["items"]:
        assert "statement" in item
        assert "correct_answer" not in item
        assert "explanation" not in item

    # 3. Single item Practice Mode
    single_p_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/true-false/{first_item_id}?mode=practice",
        headers=headers,
    )
    assert single_p_resp.status_code == 200
    sp_item = single_p_resp.json()
    assert "correct_answer" not in sp_item
    assert "explanation" not in sp_item

    # 4. Review Mode retrieval (Reveals answer, explanation, source references)
    review_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/true-false?mode=review",
        headers=headers,
    )
    assert review_resp.status_code == 200
    r_data = review_resp.json()
    assert r_data["mode"] == "review"
    for item in r_data["items"]:
        assert "correct_answer" in item
        assert isinstance(item["correct_answer"], bool)
        assert "explanation" in item
        assert len(item["explanation"]) > 0
        assert "source_references" in item

    # 5. Single item Review Mode
    single_r_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/true-false/{first_item_id}?mode=review",
        headers=headers,
    )
    assert single_r_resp.status_code == 200
    sr_item = single_r_resp.json()
    assert "correct_answer" in sr_item
    assert "explanation" in sr_item


# =============================================================================
# C8.5: Flashcard Generation & Listing API Tests
# =============================================================================

def test_flashcard_generation_and_listing(test_client, auth_context, seeded_documents):
    ws_id = auth_context["workspace"].id
    headers = auth_context["headers"]

    # 1. Generate Flashcards
    gen_payload = {
        "scope": {"scope_type": "workspace"},
        "count": 4,
    }
    create_resp = test_client.post(
        f"/api/v1/workspaces/{ws_id}/study-materials/flashcards/generate",
        json=gen_payload,
        headers=headers,
    )
    assert create_resp.status_code == 201
    created_cards = create_resp.json()
    assert len(created_cards) >= 2
    first_card_id = created_cards[0]["id"]

    # 2. List Flashcards
    list_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/flashcards",
        headers=headers,
    )
    assert list_resp.status_code == 200
    l_data = list_resp.json()
    assert l_data["total"] >= 2
    for card in l_data["items"]:
        assert 3 <= len(card["front"]) <= 200
        assert 1 <= len(card["back"]) <= 500
        assert "card_type" in card

    # 3. Get single Flashcard
    single_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/study-materials/flashcards/{first_card_id}",
        headers=headers,
    )
    assert single_resp.status_code == 200
    single_card = single_resp.json()
    assert single_card["id"] == first_card_id
    assert "front" in single_card
    assert "back" in single_card


# =============================================================================
# C8.6: Interactive Quiz Attempt Lifecycle & Authoritative Grading Tests
# =============================================================================

def test_quiz_attempt_full_lifecycle(test_client, auth_context, seeded_documents):
    ws_id = auth_context["workspace"].id
    headers = auth_context["headers"]

    # Step 1: Pre-generate MCQ, True/False, and FillBlank questions in the workspace
    mcq_resp = test_client.post(
        f"/api/v1/workspaces/{ws_id}/study-materials/mcqs/generate",
        json={"scope": {"scope_type": "workspace"}, "count": 2},
        headers=headers,
    )
    assert mcq_resp.status_code == 201
    mcq_items = mcq_resp.json()

    tf_resp = test_client.post(
        f"/api/v1/workspaces/{ws_id}/study-materials/true-false/generate",
        json={"scope": {"scope_type": "workspace"}, "count": 2},
        headers=headers,
    )
    assert tf_resp.status_code == 201
    tf_items = tf_resp.json()

    fb_resp = test_client.post(
        f"/api/v1/workspaces/{ws_id}/study-materials/fill-blanks/generate",
        json={"scope": {"scope_type": "workspace"}, "count": 2},
        headers=headers,
    )
    assert fb_resp.status_code == 201
    fb_items = fb_resp.json()

    # Step 2: Start a Quiz Attempt
    start_payload = {
        "title": "Full ML Practice Quiz",
        "count": 6,
    }
    create_attempt_resp = test_client.post(
        f"/api/v1/workspaces/{ws_id}/quiz-attempts",
        json=start_payload,
        headers=headers,
    )
    assert create_attempt_resp.status_code == 201
    attempt_data = create_attempt_resp.json()
    assert attempt_data["status"] == "in_progress"
    assert attempt_data["total_questions"] >= 3
    assert len(attempt_data["questions"]) == attempt_data["total_questions"]
    attempt_id = attempt_data["id"]

    # Anti-cheat check: questions in attempt MUST NOT leak answers
    for q in attempt_data["questions"]:
        assert "correct_answer" not in q
        assert "explanation" not in q
        if q["question_type"] == "mcq":
            for opt in q["options"]:
                assert "is_correct" not in opt

    # Step 3: List historical attempts
    list_attempts_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/quiz-attempts",
        headers=headers,
    )
    assert list_attempts_resp.status_code == 200
    list_data = list_attempts_resp.json()
    assert list_data["total"] >= 1
    assert any(a["id"] == attempt_id for a in list_data["items"])

    # Step 4: Save partial answers
    q0 = attempt_data["questions"][0]
    sample_answer = "A" if q0["question_type"] == "mcq" else (True if q0["question_type"] == "true_false" else "term")
    save_resp = test_client.put(
        f"/api/v1/workspaces/{ws_id}/quiz-attempts/{attempt_id}/answers",
        json={"answers": [{"question_id": q0["id"], "question_type": q0["question_type"], "selected_answer": sample_answer}]},
        headers=headers,
    )
    assert save_resp.status_code == 200
    saved_state = save_resp.json()
    assert saved_state["answered_count"] == 1
    assert str(q0["id"]) in saved_state["saved_answers"]

    # Step 5: Authoritative Submission & Evaluation
    # Prepare answers matching known answers from the review items
    known_answers = {}
    for item in mcq_items:
        known_answers[item["id"]] = item["correct_option_id"]
    for item in tf_items:
        known_answers[item["id"]] = item["correct_answer"]
    for item in fb_items:
        known_answers[item["id"]] = item["canonical_answer"]

    submit_answers = []
    for q in attempt_data["questions"]:
        qid = q["id"]
        val = known_answers.get(qid, "correct_test")
        submit_answers.append({
            "question_id": qid,
            "question_type": q["question_type"],
            "selected_answer": val,
        })

    submit_resp = test_client.post(
        f"/api/v1/workspaces/{ws_id}/quiz-attempts/{attempt_id}/submit",
        json={"answers": submit_answers},
        headers=headers,
    )
    assert submit_resp.status_code == 200
    eval_result = submit_resp.json()
    assert eval_result["status"] == "evaluated"
    assert eval_result["total_questions"] == attempt_data["total_questions"]
    assert eval_result["correct_count"] > 0
    assert eval_result["score_percentage"] > 0.0
    assert len(eval_result["results"]) == eval_result["total_questions"]

    # Step 6: Verified Results retrieval
    results_resp = test_client.get(
        f"/api/v1/workspaces/{ws_id}/quiz-attempts/{attempt_id}/results",
        headers=headers,
    )
    assert results_resp.status_code == 200
    verified_results = results_resp.json()
    assert verified_results["attempt_id"] == attempt_id
    assert verified_results["score_percentage"] == eval_result["score_percentage"]


def test_cross_tenant_isolation(test_client, auth_context, other_user_workspace):
    """Verifies tenant isolation across True/False, Flashcards, and Quiz Attempts."""
    ws2_id = other_user_workspace["workspace"].id
    headers1 = auth_context["headers"]

    # Attempt to access other tenant's study materials using user 1's auth
    tf_resp = test_client.get(
        f"/api/v1/workspaces/{ws2_id}/study-materials/true-false",
        headers=headers1,
    )
    assert tf_resp.status_code == 404

    fc_resp = test_client.get(
        f"/api/v1/workspaces/{ws2_id}/study-materials/flashcards",
        headers=headers1,
    )
    assert fc_resp.status_code == 404

    quiz_resp = test_client.get(
        f"/api/v1/workspaces/{ws2_id}/quiz-attempts",
        headers=headers1,
    )
    assert quiz_resp.status_code == 404
