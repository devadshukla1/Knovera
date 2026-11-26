"""Tests for IngestionJobService lifecycle, worker locking, and retry backoff (Chunk C2.7 & C2.8)."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy.orm import Session

from backend.app.ingestion.errors.taxonomy import is_retryable_error
from backend.app.ingestion.services.job_service import IngestionJobService, _ensure_utc
from backend.app.models.document import Document
from backend.app.models.workspace import Workspace


@pytest.fixture
def test_document(db_session: Session, test_workspace: Workspace) -> Document:
    now = datetime.now(timezone.utc)
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_workspace.owner_user_id,
        original_filename="jobs_test.pdf",
        storage_key="test/jobs_test.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=512,
        sha256="b" * 64,
        processing_status="queued",
        extraction_metadata={},
        created_at=now,
        updated_at=now,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def test_job_service_lifecycle_success(db_session: Session, test_document: Document):
    """Verifies complete standard lifecycle from pending to running to completed."""
    service = IngestionJobService()

    # 1. Create job
    job = service.create_job(db_session, test_document, max_attempts=3)
    assert job.status == "pending"
    assert job.attempt_count == 0
    assert job.max_attempts == 3

    # 2. Claim job
    claimed = service.claim_job(db_session, job, worker_id="worker-node-1")
    assert claimed is True
    assert job.status == "running"
    assert job.locked_by == "worker-node-1"
    assert job.attempt_count == 1
    assert job.locked_at is not None

    # 3. Update stage
    service.update_stage(db_session, job, "semantic_chunking")
    assert job.stage == "semantic_chunking"

    # 4. Mark completed
    service.mark_completed(db_session, job, metrics={"total_duration_ms": 120.5})
    assert job.status == "completed"
    assert job.stage in ("awaiting_embeddings", "ready")
    assert job.locked_at is None
    assert job.locked_by is None
    assert job.completed_at is not None
    assert job.processing_metrics["total_duration_ms"] == 120.5


def test_job_worker_lease_and_stale_recovery(db_session: Session, test_document: Document):
    """Active worker lock rejects competing claims; stale lease is automatically recovered."""
    service = IngestionJobService()
    job = service.create_job(db_session, test_document)

    # Worker 1 claims with 60-second lease
    claimed1 = service.claim_job(db_session, job, worker_id="worker-alpha", lease_seconds=60)
    assert claimed1 is True

    # Worker 2 attempts to claim while Worker 1 is still active -> REJECTED
    claimed2 = service.claim_job(db_session, job, worker_id="worker-beta", lease_seconds=60)
    assert claimed2 is False
    assert job.locked_by == "worker-alpha"

    # Simulate worker-alpha crashing and lease expiring (simulate locked_at 120s ago)
    job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    db_session.commit()

    # Worker 2 attempts to claim again -> SUCCEEDS by recovering stale lease
    claimed3 = service.claim_job(db_session, job, worker_id="worker-beta", lease_seconds=60)
    assert claimed3 is True
    assert job.locked_by == "worker-beta"
    assert job.attempt_count == 2


def test_job_retry_exponential_backoff_and_limit(db_session: Session, test_document: Document):
    """Retryable errors schedule retry with exponential backoff until max_attempts reached."""
    service = IngestionJobService()
    job = service.create_job(db_session, test_document, max_attempts=2)

    # Attempt 1: Claim and fail with retryable error
    service.claim_job(db_session, job, worker_id="worker-1")
    service.mark_failed(
        db_session,
        job,
        error_code="storage_write_failed",
        error_summary="Temporary disk IO failure",
        retryable=True,
    )

    assert job.status == "retry_wait"
    assert job.attempt_count == 1
    assert _ensure_utc(job.available_at) > datetime.now(timezone.utc)
    assert job.locked_by is None

    # Fast-forward available_at
    job.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    # Attempt 2: Claim again and fail
    service.claim_job(db_session, job, worker_id="worker-1")
    assert job.attempt_count == 2
    service.mark_failed(
        db_session,
        job,
        error_code="storage_write_failed",
        error_summary="Temporary disk IO failure",
        retryable=True,
    )

    # Max attempts reached -> permanent failure
    assert job.status == "failed"
    assert job.attempt_count == 2
    assert job.last_error_code == "storage_write_failed"


def test_retryable_error_taxonomy_checks():
    """Verifies that permanent errors are never retryable, while transient errors are."""
    assert is_retryable_error("storage_write_failed") is True
    assert is_retryable_error("database_persistence_failed") is True
    assert is_retryable_error("connection_error") is True

    # Permanent errors must NOT be retryable
    assert is_retryable_error("duplicate_document") is False
    assert is_retryable_error("unsupported_file_type") is False
    assert is_retryable_error("invalid_pdf") is False
    assert is_retryable_error("pdf_encrypted") is False
    assert is_retryable_error("chunk_provenance_invalid") is False
