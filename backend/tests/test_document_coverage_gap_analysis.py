"""Unit and Integration Tests for C10.9: Document Coverage Gap Analysis."""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.ml.research.coverage_service import DocumentCoverageService
from backend.app.models.document import Document
from backend.app.models.research_intelligence import (
    DocumentCoverageAnalysisRun,
    DocumentCoverageGap,
    ResearchFinding,
    ResearchMetadataProfile,
    ResearchMethodologyProfile,
    ResearchObjectiveProfile,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.research_intelligence import CoverageRunRequest


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
def corpus_setup(db_session):
    """Seed user, workspace, and 3 research papers with distinct profiles."""
    user = User(
        id=uuid.uuid4(),
        email="curator@knovera.test",
        password_hash="mock_hash",
        display_name="Corpus Curator",
    )
    workspace = Workspace(
        id=uuid.uuid4(),
        name="NLP Corpus Review",
        owner_user_id=user.id,
    )
    doc_1 = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        uploaded_by_user_id=user.id,
        original_filename="study_transformer.pdf",
        storage_key=f"ws-{workspace.id}/docs/study_transformer.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100000,
        sha256="1" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "Transformer Evaluation"},
    )
    doc_2 = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        uploaded_by_user_id=user.id,
        original_filename="study_rnn.pdf",
        storage_key=f"ws-{workspace.id}/docs/study_rnn.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100000,
        sha256="2" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "RNN Memory Bounds"},
    )
    doc_3 = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        uploaded_by_user_id=user.id,
        original_filename="study_ssm.pdf",
        storage_key=f"ws-{workspace.id}/docs/study_ssm.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100000,
        sha256="3" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "State Space Models for Sequences"},
    )
    db_session.add_all([user, workspace, doc_1, doc_2, doc_3])
    db_session.flush()

    m1 = ResearchMetadataProfile(
        workspace_id=workspace.id,
        document_id=doc_1.id,
        title="Transformer Evaluation",
        metadata_fields={"keywords": ["attention", "nlp", "scaling"]},
    )
    m2 = ResearchMetadataProfile(
        workspace_id=workspace.id,
        document_id=doc_2.id,
        title="RNN Memory Bounds",
        metadata_fields={"keywords": ["recurrent", "lstm", "nlp"]},
    )
    m3 = ResearchMetadataProfile(
        workspace_id=workspace.id,
        document_id=doc_3.id,
        title="State Space Models for Sequences",
        metadata_fields={"keywords": ["mamba", "linear", "nlp"]},
    )

    meth1 = ResearchMethodologyProfile(
        workspace_id=workspace.id,
        document_id=doc_1.id,
        research_approaches=["empirical"],
        datasets=[{"name": "GLUE"}],
        evaluation_metrics=[{"name": "accuracy"}],
    )
    meth2 = ResearchMethodologyProfile(
        workspace_id=workspace.id,
        document_id=doc_2.id,
        research_approaches=["theoretical"],
        datasets=[],
        evaluation_metrics=[{"name": "perplexity"}],
    )
    meth3 = ResearchMethodologyProfile(
        workspace_id=workspace.id,
        document_id=doc_3.id,
        research_approaches=["empirical"],
        datasets=[],
        evaluation_metrics=[{"name": "inference_speed"}],
    )

    db_session.add_all([m1, m2, m3, meth1, meth2, meth3])
    db_session.commit()

    return {
        "user": user,
        "workspace": workspace,
        "docs": [doc_1, doc_2, doc_3],
    }


def test_coverage_analysis_matrix_and_gaps(db_session, corpus_setup):
    """Test generating a coverage matrix and identifying gaps across the 3 papers."""
    service = DocumentCoverageService(db_session)
    ws = corpus_setup["workspace"]
    docs = corpus_setup["docs"]

    req = CoverageRunRequest(document_ids=[d.id for d in docs])
    run_record = service.analyze_coverage(workspace_id=ws.id, request=req)

    assert run_record.total_documents == 3
    assert run_record.corpus_only_scope is True
    assert "scope_notice" in run_record.gap_summary
    assert "strictly within the selected corpus" in run_record.gap_summary["scope_notice"]

    matrix = run_record.coverage_matrix
    assert len(matrix["documents"]) == 3
    assert matrix["dimension_totals"]["topics"] >= 3

    gaps = run_record.gaps
    assert len(gaps) >= 2

    gap_types = [g.gap_type for g in gaps]
    assert "corpus_coverage_gap" in gap_types
    assert "candidate_research_direction" in gap_types

    comparative_gaps = [g for g in gaps if g.gap_type == "comparative_evidence_gap"]
    assert len(comparative_gaps) >= 1
    assert comparative_gaps[0].dimension == "metric"


def test_corpus_size_validation(db_session, corpus_setup):
    """Corpus analysis must enforce 2 <= N <= 10 documents."""
    service = DocumentCoverageService(db_session)
    ws = corpus_setup["workspace"]
    doc_1 = corpus_setup["docs"][0]

    with pytest.raises(ValueError, match="between 2 and 10 documents"):
        service.analyze_coverage(
            workspace_id=ws.id,
            request=CoverageRunRequest.model_construct(document_ids=[doc_1.id]),
        )


def test_list_and_get_coverage_runs(db_session, corpus_setup):
    """Test retrieving past runs and inspect individual run details."""
    service = DocumentCoverageService(db_session)
    ws = corpus_setup["workspace"]
    docs = corpus_setup["docs"]

    run = service.analyze_coverage(
        workspace_id=ws.id,
        request=CoverageRunRequest(document_ids=[d.id for d in docs]),
    )

    runs = service.list_runs(workspace_id=ws.id)
    assert len(runs) >= 1
    assert runs[0].id == run.id

    fetched = service.get_run(workspace_id=ws.id, run_id=run.id)
    assert fetched is not None
    assert fetched.id == run.id
    assert len(fetched.gaps) == len(run.gaps)
