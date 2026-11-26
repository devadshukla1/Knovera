"""Unified 8-stage document processing pipeline orchestrator for Knovera Ingestion (Phase 2 C2.6–C2.8)."""

from datetime import datetime, timezone
import hashlib
import os
import time
from typing import Any, Dict, Optional, Tuple
import uuid
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.ingestion.chunking.schemas import ChunkingDiagnostics
from backend.app.ingestion.chunking.semantic_chunker import SemanticChunker
from backend.app.ingestion.cleaning.normalizer import TextNormalizer
from backend.app.ingestion.errors.taxonomy import (
    FileIntegrityMismatchError,
    StorageFileMissingError,
    get_safe_error_summary,
    is_retryable_error,
)
from backend.app.ingestion.extractors.dispatcher import get_extractor_for_extension
from backend.app.ingestion.extractors.exceptions import ExtractionException
from backend.app.ingestion.metadata.provenance_validator import ProvenanceValidator
from backend.app.ingestion.schemas.extracted_document import ExtractedDocument
from backend.app.ingestion.services.job_service import IngestionJobService
from backend.app.models.document import Document, DocumentPage
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.ingestion_job import IngestionJob
from backend.app.rag.embeddings.base import EmbeddingProvider
from backend.app.rag.embeddings.model_manager import EmbeddingModelManager
from backend.app.rag.vector_store.chroma_repository import ChromaVectorRepository
from backend.app.rag.vector_store.exceptions import UpsertFailedError
from backend.app.rag.vector_store.schemas import VectorRecord
from backend.app.storage.base import StorageService

logger = get_logger("knovera.ingestion.pipeline")


