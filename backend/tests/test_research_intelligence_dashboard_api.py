"""Integration Tests for C10.10: Research Intelligence Dashboard API."""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.ml.research.dashboard_service import ResearchDashboardService
from backend.app.models.document import Document
from backend.app.models.research_intelligence import (
    ResearchContradictionRecord,
    ResearchEvidenceValidationRecord,
    ResearchFinding,
    ResearchMetadataProfile,
    ResearchObjectiveProfile,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


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
def dashboard_fixture(db_session):
    """Seed workspace with documents, extraction profiles, validations, and contradiction records."""
    user = User(
        id=uuid.uuid4(),
        email="lead@knovera.test",
        password_hash="mock_hash",
        display_name="Research Director",
    )
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Neuroscience Lab",
        owner_user_id=user.id,
    )
    doc_1 = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        uploaded_by_user_id=user.id,
        original_filename="cortex_study.pdf",
        storage_key=f"ws-{workspace.id}/docs/cortex_study.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100000,
        sha256="1" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "Cortical Dynamics in Mice"},
    )
    doc_2 = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        uploaded_by_user_id=user.id,
        original_filename="hippocampus_study.pdf",
        storage_key=f"ws-{workspace.id}/docs/hippocampus_study.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100000,
        sha256="2" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "Hippocampal Replay Dynamics"},
    )
    db_session.add_all([user, workspace, doc_1, doc_2])
    db_session.flush()

    meta1 = ResearchMetadataProfile(
        workspace_id=workspace.id,
        document_id=doc_1.id,
        title="Cortical Dynamics in Mice",
    )
    obj1 = ResearchObjectiveProfile(
        workspace_id=workspace.id,
        document_id=doc_1.id,
        primary_objective="Investigate sensory gating",
        objectives=[{"statement": "Investigate sensory gating"}],
    )
    f1 = ResearchFinding(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        document_id=doc_1.id,
        finding_type="quantitative",
        original_statement="Gating reduces background sensory noise by 65%.",
        normalized_statement="Gating reduces background sensory noise by 65%.",
        outcome_variable="noise reduction",
        validation_status="supported",
    )
    f2 = ResearchFinding(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        document_id=doc_2.id,
        finding_type="quantitative",
        original_statement="Replay operates independently of background noise.",
        normalized_statement="Replay operates independently of background noise.",
        outcome_variable="noise reduction",
        validation_status="supported",
    )

    val_record = ResearchEvidenceValidationRecord(
        workspace_id=workspace.id,
        document_id=doc_1.id,
        claim_type="finding",
        claim_id=f1.id,
        claim_text=f1.original_statement,
        validation_status="supported",
        validation_tier="tier_2_normalized_overlap",
        confidence_score=0.88,
        exact_match=False,
        normalized_overlap=0.74,
    )

    contra_record = ResearchContradictionRecord(
        workspace_id=workspace.id,
        finding_a_id=f1.id,
        finding_b_id=f2.id,
        document_a_id=doc_1.id,
        document_b_id=doc_2.id,
        contradiction_category="direct_contradiction_candidate",
        evidence_validity_a="supported",
        evidence_validity_b="supported",
        comparability_status="comparable",
        confidence_score=0.82,
        review_status="needs_review",
        human_verified=False,
    )

    db_session.add_all([meta1, obj1, f1, f2, val_record, contra_record])
    db_session.commit()

    return {
        "workspace": workspace,
        "doc_1": doc_1,
        "doc_2": doc_2,
        "f1": f1,
        "f2": f2,
    }


def test_dashboard_summary_projection(db_session, dashboard_fixture):
    """Test full dashboard summary calculation and enrichment."""
    service = ResearchDashboardService(db_session)
    ws = dashboard_fixture["workspace"]

    summary = service.get_dashboard_summary(workspace_id=ws.id)

    assert summary.workspace_id == ws.id
    assert summary.total_research_documents == 2
    assert summary.extraction_stats["metadata_extracted"] == 1
    assert summary.extraction_stats["objectives_extracted"] == 1
    assert summary.total_findings == 2

    # Validation breakdown
    assert summary.validation_stats.get("supported") == 1

    # Contradiction breakdown
    assert summary.contradiction_stats.get("needs_review") == 1

    # Recent items
    assert len(summary.recent_contradictions) == 1
    recent_contra = summary.recent_contradictions[0]
    assert recent_contra.contradiction_category == "direct_contradiction_candidate"
    assert recent_contra.finding_a_statement == "Gating reduces background sensory noise by 65%."
    assert recent_contra.paper_a_title == "cortex_study.pdf"

    assert len(summary.recent_validations) == 1
    assert summary.recent_validations[0].validation_status == "supported"
