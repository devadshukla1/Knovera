"""Unit and Integration Tests for C10.8: Cross-Paper Contradiction Detection."""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.ml.research.contradiction_service import ContradictionDetectionService
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.research_intelligence import (
    ResearchContradictionRecord,
    ResearchFinding,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.research_intelligence import (
    ContradictionDetectRequest,
    ContradictionReviewRequest,
)


@pytest.fixture
def db_session():
    """In-memory SQLite session with full schema initialized."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def workspace_setup(db_session):
    """Seed user, workspace, two documents, and their chunks."""
    user = User(
        id=uuid.uuid4(),
        email="auditor@knovera.test",
        password_hash="mock_hash",
        display_name="Auditor One",
    )
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Meta-Analysis Group",
        owner_user_id=user.id,
    )
    doc_a = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        uploaded_by_user_id=user.id,
        original_filename="paper_a.pdf",
        storage_key=f"ws-{workspace.id}/docs/paper_a.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100000,
        sha256="1" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "Paper A: Supervised Learning Advantage"},
    )
    doc_b = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        uploaded_by_user_id=user.id,
        original_filename="paper_b.pdf",
        storage_key=f"ws-{workspace.id}/docs/paper_b.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100000,
        sha256="2" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "Paper B: Self-Supervised Superiority"},
    )
    db_session.add_all([user, workspace, doc_a, doc_b])
    db_session.flush()

    chunk_a = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        document_id=doc_a.id,
        chunk_index=0,
        content="Supervised fine-tuning consistently outperforms self-supervised representations on classification tasks.",
        content_hash="1" * 64,
        page_start=3,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
        token_count=13,
    )
    chunk_b = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        document_id=doc_b.id,
        chunk_index=0,
        content="Self-supervised pretraining significantly outperforms supervised baselines across all classification benchmarks.",
        content_hash="2" * 64,
        page_start=4,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
        token_count=13,
    )
    db_session.add_all([chunk_a, chunk_b])
    db_session.commit()

    return {
        "user": user,
        "workspace": workspace,
        "doc_a": doc_a,
        "doc_b": doc_b,
        "chunk_a": chunk_a,
        "chunk_b": chunk_b,
    }


def test_metric_divergence_safeguard(db_session, workspace_setup):
    """Stage 2 Safeguard: If findings measure different outcome variables, categorize as metric_difference."""
    service = ContradictionDetectionService(db_session)
    ws = workspace_setup["workspace"]
    doc_a = workspace_setup["doc_a"]
    doc_b = workspace_setup["doc_b"]

    fa = ResearchFinding(
        workspace_id=ws.id,
        document_id=doc_a.id,
        finding_type="quantitative",
        original_statement="Approach A achieves 92% accuracy on ImageNet.",
        normalized_statement="Approach A achieves 92% accuracy on ImageNet.",
        outcome_variable="accuracy",
        validation_status="supported",
    )
    fb = ResearchFinding(
        workspace_id=ws.id,
        document_id=doc_b.id,
        finding_type="quantitative",
        original_statement="Approach B requires 45 milliseconds latency on ImageNet.",
        normalized_statement="Approach B requires 45 milliseconds latency on ImageNet.",
        outcome_variable="latency",
        validation_status="supported",
    )
    db_session.add_all([fa, fb])
    db_session.commit()

    req = ContradictionDetectRequest(finding_a_id=fa.id, finding_b_id=fb.id)
    record = service.detect_contradiction(workspace_id=ws.id, request=req)

    assert record.contradiction_category == "metric_difference"
    assert record.comparability_status in ("conditionally_comparable", "not_comparable")
    assert any("Outcome metric divergence" in d for d in record.contextual_differences)


def test_population_divergence_safeguard(db_session, workspace_setup):
    """Stage 2 Safeguard: Divergent study populations must be categorized as population_difference."""
    service = ContradictionDetectionService(db_session)
    ws = workspace_setup["workspace"]
    doc_a = workspace_setup["doc_a"]
    doc_b = workspace_setup["doc_b"]

    fa = ResearchFinding(
        workspace_id=ws.id,
        document_id=doc_a.id,
        finding_type="quantitative",
        original_statement="Treatment improves memory retention by 40%.",
        normalized_statement="Treatment improves memory retention by 40%.",
        outcome_variable="memory retention",
        population="elderly adults aged 65-80",
        validation_status="supported",
    )
    fb = ResearchFinding(
        workspace_id=ws.id,
        document_id=doc_b.id,
        finding_type="quantitative",
        original_statement="Treatment decreases memory retention by 10%.",
        normalized_statement="Treatment decreases memory retention by 10%.",
        outcome_variable="memory retention",
        population="adolescents aged 12-16",
        validation_status="supported",
    )
    db_session.add_all([fa, fb])
    db_session.commit()

    req = ContradictionDetectRequest(finding_a_id=fa.id, finding_b_id=fb.id)
    record = service.detect_contradiction(workspace_id=ws.id, request=req)

    assert record.contradiction_category == "population_difference"
    assert any("Population difference" in d for d in record.contextual_differences)


def test_direct_contradiction_candidate_and_human_review_lifecycle(db_session, workspace_setup):
    """Tests identifying direct contradiction candidate, followed by human audit confirmation and rejection."""
    service = ContradictionDetectionService(db_session)
    ws = workspace_setup["workspace"]
    user = workspace_setup["user"]
    doc_a = workspace_setup["doc_a"]
    doc_b = workspace_setup["doc_b"]

    fa = ResearchFinding(
        workspace_id=ws.id,
        document_id=doc_a.id,
        finding_type="quantitative",
        original_statement="Model scaling increases hallucination rates on QA benchmarks.",
        normalized_statement="Model scaling increases hallucination rates on QA benchmarks.",
        outcome_variable="hallucination rate",
        validation_status="supported",
    )
    fb = ResearchFinding(
        workspace_id=ws.id,
        document_id=doc_b.id,
        finding_type="quantitative",
        original_statement="Model scaling decreases hallucination rates on QA benchmarks.",
        normalized_statement="Model scaling decreases hallucination rates on QA benchmarks.",
        outcome_variable="hallucination rate",
        validation_status="supported",
    )
    db_session.add_all([fa, fb])
    db_session.commit()

    # Step 1: Detect candidate
    req = ContradictionDetectRequest(finding_a_id=fa.id, finding_b_id=fb.id)
    record = service.detect_contradiction(workspace_id=ws.id, request=req)

    assert record.contradiction_category == "direct_contradiction_candidate"
    assert record.review_status == "needs_review"
    assert record.human_verified is False

    # Step 2: Human reviewer confirms contradiction
    review_req = ContradictionReviewRequest(
        action="confirm",
        notes="Empirical conflict confirmed on identical QA benchmark.",
    )
    confirmed_record = service.review_contradiction(
        workspace_id=ws.id,
        contradiction_id=record.id,
        request=review_req,
        user_id=user.id,
    )

    assert confirmed_record.review_status == "confirmed"
    assert confirmed_record.human_verified is True
    assert confirmed_record.reviewer_notes == "Empirical conflict confirmed on identical QA benchmark."
    assert len(confirmed_record.reviews) == 1
    assert confirmed_record.reviews[0].review_action == "confirm"

    # Step 3: Human reopens review
    reopen_req = ContradictionReviewRequest(
        action="reopen",
        notes="Reopening for senior investigator verification.",
    )
    reopened = service.review_contradiction(
        workspace_id=ws.id,
        contradiction_id=record.id,
        request=reopen_req,
        user_id=user.id,
    )
    assert reopened.review_status == "needs_review"
    assert reopened.human_verified is False
    assert len(reopened.reviews) == 2
