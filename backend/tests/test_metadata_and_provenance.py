"""Tests for document metadata assembly and provenance validation (Chunk C2.6)."""

from datetime import datetime, timezone
import io
import uuid
import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.ingestion.chunking.schemas import ChunkSegment, DocumentChunkData
from backend.app.ingestion.metadata.document_metadata import DocumentMetadata
from backend.app.ingestion.metadata.provenance_validator import (
    ProvenanceValidationError,
    ProvenanceValidator,
)
from backend.app.ingestion.schemas.extracted_document import ExtractedBlock, ExtractedDocument
from backend.app.models.document import Document
from backend.app.models.workspace import Workspace


def test_document_metadata_model_instantiation():
    """Verifies DocumentMetadata typed schema enforcement and immutable freezing."""
    doc_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    meta = DocumentMetadata(
        document_id=doc_id,
        workspace_id=ws_id,
        filename="research_report.pdf",
        extension=".pdf",
        media_type="application/pdf",
        file_size_bytes=10240,
        sha256="a" * 64,
        page_count=5,
        slide_count=None,
        extracted_block_count=25,
        total_characters=8500,
        empty_page_count=0,
        empty_slide_count=0,
        parser_name="PyMuPDFParser",
        parser_version="1.0.0",
        cleaning_version="v1.0",
        chunking_version="semantic-v1",
        pipeline_version="v1.0",
        chunk_count=8,
        total_chunk_characters=8400,
        processing_status="queued",
        processing_stage="awaiting_embeddings",
    )

    assert meta.document_id == doc_id
    assert meta.chunk_count == 8
    assert meta.pipeline_version == "v1.0"
    assert meta.page_count == 5

    # Test frozen immutability
    with pytest.raises(Exception):
        meta.chunk_count = 10  # type: ignore


def test_provenance_validator_accepts_valid_pdf_chunks():
    """Valid PDF chunks with 1-based coordinates and source segments pass validation."""
    doc_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    extracted_doc = ExtractedDocument(
        document_id=doc_id,
        filename="test.pdf",
        file_type=".pdf",
        total_pages=3,
        total_characters=300,
        parser_name="PyMuPDFParser",
        parser_version="1.0.0",
        extracted_at=now.isoformat(),
        blocks=[
            ExtractedBlock(block_index=0, block_type="paragraph", source_type="pdf_page", text="Intro block", page_number=1),
            ExtractedBlock(block_index=1, block_type="paragraph", source_type="pdf_page", text="Methods block", page_number=2),
        ],
    )

    chunks = [
        DocumentChunkData(
            id=uuid.uuid4(),
            document_id=doc_id,
            workspace_id=ws_id,
            chunk_index=0,
            content="Intro block",
            content_hash="h1",
            page_start=1,
            page_end=1,
            token_count=10,
            parser_version="1.0.0",
            cleaning_version="v1.0",
            chunking_version="semantic-v1",
            source_segments=[
                ChunkSegment(source_type="pdf_page", block_index=0, page_number=1, start_offset=0, end_offset=11)
            ],
            created_at=now,
        ),
        DocumentChunkData(
            id=uuid.uuid4(),
            document_id=doc_id,
            workspace_id=ws_id,
            chunk_index=1,
            content="Methods block",
            content_hash="h2",
            page_start=2,
            page_end=2,
            token_count=10,
            parser_version="1.0.0",
            cleaning_version="v1.0",
            chunking_version="semantic-v1",
            source_segments=[
                ChunkSegment(source_type="pdf_page", block_index=1, page_number=2, start_offset=0, end_offset=13)
            ],
            created_at=now,
        ),
    ]

    validator = ProvenanceValidator()
    # Should not raise
    validator.validate_chunks_provenance(doc_id, ws_id, chunks, extracted_doc)


