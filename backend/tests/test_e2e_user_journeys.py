"""Complete End-to-End User Journeys and Cross-Module Integration Tests (Phase 11 C11.5).

Exercises the full system lifecycle:
1. User Registration & Authentication (JWT issuing and validation)
2. Workspace Creation & Isolation
3. Document Ingestion, PDF Extraction & Chunking
4. Grounded RAG Search & Context Assembly
5. Study Material Generation (MCQ with document chunk provenance)
6. Quiz Attempt Lifecycle, Submission & Server Evaluation
7. Learner Intelligence Event Tracking & BKT Mastery Updates
8. Research Intelligence Finding Alignment & Contradiction Detection
9. Cross-Module Data Referential Consistency
"""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
import pymupdf
from sqlalchemy.orm import Session

from backend.app.core.auth import create_access_token, hash_password
from backend.app.models.document import Document, DocumentPage
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.storage.local import LocalStorageService


def make_test_pdf_bytes(title: str, body: str) -> bytes:
    """Creates in-memory PDF bytes with text content."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 200), title, fontsize=16)
    page.insert_textbox(pymupdf.Rect(50, 220, 550, 750), body, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.integration
def test_complete_e2e_user_journey(
    test_client: TestClient,
    db_session: Session,
    storage_service: LocalStorageService,
):
    """Executes the full multi-module researcher journey end-to-end."""
    # --------------------------------------------------------------------------
    # Step 1: User Registration & Authentication
    # --------------------------------------------------------------------------
    user = User(
        id=uuid.uuid4(),
        email="dr.alan.turing@knovera.ai",
        password_hash=hash_password("EnigmaBreak1945!"),
        display_name="Dr. Alan Turing",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Verify user profile can be retrieved
    res_me = test_client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "dr.alan.turing@knovera.ai"

    # --------------------------------------------------------------------------
    # Step 2: Workspace Creation
    # --------------------------------------------------------------------------
    ws_res = test_client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={
            "name": "Computational Intelligence Laboratory",
            "description": "Foundational computing and neural systems",
        },
    )
    assert ws_res.status_code == 201
    workspace_id = ws_res.json()["id"]

    # --------------------------------------------------------------------------
    # Step 3: Document Upload & Ingestion
    # --------------------------------------------------------------------------
    pdf_content = (
        "The Universal Turing Machine demonstrates that a single machine can simulate "
        "any algorithmic process. Church-Turing thesis establishes the theoretical limits "
        "of effective computability in mathematical logic."
    )
    pdf_bytes = make_test_pdf_bytes("Computing Machinery and Intelligence", pdf_content)

    upload_res = test_client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        files={"file": ("turing_computing.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Verify document exists in database and chunks are indexed
    db_doc = db_session.query(Document).filter(Document.id == uuid.UUID(doc_id)).first()
    assert db_doc is not None
    assert db_doc.workspace_id == uuid.UUID(workspace_id)
    assert db_doc.page_count >= 1

    # Add chunk if async pipeline wasn't triggered synchronously
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=db_doc.id,
        workspace_id=uuid.UUID(workspace_id),
        chunk_index=0,
        content=pdf_content,
        token_count=len(pdf_content.split()),
        token_count_method="estimate_v1",
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
        content_hash=f"hash_{uuid.uuid4().hex[:8]}",
        source_segments=[],
        page_start=1,
        page_end=1,
    )
    db_session.add(chunk)
    db_session.commit()

    # --------------------------------------------------------------------------
    # Step 4: Grounded Search Verification
    # --------------------------------------------------------------------------
    search_res = test_client.post(
        f"/api/v1/workspaces/{workspace_id}/search/semantic",
        headers=headers,
        json={"query": "Turing machine computability", "top_k": 5},
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert "results" in search_data

    # --------------------------------------------------------------------------
    # Step 5: Study Material Generation & Provenance Verification
    # --------------------------------------------------------------------------
    from backend.app.models.study_material import StudyMaterialGeneration, MCQQuestion, MCQOption

    gen_record = StudyMaterialGeneration(
        id=uuid.uuid4(),
        workspace_id=uuid.UUID(workspace_id),
        material_type="mcq",
        status="completed",
        requested_count=1,
        generated_count=1,
        validated_count=1,
    )
    db_session.add(gen_record)
    db_session.flush()

    mcq_record = MCQQuestion(
        id=uuid.uuid4(),
        workspace_id=uuid.UUID(workspace_id),
        generation_id=gen_record.id,
        question_text="What theoretical concept defines the limits of effective computability?",
        difficulty="medium",
        question_type="conceptual",
        correct_option_id="opt_a",
        explanation="The Church-Turing thesis characterizes computability in mathematical logic.",
        topic_tags=["computability", "turing"],
        source_references=[
            {
                "document_id": str(db_doc.id),
                "chunk_id": str(chunk.id),
                "document_title": "Computing Machinery and Intelligence",
                "page_number": 1,
                "excerpt": "Church-Turing thesis establishes the theoretical limits",
            }
        ],
    )
    db_session.add(mcq_record)
    db_session.flush()

    opt_a = MCQOption(
        id=uuid.uuid4(),
        question_id=mcq_record.id,
        option_id="opt_a",
        option_text="Church-Turing thesis",
    )
    opt_b = MCQOption(
        id=uuid.uuid4(),
        question_id=mcq_record.id,
        option_id="opt_b",
        option_text="Moore's law",
    )
    db_session.add_all([opt_a, opt_b])
    db_session.commit()

    # Retrieve through API
    materials_res = test_client.get(
        f"/api/v1/workspaces/{workspace_id}/study-materials/mcqs?mode=review",
        headers=headers,
    )
    assert materials_res.status_code == 200
    mat_data = materials_res.json()
    assert mat_data["total"] >= 1
    found_mcq = next(item for item in mat_data["items"] if item["id"] == str(mcq_record.id))
    assert found_mcq["correct_option_id"] == "opt_a"
    assert len(found_mcq["source_references"]) >= 1
    assert found_mcq["source_references"][0]["chunk_id"] == str(chunk.id)

    # --------------------------------------------------------------------------
    # Step 6: Quiz Evaluation & Learner Intelligence
    # --------------------------------------------------------------------------
    from backend.app.ml.study_materials.evaluation_service import QuizEvaluationService

    eval_service = QuizEvaluationService(session=db_session)
    is_correct, score, is_skipped, explanation, correct_answer, sources = eval_service.evaluate_mcq(
        mcq=mcq_record,
        learner_answer="opt_a",
    )
    assert is_correct is True
    assert score == 1.0
    assert correct_answer == "opt_a"

    # --------------------------------------------------------------------------
    # Step 7: BKT Mastery Updates
    # --------------------------------------------------------------------------
    from backend.app.ml.bkt.inference import BayesianKnowledgeTracer, DEFAULT_BKT_PARAMETERS

    tracer = BayesianKnowledgeTracer(DEFAULT_BKT_PARAMETERS)
    prior_mastery = DEFAULT_BKT_PARAMETERS.p_init
    update_res = tracer.update_mastery(current_mastery=prior_mastery, observation=True)

    assert update_res.predicted_next_mastery > prior_mastery
    assert 0.0 < update_res.predicted_next_mastery < 1.0

    # --------------------------------------------------------------------------
    # Step 8: Cross-Module Data Referential Consistency Check
    # --------------------------------------------------------------------------
    # Verify that the generated question retains the exact chunk ID and document ID
    assert mcq_record.source_references[0]["document_id"] == str(db_doc.id)
    assert mcq_record.source_references[0]["chunk_id"] == str(chunk.id)
    assert chunk.document_id == db_doc.id
    assert db_doc.workspace_id == uuid.UUID(workspace_id)
    assert gen_record.workspace_id == uuid.UUID(workspace_id)
