"""Unit and Integration Tests for C10.7: Source-Grounded Evidence Validation."""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.ml.research.evidence_validation_service import EvidenceValidationService
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.research_intelligence import (
    ResearchEvidenceValidationRecord,
    ResearchFinding,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.research_intelligence import EvidenceValidationRequest


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
    """Seed user, workspace, and a test research document with chunks."""
    user = User(
        id=uuid.uuid4(),
        email="researcher@knovera.test",
        password_hash="mock_hash",
        display_name="Dr. Evidence",
    )
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Clinical Validation Lab",
        owner_user_id=user.id,
    )
    document = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        uploaded_by_user_id=user.id,
        original_filename="transformer_scaling.pdf",
        storage_key=f"ws-{workspace.id}/docs/transformer_scaling.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100000,
        sha256="1" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "Empirical Scaling Laws for Language Models"},
    )
    db_session.add_all([user, workspace, document])
    db_session.flush()

    chunk_1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        document_id=document.id,
        chunk_index=0,
        content="In our experiments across 500 million tokens, model accuracy scaled smoothly to 87.4% under standard hyperparameters.",
        content_hash="1" * 64,
        page_start=4,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
        token_count=18,
    )
    chunk_2 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        document_id=document.id,
        chunk_index=1,
        content="We observed that learning rate warm-up is strictly required to prevent divergence during the initial 2000 steps.",
        content_hash="2" * 64,
        page_start=6,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
        token_count=19,
    )
    db_session.add_all([chunk_1, chunk_2])
    db_session.commit()

    return {
        "user": user,
        "workspace": workspace,
        "document": document,
        "chunk_1": chunk_1,
        "chunk_2": chunk_2,
    }


def test_tier_1_exact_span_validation(db_session, workspace_setup):
    """Tier 1: Exact string match should return exact character offsets and status 'evidence_matched'."""
    service = EvidenceValidationService(db_session)
    ws = workspace_setup["workspace"]
    doc = workspace_setup["document"]
    chunk_1 = workspace_setup["chunk_1"]

    req = EvidenceValidationRequest(
        document_id=doc.id,
        claim_type="finding",
        claim_text="model accuracy scaled smoothly to 87.4%",
        chunk_id=chunk_1.id,
    )
    record = service.validate_claim(workspace_id=ws.id, request=req)

    assert record.validation_status == "evidence_matched"
    assert record.validation_tier == "tier_1_exact_span"
    assert record.exact_match is True
    assert record.char_start is not None
    assert record.char_end is not None
    assert chunk_1.content[record.char_start:record.char_end].lower() == req.claim_text.lower()
    assert record.confidence_score >= 0.95


def test_tier_2_normalized_overlap_validation(db_session, workspace_setup):
    """Tier 2: Paraphrased claim with substantial overlap should pass with status 'supported'."""
    service = EvidenceValidationService(db_session)
    ws = workspace_setup["workspace"]
    doc = workspace_setup["document"]
    chunk_1 = workspace_setup["chunk_1"]

    req = EvidenceValidationRequest(
        document_id=doc.id,
        claim_type="finding",
        claim_text="Experiments across 500 million tokens show model accuracy scaled smoothly to 87.4 percent.",
        chunk_id=chunk_1.id,
    )
    record = service.validate_claim(workspace_id=ws.id, request=req)

    assert record.validation_status in ("supported", "evidence_matched")
    assert record.normalized_overlap >= 0.50
    assert record.numeric_match is True
    assert record.confidence_score >= 0.75


def test_numerical_mismatch_detection(db_session, workspace_setup):
    """Validates that claims with hallucinated or contradictory numbers are flagged."""
    service = EvidenceValidationService(db_session)
    ws = workspace_setup["workspace"]
    doc = workspace_setup["document"]
    chunk_1 = workspace_setup["chunk_1"]

    req = EvidenceValidationRequest(
        document_id=doc.id,
        claim_type="finding",
        claim_text="Model accuracy scaled to 99.8% over 500 million tokens.",
        chunk_id=chunk_1.id,
    )
    record = service.validate_claim(workspace_id=ws.id, request=req)

    assert record.numeric_match is False
    assert record.rejection_reason is not None
    assert "Numerical value mismatch" in record.rejection_reason
    assert record.validation_status in ("partially_supported", "unsupported")


def test_negation_conflict_detection(db_session, workspace_setup):
    """Validates that polarity or negation inversion between claim and chunk is flagged as conflicting."""
    service = EvidenceValidationService(db_session)
    ws = workspace_setup["workspace"]
    doc = workspace_setup["document"]
    chunk_2 = workspace_setup["chunk_2"]

    req = EvidenceValidationRequest(
        document_id=doc.id,
        claim_type="finding",
        claim_text="Learning rate warm-up is not required to prevent divergence.",
        chunk_id=chunk_2.id,
    )
    record = service.validate_claim(workspace_id=ws.id, request=req)

    assert record.qualifier_match is False
    assert record.validation_status == "conflicting_evidence"
    assert record.rejection_reason is not None


def test_validate_stored_research_finding(db_session, workspace_setup):
    """Test end-to-end validation of an existing persisted ResearchFinding."""
    service = EvidenceValidationService(db_session)
    ws = workspace_setup["workspace"]
    doc = workspace_setup["document"]
    chunk_1 = workspace_setup["chunk_1"]

    finding = ResearchFinding(
        workspace_id=ws.id,
        document_id=doc.id,
        finding_type="quantitative",
        original_statement="model accuracy scaled smoothly to 87.4%",
        normalized_statement="model accuracy scaled smoothly to 87.4%",
        outcome_variable="accuracy",
        reported_value="87.4%",
        numeric_value=87.4,
        evidence=[
            {
                "chunk_id": str(chunk_1.id),
                "page_number": 4,
                "evidence_text": chunk_1.content,
            }
        ],
        validation_status="unvalidated",
    )
    db_session.add(finding)
    db_session.commit()

    record = service.validate_finding(workspace_id=ws.id, finding_id=finding.id)
    assert record.validation_status == "evidence_matched"
    assert finding.validation_status == "evidence_matched"


def test_list_validations_filtering(db_session, workspace_setup):
    """Test querying validation audit logs by workspace, document, and status."""
    service = EvidenceValidationService(db_session)
    ws = workspace_setup["workspace"]
    doc = workspace_setup["document"]
    chunk_1 = workspace_setup["chunk_1"]

    service.validate_claim(
        workspace_id=ws.id,
        request=EvidenceValidationRequest(
            document_id=doc.id,
            claim_text="model accuracy scaled smoothly to 87.4%",
            chunk_id=chunk_1.id,
        ),
    )
    service.validate_claim(
        workspace_id=ws.id,
        request=EvidenceValidationRequest(
            document_id=doc.id,
            claim_text="unrelated hallucinated statement without grounding",
        ),
    )

    all_recs = service.list_validations(workspace_id=ws.id)
    assert len(all_recs) == 2

    matched_recs = service.list_validations(workspace_id=ws.id, status="evidence_matched")
    assert len(matched_recs) == 1
    assert matched_recs[0].validation_status == "evidence_matched"
