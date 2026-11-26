"""Document upload, reprocessing, and ingestion API endpoints for Knovera Phase 2 (C2.1–C2.8)."""

from datetime import datetime, timezone
import os
import re
from typing import List, Optional
import uuid
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_user_workspace
from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.ingestion.errors.taxonomy import DuplicateDocumentError
from backend.app.ingestion.extractors.exceptions import (
    DOCXEncryptedError,
    ExtractionException,
    InvalidDOCXError,
    InvalidPDFError,
    InvalidPDFSignatureError,
    InvalidPPTXError,
    NoExtractableTextError,
    PDFEncryptedError,
    PDFPageLimitExceededError,
    PDFTextLimitExceededError,
    PPTXEncryptedError,
    SlideLimitExceededError,
    UnsupportedFormatError,
)
from backend.app.ingestion.pipeline.orchestrator import DocumentProcessingPipeline
from backend.app.ingestion.services.duplicate_service import DuplicateDetectionService
from backend.app.ingestion.services.job_service import IngestionJobService
from backend.app.models.document import Document, DocumentPage
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.document import (
    DocumentChunkResponse,
    DocumentChunksListResponse,
    DocumentDetailResponse,
    DocumentPageResponse,
    DocumentPagesListResponse,
    DocumentResponse,
    IngestionJobsListResponse,
)
from backend.app.storage import get_storage_service
from backend.app.storage.base import StorageService
from backend.app.storage.exceptions import FileTooLargeError, PathTraversalError

logger = get_logger("knovera.api.documents")
router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}
MIME_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


def sanitize_filename(raw_filename: Optional[str]) -> str:
    """Sanitizes an untrusted filename, stripping directory traversal tokens and control characters."""
    if not raw_filename or not raw_filename.strip():
        return "document.pdf"

    # Remove directory paths
    base = os.path.basename(raw_filename.replace("\\", "/"))
    # Remove control characters and null bytes
    sanitized = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    # Strip dangerous prefix dots
    sanitized = sanitized.lstrip(".")

    if not sanitized:
        sanitized = "document.pdf"

    # Restrict length
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        sanitized = f"{name[:250 - len(ext)]}{ext}"

    return sanitized