class DocumentProcessingPipeline:
    """End-to-end 8-stage document processing orchestrator.

    Stages:
        1. Validation & Integrity Check
        2. Format-Specific Extraction (PDF, DOCX, PPTX)
        3. Text Cleaning & Normalisation
        4. Metadata Assembly
        5. Semantic Chunking
        6. Provenance & Coordinate Validation
        7. Transactional Persistence
        8. Vector Embedding & ChromaDB Indexing (Phase 3 C3.1–C3.3)
    """

    def __init__(
        self,
        normalizer: Optional[TextNormalizer] = None,
        chunker: Optional[SemanticChunker] = None,
        provenance_validator: Optional[ProvenanceValidator] = None,
        job_service: Optional[IngestionJobService] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_repository: Optional[ChromaVectorRepository] = None,
    ) -> None:
        self.settings = get_settings()
        self.normalizer = normalizer or TextNormalizer()
        self.chunker = chunker or SemanticChunker()
        self.validator = provenance_validator or ProvenanceValidator()
        self.job_service = job_service or IngestionJobService()
        self.embedding_provider = embedding_provider
        self.vector_repository = vector_repository

    def process_document(
        self,
        db: Session,
        document: Document,
        storage: StorageService,
        job: Optional[IngestionJob] = None,
        worker_id: str = "orchestrator-main",
    ) -> Tuple[ExtractedDocument, ChunkingDiagnostics, Dict[str, Any]]:
        """Executes the 8-stage pipeline with strict validation, metrics, and error classification.

        Returns:
            Tuple of (ExtractedDocument, ChunkingDiagnostics, processing_metrics_dict).
        """
        start_time = time.perf_counter()
        metrics: Dict[str, Any] = {
            "pipeline_version": self.settings.PIPELINE_VERSION,
            "stages": {},
        }

        # Associate or create IngestionJob if not provided
        if job is None:
            job = self.job_service.create_job(db, document)

        # Claim the job lock
        claimed = self.job_service.claim_job(db, job, worker_id=worker_id)
        if not claimed:
            logger.warning("Could not claim job %s for document %s; aborting execution", job.id, document.id)
            raise ExtractionException(
                f"Document {document.id} is currently locked by another worker.",
                error_code="job_already_running",
            )

        now_utc = datetime.now(timezone.utc)
        file_ext = document.file_extension.lower()

        try:
            # ---------------------------------------------------------
            # Stage 1: Validation & Integrity Check
            # ---------------------------------------------------------
            s1_start = time.perf_counter()
            self.job_service.update_stage(db, job, "validation")
            document.processing_status = "extracting"
            document.processing_stage = "validation"
            document.updated_at = now_utc
            db.commit()

            file_path = storage.get_absolute_path(document.storage_key)
            if not os.path.exists(file_path):
                raise StorageFileMissingError(
                    f"Physical file missing for document {document.id} at {document.storage_key}"
                )

            # Verify cryptographic SHA-256 integrity
            sha = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha.update(chunk)
            computed_hash = sha.hexdigest().lower()

            if computed_hash != document.sha256.lower():
                raise FileIntegrityMismatchError(
                    f"File integrity mismatch for document {document.id}: expected {document.sha256}, got {computed_hash}"
                )
            metrics["stages"]["validation_duration_ms"] = round((time.perf_counter() - s1_start) * 1000, 2)

            # ---------------------------------------------------------
            # Stage 2: Format-Specific Extraction
            # ---------------------------------------------------------
            s2_start = time.perf_counter()
            stage_name = f"{file_ext.lstrip('.')}_extraction"
            self.job_service.update_stage(db, job, stage_name)
            document.processing_stage = stage_name
            document.updated_at = datetime.now(timezone.utc)
            db.commit()

            extractor = get_extractor_for_extension(file_ext)
            logger.info("Extracting document %s using %s", document.id, extractor.__class__.__name__)
            extracted_doc: ExtractedDocument = extractor.extract_document(
                file_path=file_path,
                document_id=document.id,
            )

            # If PDF, populate document_pages records
            if file_ext == ".pdf":
                db.query(DocumentPage).filter(DocumentPage.document_id == document.id).delete()
                pages_dict: dict[int, list[str]] = {}
                for b in extracted_doc.blocks:
                    if b.page_number:
                        pages_dict.setdefault(b.page_number, []).append(b.text)

                total_pages = extracted_doc.total_pages or (max(pages_dict.keys()) if pages_dict else 1)
                for page_num in range(1, total_pages + 1):
                    p_texts = pages_dict.get(page_num, [])
                    full_p_text = "\n\n".join(p_texts).strip()
                    page_record = DocumentPage(
                        workspace_id=document.workspace_id,
                        document_id=document.id,
                        page_number=page_num,
                        extracted_text=full_p_text,
                        character_count=len(full_p_text),
                        is_empty=len(full_p_text) == 0,
                        warnings=[],
                        created_at=now_utc,
                    )
                    db.add(page_record)

            metrics["stages"]["extraction_duration_ms"] = round((time.perf_counter() - s2_start) * 1000, 2)

            # ---------------------------------------------------------
            # Stage 3: Text Cleaning & Normalisation
            # ---------------------------------------------------------
            s3_start = time.perf_counter()
            self.job_service.update_stage(db, job, "text_cleaning")
            document.processing_status = "chunking"
            document.processing_stage = "text_cleaning"
            document.updated_at = datetime.now(timezone.utc)
            db.commit()

            logger.info("Normalising document %s", document.id)
            normalised_doc = self.normalizer.normalize_document(extracted_doc)
            metrics["stages"]["cleaning_duration_ms"] = round((time.perf_counter() - s3_start) * 1000, 2)

            # ---------------------------------------------------------
            # Stage 4: Metadata Assembly
            # ---------------------------------------------------------
            s4_start = time.perf_counter()
            self.job_service.update_stage(db, job, "metadata_assembly")
            document.processing_stage = "metadata_assembly"
            document.updated_at = datetime.now(timezone.utc)
            db.commit()

            # Assemble counts
            block_count = len(extracted_doc.blocks)
            total_chars = extracted_doc.total_characters
            slide_count = extracted_doc.total_slides
            page_count = extracted_doc.total_pages

            metrics["stages"]["metadata_assembly_duration_ms"] = round((time.perf_counter() - s4_start) * 1000, 2)

            # ---------------------------------------------------------
            # Stage 5: Semantic Chunking
            # ---------------------------------------------------------
            s5_start = time.perf_counter()
            self.job_service.update_stage(db, job, "semantic_chunking")
            document.processing_stage = "semantic_chunking"
            document.updated_at = datetime.now(timezone.utc)
            db.commit()

            logger.info("Semantic chunking document %s", document.id)
            chunks, diagnostics = self.chunker.chunk_document(
                document=normalised_doc,
                workspace_id=document.workspace_id,
            )
            metrics["stages"]["chunking_duration_ms"] = round((time.perf_counter() - s5_start) * 1000, 2)

            # ---------------------------------------------------------
            # Stage 6: Provenance & Coordinate Validation
            # ---------------------------------------------------------
            s6_start = time.perf_counter()
            self.job_service.update_stage(db, job, "provenance_validation")
            document.processing_stage = "provenance_validation"
            document.updated_at = datetime.now(timezone.utc)
            db.commit()

            logger.info("Validating provenance for %d chunks of document %s", len(chunks), document.id)
            self.validator.validate_chunks_provenance(
                document_id=document.id,
                workspace_id=document.workspace_id,
                chunks=chunks,
                extracted_doc=extracted_doc,
            )
            metrics["stages"]["provenance_duration_ms"] = round((time.perf_counter() - s6_start) * 1000, 2)

            # ---------------------------------------------------------
            # Stage 7: Transactional Persistence
            # ---------------------------------------------------------
            s7_start = time.perf_counter()
            self.job_service.update_stage(db, job, "persistence")
            document.processing_stage = "persistence"
            document.updated_at = datetime.now(timezone.utc)
            db.commit()

            # Idempotent replacement: delete previous chunks for this document
            db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()

            for chunk_data in chunks:
                chunk_record = DocumentChunk(
                    id=chunk_data.id,
                    workspace_id=document.workspace_id,
                    document_id=document.id,
                    chunk_index=chunk_data.chunk_index,
                    content=chunk_data.content,
                    content_hash=chunk_data.content_hash,
                    page_start=chunk_data.page_start,
                    page_end=chunk_data.page_end,
                    slide_number=chunk_data.slide_number,
                    section_title=chunk_data.section_title,
                    source_start_offset=chunk_data.source_start_offset,
                    source_end_offset=chunk_data.source_end_offset,
                    token_count=chunk_data.token_count,
                    token_count_method=chunk_data.token_count_method,
                    parser_version=chunk_data.parser_version,
                    cleaning_version=chunk_data.cleaning_version,
                    chunking_version=chunk_data.chunking_version,
                    source_segments=[seg.model_dump() for seg in chunk_data.source_segments],
                    created_at=chunk_data.created_at,
                )
                db.add(chunk_record)

            # Update document model columns per C2.6 specification
            document.page_count = page_count
            document.slide_count = slide_count
            document.extracted_block_count = block_count
            document.total_characters = total_chars
            document.chunk_count = len(chunks)
            document.pipeline_version = self.settings.PIPELINE_VERSION
            document.extraction_metadata = {
                "parser": extracted_doc.parser_name,
                "parser_version": extracted_doc.parser_version,
                "extracted_at": extracted_doc.extracted_at,
                "file_type": extracted_doc.file_type,
                "total_pages": page_count,
                "total_slides": slide_count,
                "total_blocks": block_count,
                "total_characters": total_chars,
                "cleaning_stats": normalised_doc.cleaning_metadata.model_dump(),
                "chunking_stats": diagnostics.model_dump(),
                "warnings": extracted_doc.warnings,
            }
            metrics["stages"]["persistence_duration_ms"] = round((time.perf_counter() - s7_start) * 1000, 2)

            # ---------------------------------------------------------
            # Stage 8: Vector Embedding & ChromaDB Indexing (Phase 3 C3.1–C3.3)
            # ---------------------------------------------------------
            s8_start = time.perf_counter()
            self.job_service.update_stage(db, job, "embedding_indexing")
            document.processing_stage = "embedding_indexing"
            document.updated_at = datetime.now(timezone.utc)
            db.commit()

            provider = self.embedding_provider or EmbeddingModelManager.get_instance().get_provider()
            vector_repo = self.vector_repository or ChromaVectorRepository(embedding_provider=provider)

            indexed_count = 0
            if chunks:
                chunk_texts = [c.content for c in chunks]
                embeddings = provider.encode_documents(chunk_texts)

                records = []
                for chunk_item, emb in zip(chunks, embeddings):
                    records.append(
                        VectorRecord(
                            id=str(chunk_item.id),
                            embedding=emb,
                            metadata={
                                "chunk_id": str(chunk_item.id),
                                "document_id": str(document.id),
                                "workspace_id": str(document.workspace_id),
                                "chunk_index": chunk_item.chunk_index,
                                "page_start": chunk_item.page_start if chunk_item.page_start is not None else -1,
                                "page_end": chunk_item.page_end if chunk_item.page_end is not None else -1,
                                "slide_number": chunk_item.slide_number if chunk_item.slide_number is not None else -1,
                                "token_count": chunk_item.token_count,
                                "content_hash": chunk_item.content_hash,
                                "parser_version": chunk_item.parser_version,
                                "chunking_version": chunk_item.chunking_version,
                            },
                        )
                    )
                indexed_count = vector_repo.upsert_records(records)
                if indexed_count != len(chunks):
                    raise UpsertFailedError(
                        f"Expected {len(chunks)} vectors indexed, but Chroma accepted {indexed_count}"
                    )

            metrics["stages"]["embedding_indexing_duration_ms"] = round((time.perf_counter() - s8_start) * 1000, 2)
            total_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            metrics["total_duration_ms"] = total_duration_ms

            # State Transition: document status becomes 'ready' ONLY after vector indexing is verified
            document.processing_status = "ready"
            document.processing_stage = "ready"
            document.error_code = None
            document.error_summary = None
            document.updated_at = datetime.now(timezone.utc)

            doc_meta = dict(document.extraction_metadata or {})
            doc_meta["vector_indexing"] = {
                "indexed_vectors": indexed_count,
                "model_id": provider.get_model_id(),
                "model_revision": provider.get_model_revision(),
                "dimension": provider.get_dimension(),
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }
            document.extraction_metadata = doc_meta

            # Mark IngestionJob completed with stage="ready"
            self.job_service.mark_completed(db, job, metrics=metrics, stage="ready")

            db.commit()
            db.refresh(document)

            # Invalidate in-memory BM25 index cache for this workspace to ensure immediate freshness
            try:
                from backend.app.rag.retrieval.bm25.cache import BM25IndexCache
                BM25IndexCache.get_instance().invalidate(document.workspace_id)
            except Exception as inv_exc:
                logger.warning("Failed to invalidate BM25 index cache for workspace %s: %s", document.workspace_id, inv_exc)

            logger.info(
                "Pipeline completed for document %s: %d chunks generated and %d vectors indexed in %.2fms",
                document.id,
                len(chunks),
                indexed_count,
                total_duration_ms,
            )
            return extracted_doc, diagnostics, metrics

        except Exception as exc:
            db.rollback()
            total_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            metrics["total_duration_ms"] = total_duration_ms
            metrics["failed_at"] = datetime.now(timezone.utc).isoformat()

            error_code = getattr(exc, "error_code", "document_processing_failed")
            raw_summary = str(exc)
            safe_summary = get_safe_error_summary(error_code, fallback_message=raw_summary)

            logger.warning(
                "Document %s processing failed in stage '%s' (%s): %s",
                document.id,
                job.stage,
                error_code,
                raw_summary,
            )

            # Update document failure state
            document.processing_status = "failed"
            document.error_code = error_code
            document.error_summary = safe_summary
            document.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(document)

            # Update job state with retry evaluation
            retryable = is_retryable_error(exc)
            self.job_service.mark_failed(
                db=db,
                job=job,
                error_code=error_code,
                error_summary=safe_summary,
                retryable=retryable,
            )

            if isinstance(exc, ExtractionException):
                raise
            raise ExtractionException(f"Processing failed: {exc}", error_code=error_code) from exc
