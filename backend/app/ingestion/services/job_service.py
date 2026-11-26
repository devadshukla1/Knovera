"""Ingestion job tracking and retry orchestration service for Knovera Ingestion (Chunk C2.7 & C2.8)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.ingestion.errors.taxonomy import is_retryable_error, get_safe_error_summary
from backend.app.models.document import Document
from backend.app.models.ingestion_job import IngestionJob

logger = get_logger("knovera.ingestion.jobs")


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures a datetime object is timezone-aware (UTC), supporting SQLite and PostgreSQL."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class IngestionJobService:
    """Manages ingestion job lifecycle, worker locking, exponential backoff, and retry states."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def create_job(
        self,
        db: Session,
        document: Document,
        job_type: str = "document_ingestion",
        max_attempts: Optional[int] = None,
    ) -> IngestionJob:
        """Creates a new queued ingestion job record for a document."""
        now_utc = datetime.now(timezone.utc)
        effective_max = max_attempts if max_attempts is not None else self.settings.INGESTION_MAX_ATTEMPTS

        job = IngestionJob(
            id=uuid.uuid4(),
            document_id=document.id,
            workspace_id=document.workspace_id,
            job_type=job_type,
            status="pending",
            stage="queued",
            attempt_count=0,
            max_attempts=effective_max,
            available_at=now_utc,
            pipeline_version=self.settings.PIPELINE_VERSION,
            processing_metrics={},
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info("Created IngestionJob %s for document %s (type=%s)", job.id, document.id, job_type)
        return job

    def claim_job(
        self,
        db: Session,
        job: IngestionJob,
        worker_id: str,
        lease_seconds: Optional[int] = None,
    ) -> bool:
        """Claims a job with a worker lease, verifying availability and recovering expired leases.

        Returns:
            True if claimed successfully, False if currently locked by an active worker.
        """
        now_utc = datetime.now(timezone.utc)
        effective_lease = lease_seconds if lease_seconds is not None else self.settings.INGESTION_LEASE_SECONDS

        locked_at_utc = _ensure_utc(job.locked_at)
        available_at_utc = _ensure_utc(job.available_at)

        # Check if already running with a valid lease
        if job.status == "running" and locked_at_utc is not None:
            time_since_lock = (now_utc - locked_at_utc).total_seconds()
            if time_since_lock < effective_lease:
                logger.warning(
                    "Job %s claim denied: actively locked by worker '%s' (age: %.1fs < %ds)",
                    job.id,
                    job.locked_by,
                    time_since_lock,
                    effective_lease,
                )
                return False
            else:
                logger.warning(
                    "Job %s recovered from stale worker lease '%s' (age: %.1fs > %ds)",
                    job.id,
                    job.locked_by,
                    time_since_lock,
                    effective_lease,
                )

        # Check availability timestamp for retry backoff
        if available_at_utc and available_at_utc > now_utc:
            logger.info("Job %s not yet available for execution (backoff until %s)", job.id, job.available_at)
            return False

        job.status = "running"
        job.locked_at = now_utc
        job.locked_by = worker_id
        job.attempt_count += 1
        job.updated_at = now_utc
        db.commit()
        db.refresh(job)
        logger.info(
            "Worker '%s' claimed job %s (attempt %d/%d)",
            worker_id,
            job.id,
            job.attempt_count,
            job.max_attempts,
        )
        return True

    def update_stage(self, db: Session, job: IngestionJob, stage: str) -> None:
        """Updates the current execution stage of an active job."""
        job.stage = stage
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)

    def mark_completed(
        self,
        db: Session,
        job: IngestionJob,
        metrics: Optional[Dict[str, Any]] = None,
        stage: str = "ready",
    ) -> None:
        """Marks a job as successfully completed and releases the lock."""
        now_utc = datetime.now(timezone.utc)
        job.status = "completed"
        job.stage = stage
        job.locked_at = None
        job.locked_by = None
        job.completed_at = now_utc
        job.updated_at = now_utc
        if metrics:
            job.processing_metrics = metrics
        db.commit()
        db.refresh(job)
        logger.info("IngestionJob %s completed successfully", job.id)

    def mark_failed(
        self,
        db: Session,
        job: IngestionJob,
        error_code: str,
        error_summary: str,
        retryable: Optional[bool] = None,
    ) -> None:
        """Handles job failure: schedules retry with exponential backoff if eligible, or marks permanent failure."""
        now_utc = datetime.now(timezone.utc)
        safe_summary = get_safe_error_summary(error_code, fallback_message=error_summary)

        # Determine if retryable
        can_retry = is_retryable_error(error_code) if retryable is None else retryable

        if can_retry and job.attempt_count < job.max_attempts:
            # Exponential backoff: base * 2^(attempt - 1), capped at max_delay
            base_delay = self.settings.INGESTION_RETRY_BASE_SECONDS
            max_delay = self.settings.INGESTION_RETRY_MAX_SECONDS
            backoff_seconds = min(base_delay * (2 ** max(0, job.attempt_count - 1)), max_delay)
            next_available = now_utc + timedelta(seconds=backoff_seconds)

            job.status = "retry_wait"
            job.stage = "waiting_retry"
            job.available_at = next_available
            job.locked_at = None
            job.locked_by = None
            job.last_error_code = error_code
            job.last_error_summary = safe_summary
            job.updated_at = now_utc

            logger.info(
                "IngestionJob %s scheduled for retry in %ds (attempt %d/%d) due to %s",
                job.id,
                backoff_seconds,
                job.attempt_count,
                job.max_attempts,
                error_code,
            )
        else:
            job.status = "failed"
            job.stage = "failed"
            job.locked_at = None
            job.locked_by = None
            job.last_error_code = error_code
            job.last_error_summary = safe_summary
            job.updated_at = now_utc
            logger.warning(
                "IngestionJob %s permanently failed (attempt %d/%d): [%s] %s",
                job.id,
                job.attempt_count,
                job.max_attempts,
                error_code,
                safe_summary,
            )

        db.commit()
        db.refresh(job)

    def get_jobs_for_document(self, db: Session, document_id: uuid.UUID) -> List[IngestionJob]:
        """Returns all ingestion jobs for a document in reverse chronological order."""
        return (
            db.query(IngestionJob)
            .filter(IngestionJob.document_id == document_id)
            .order_by(IngestionJob.created_at.desc())
            .all()
        )