@router.post(
    "/{workspace_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a document (PDF, DOCX, PPTX) into a workspace",
)
async def upload_document(
    workspace_id: uuid.UUID,
    file: UploadFile = File(..., description="Document file to upload (PDF, DOCX, PPTX)"),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    """Uploads a document to private workspace storage, validates it, and triggers processing."""
    raw_filename = file.filename or ""
    clean_filename = sanitize_filename(raw_filename)
    _, ext = os.path.splitext(clean_filename.lower())

    # 1. Validate file extension (.pdf, .docx, .pptx, .txt, .md)
    if ext not in SUPPORTED_EXTENSIONS:
        logger.warning(
            "Rejected unsupported file extension '%s' for workspace %s",
            ext,
            workspace.id,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error_code": "unsupported_file_type",
                "message": f"Only PDF (.pdf), Word (.docx), PowerPoint (.pptx), and Text (.txt) documents are supported. Received '{ext}'.",
            },
        )

    # 2. Read initial header bytes to verify signature and ensure file is not empty
    header_bytes = await file.read(1024)
    if not header_bytes or len(header_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "empty_file", "message": "Uploaded file is empty (0 bytes)."},
        )

    # Magic signature and format check
    if ext == ".pdf":
        if b"%PDF-" not in header_bytes:
            logger.warning("Missing %%PDF- magic signature in uploaded file '%s'", clean_filename)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={
                    "error_code": "invalid_pdf_signature",
                    "message": "File does not contain a valid %PDF- header signature.",
                },
            )
    elif ext in (".docx", ".pptx"):
        # ZIP magic signature: PK\x03\x04
        if not header_bytes.startswith(b"PK\x03\x04"):
            logger.warning("Missing PK zip signature in OpenXML file '%s'", clean_filename)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={
                    "error_code": "invalid_zip_signature",
                    "message": f"File does not contain a valid {ext.upper()} ZIP package signature.",
                },
            )
    elif ext in (".txt", ".md"):
        # Text encoding check: verify sample bytes can be decoded as text
        decoded_sample = None
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                decoded_sample = header_bytes.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if decoded_sample is None:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={
                    "error_code": "invalid_text_encoding",
                    "message": "File is binary or could not be decoded as text.",
                },
            )

    # Rewind stream for full save
    await file.seek(0)

    # 3. Generate private server-side storage key
    document_id = uuid.uuid4()
    storage_key = f"documents/{workspace.id}/{document_id}/original{ext}"
    media_type = MIME_MAP.get(ext, file.content_type or "application/octet-stream")

    # 4. Stream and store original file safely
    try:
        file_size, sha256_hex = await storage.save_upload(
            upload_file=file,
            storage_key=storage_key,
            max_size_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
        )
    except FileTooLargeError:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error_code": "file_too_large",
                "message": f"File exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes.",
            },
        )
    except PathTraversalError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "invalid_storage_key",
                "message": "Storage key validation failed.",
            },
        )
    except Exception as exc:
        logger.exception("Storage write failed for workspace %s", workspace.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "storage_write_failed",
                "message": "An error occurred while saving the uploaded file.",
            },
        ) from exc

    # 5. Check workspace-scoped duplicate detection (Chunk C2.8)
    duplicate_service = DuplicateDetectionService()

    # If an earlier attempt of this exact file previously failed in this workspace,
    # clean up the failed record to allow a safe retry without unique constraint collision.
    failed_doc = (
        db.query(Document)
        .filter(
            Document.workspace_id == workspace.id,
            Document.sha256 == sha256_hex,
            Document.deleted_at.is_(None),
            Document.processing_status == "failed",
        )
        .first()
    )
    if failed_doc:
        logger.info(
            "Soft-deleting prior failed document %s for sha256 %s to allow safe retry",
            failed_doc.id,
            sha256_hex,
        )
        failed_doc.deleted_at = datetime.now(timezone.utc)
        db.flush()

    try:
        duplicate_service.ensure_not_duplicate(db, workspace.id, sha256_hex)
    except DuplicateDocumentError as exc:
        storage.delete_file(storage_key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "duplicate_document",
                "error_code": "duplicate_document",
                "message": "A document with identical content already exists in this workspace.",
                "details": {"existing_document_id": str(exc.existing_document_id)},
            },
        ) from exc

    # 6. Create PostgreSQL document record
    now_utc = datetime.now(timezone.utc)
    document = Document(
        id=document_id,
        workspace_id=workspace.id,
        uploaded_by_user_id=current_user.id,
        original_filename=clean_filename,
        storage_key=storage_key,
        media_type=media_type,
        file_extension=ext,
        file_size_bytes=file_size,
        sha256=sha256_hex,
        processing_status="extracting",
        processing_stage=f"{ext.lstrip('.')}_extraction",
        extraction_metadata={},
        pipeline_version=settings.PIPELINE_VERSION,
        created_at=now_utc,
        updated_at=now_utc,
    )

    try:
        db.add(document)
        db.commit()
        db.refresh(document)
    except IntegrityError as exc:
        db.rollback()
        storage.delete_file(storage_key)
        dup_err = duplicate_service.handle_integrity_error(db, workspace.id, sha256_hex, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "duplicate_document",
                "error_code": "duplicate_document",
                "message": "A document with identical content already exists in this workspace.",
                "details": {"existing_document_id": str(dup_err.existing_document_id)},
            },
        ) from exc
    except Exception as exc:
        db.rollback()
        storage.delete_file(storage_key)
        logger.exception("Failed to insert document record for %s", clean_filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "database_persistence_failed",
                "message": "Failed to persist document metadata in database.",
            },
        ) from exc

    # 7. Execute 8-stage document processing pipeline (Extract -> Clean -> Chunk -> Validate)
    pipeline = DocumentProcessingPipeline()
    try:
        pipeline.process_document(db, document, storage)
        db.refresh(document)
    except (
        InvalidPDFSignatureError,
        InvalidPDFError,
        PDFEncryptedError,
        PDFPageLimitExceededError,
        PDFTextLimitExceededError,
        InvalidDOCXError,
        DOCXEncryptedError,
        InvalidPPTXError,
        PPTXEncryptedError,
        SlideLimitExceededError,
        UnsupportedFormatError,
        NoExtractableTextError,
        ExtractionException,
    ) as exc:
        db.refresh(document)
        error_code = getattr(exc, "error_code", "document_processing_failed")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": error_code,
                "message": str(exc),
                "document_id": str(document.id),
            },
        ) from exc

    return document