def test_provenance_validator_rejects_zero_or_exceeded_page_number():
    """Provenance validator and schemas reject invalid page coordinates."""
    doc_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # 1. Pydantic schema validation rejects 0 or negative page
    with pytest.raises(Exception):
        DocumentChunkData(
            id=uuid.uuid4(),
            document_id=doc_id,
            workspace_id=ws_id,
            chunk_index=0,
            content="Bad coord",
            content_hash="h1",
            page_start=0,  # Invalid: must be >= 1
            page_end=1,
            token_count=5,
            parser_version="1.0.0",
            cleaning_version="v1.0",
            chunking_version="semantic-v1",
            source_segments=[
                ChunkSegment(source_type="pdf_page", block_index=0, page_number=1, start_offset=0, end_offset=9)
            ],
            created_at=now,
        )

    # 2. Provenance validator rejects page exceeding total_pages
    extracted_doc = ExtractedDocument(
        document_id=doc_id,
        filename="test.pdf",
        file_type=".pdf",
        total_pages=2,
        total_characters=100,
        parser_name="PyMuPDFParser",
        parser_version="1.0.0",
        extracted_at=now.isoformat(),
        blocks=[ExtractedBlock(block_index=0, block_type="paragraph", source_type="pdf_page", text="Coord", page_number=1)],
    )

    exceeded_chunks = [
        DocumentChunkData(
            id=uuid.uuid4(),
            document_id=doc_id,
            workspace_id=ws_id,
            chunk_index=0,
            content="Exceeded page",
            content_hash="h1",
            page_start=5,  # Exceeds total_pages=2
            page_end=5,
            token_count=5,
            parser_version="1.0.0",
            cleaning_version="v1.0",
            chunking_version="semantic-v1",
            source_segments=[
                ChunkSegment(source_type="pdf_page", block_index=0, page_number=2, start_offset=0, end_offset=13)
            ],
            created_at=now,
        )
    ]

    validator = ProvenanceValidator()
    with pytest.raises(ProvenanceValidationError) as exc:
        validator.validate_chunks_provenance(doc_id, ws_id, exceeded_chunks, extracted_doc)
    assert "page_start" in str(exc.value) or "exceeds" in str(exc.value)


def test_provenance_validator_rejects_missing_source_segments():
    """Provenance validator rejects chunks that lack source_segments."""
    doc_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    extracted_doc = ExtractedDocument(
        document_id=doc_id,
        filename="test.pdf",
        file_type=".pdf",
        total_pages=1,
        total_characters=50,
        parser_name="PyMuPDFParser",
        parser_version="1.0.0",
        extracted_at=now.isoformat(),
        blocks=[ExtractedBlock(block_index=0, block_type="paragraph", source_type="pdf_page", text="Content", page_number=1)],
    )

    chunks_without_provenance = [
        DocumentChunkData(
            id=uuid.uuid4(),
            document_id=doc_id,
            workspace_id=ws_id,
            chunk_index=0,
            content="Content",
            content_hash="h1",
            page_start=1,
            page_end=1,
            token_count=5,
            parser_version="1.0.0",
            cleaning_version="v1.0",
            chunking_version="semantic-v1",
            source_segments=[],  # Missing!
            created_at=now,
        )
    ]

    validator = ProvenanceValidator()
    with pytest.raises(ProvenanceValidationError) as exc:
        validator.validate_chunks_provenance(doc_id, ws_id, chunks_without_provenance, extracted_doc)
    assert "source_segments" in str(exc.value)


def test_provenance_validator_rejects_page_end_less_than_page_start():
    """Provenance validator rejects chunks where page_end < page_start."""
    doc_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    extracted_doc = ExtractedDocument(
        document_id=doc_id,
        filename="test.pdf",
        file_type=".pdf",
        total_pages=5,
        total_characters=100,
        parser_name="PyMuPDFParser",
        parser_version="1.0.0",
        extracted_at=now.isoformat(),
        blocks=[ExtractedBlock(block_index=0, block_type="paragraph", source_type="pdf_page", text="Inverted pages", page_number=1)],
    )

    bad_chunks = [
        DocumentChunkData(
            id=uuid.uuid4(),
            document_id=doc_id,
            workspace_id=ws_id,
            chunk_index=0,
            content="Inverted pages",
            content_hash="h1",
            page_start=3,
            page_end=2,  # Invalid: page_end < page_start
            token_count=5,
            parser_version="1.0.0",
            cleaning_version="v1.0",
            chunking_version="semantic-v1",
            source_segments=[
                ChunkSegment(source_type="pdf_page", block_index=0, page_number=3, start_offset=0, end_offset=14)
            ],
            created_at=now,
        )
    ]

    validator = ProvenanceValidator()
    with pytest.raises(ProvenanceValidationError) as exc:
        validator.validate_chunks_provenance(doc_id, ws_id, bad_chunks, extracted_doc)
    assert "page_end" in str(exc.value)


def test_database_metadata_columns_populated_on_upload(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """Verifies that uploaded documents have all new C2.6 metadata columns correctly populated in PostgreSQL."""
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "First page content for metadata validation test.")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "Second page content for metadata validation test.")
    buf = io.BytesIO()
    doc.save(buf)
    pdf_bytes = buf.getvalue()

    res = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("meta_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res.status_code == 201
    doc_id = uuid.UUID(res.json()["id"])

    # Query DB record directly
    db_doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert db_doc is not None
    assert db_doc.page_count == 2
    assert db_doc.slide_count is None
    assert db_doc.extracted_block_count >= 2
    assert db_doc.total_characters > 0
    assert db_doc.chunk_count >= 1
    assert db_doc.pipeline_version == "v1.0"
    assert db_doc.processing_status in ("queued", "ready")
    assert db_doc.processing_stage in ("awaiting_embeddings", "ready")