@router.post(
    "/{workspace_id}/documents/{document_id}/reprocess",
    response_model=DocumentDetailResponse,
    summary="Reprocess an existing document through the ingestion pipeline",
)
def reprocess_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> DocumentDetailResponse:
    """Idempotently reprocesses an existing document, replacing previous pages and chunks."""
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == workspace.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in this workspace",
        )

    # Guard: check if already currently processing
    if document.processing_status in ("extracting", "chunking"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "document_currently_processing",
                "message": f"Document {document_id} is already actively being processed.",
            },
        )

    pipeline = DocumentProcessingPipeline()
    try:
        pipeline.process_document(db, document, storage)
        db.refresh(document)
    except ExtractionException as exc:
        db.refresh(document)
        error_code = getattr(exc, "error_code", "document_processing_failed")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": error_code,
                "message": str(exc),
                "document_id": str(document.id),
            },
        ) from exc

    return document


@router.get(
    "/{workspace_id}/documents/{document_id}/jobs",
    response_model=IngestionJobsListResponse,
    summary="Get ingestion job execution history for a document",
)
def get_document_jobs(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> IngestionJobsListResponse:
    """Retrieves all historical ingestion jobs and execution metrics for a document."""
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == workspace.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in this workspace",
        )

    job_service = IngestionJobService()
    jobs = job_service.get_jobs_for_document(db, document.id)

    return IngestionJobsListResponse(
        document_id=document.id,
        total_jobs=len(jobs),
        jobs=jobs,
    )


@router.get(
    "/{workspace_id}/documents",
    response_model=List[DocumentResponse],
    summary="List all documents in a workspace",
)
def list_workspace_documents(
    workspace_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> List[DocumentResponse]:
    """Retrieves all non-deleted documents for the specified workspace."""
    documents = (
        db.query(Document)
        .filter(
            Document.workspace_id == workspace.id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.created_at.desc())
        .all()
    )
    return documents


@router.get(
    "/{workspace_id}/documents/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get document details by ID",
)
def get_document_detail(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> DocumentDetailResponse:
    """Retrieves detailed metadata for a single workspace document."""
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == workspace.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in this workspace",
        )
    return document


@router.get(
    "/{workspace_id}/documents/{document_id}/pages",
    response_model=DocumentPagesListResponse,
    summary="Get extracted pages for a document",
)
def get_document_pages(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
    page_start: Optional[int] = Query(default=None, ge=1),
    page_end: Optional[int] = Query(default=None, ge=1),
) -> DocumentPagesListResponse:
    """Retrieves extracted page-by-page text and provenance for a document."""
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == workspace.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in this workspace",
        )

    query = db.query(DocumentPage).filter(DocumentPage.document_id == document.id)
    if page_start is not None:
        query = query.filter(DocumentPage.page_number >= page_start)
    if page_end is not None:
        query = query.filter(DocumentPage.page_number <= page_end)

    pages = query.order_by(DocumentPage.page_number.asc()).all()
    total_pages = document.page_count or len(pages)

    return DocumentPagesListResponse(
        document_id=document.id,
        total_pages=total_pages,
        pages=pages,
    )


@router.get(
    "/{workspace_id}/documents/{document_id}/chunks",
    response_model=DocumentChunksListResponse,
    summary="List all semantic chunks for a document",
)
def get_document_chunks(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> DocumentChunksListResponse:
    """Retrieves all semantically chunked records with source provenance for a document."""
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == workspace.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in this workspace",
        )

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )

    return DocumentChunksListResponse(
        document_id=document.id,
        total_chunks=len(chunks),
        chunks=chunks,
    )


@router.delete(
    "/{workspace_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and purge its vectors from ChromaDB",
)
def delete_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> None:
    """Soft-deletes a document and purges its indexed vectors from ChromaDB."""
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == workspace.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in this workspace",
        )

    # 1. Purge vectors from ChromaDB
    try:
        from backend.app.rag.vector_store.chroma_repository import ChromaVectorRepository
        repo = ChromaVectorRepository()
        repo.delete_by_document(workspace_id=workspace.id, document_id=document.id)
    except Exception as exc:
        logger.warning("Failed to delete vectors for document %s from Chroma: %s", document.id, exc)

    # 2. Delete file from physical storage
    try:
        storage.delete_file(document.storage_key)
    except Exception as exc:
        logger.warning("Failed to delete storage file %s: %s", document.storage_key, exc)

    # 3. Soft-delete document
    document.deleted_at = datetime.now(timezone.utc)
    document.processing_status = "deleted"
    db.commit()

    # 4. Invalidate BM25 lexical index cache for workspace
    try:
        from backend.app.rag.retrieval.bm25.cache import BM25IndexCache
        BM25IndexCache.get_instance().invalidate(workspace.id)
    except Exception as exc:
        logger.warning("Failed to invalidate BM25 cache for workspace %s: %s", workspace.id, exc)
