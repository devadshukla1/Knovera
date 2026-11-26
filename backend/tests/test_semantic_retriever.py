"""Tests for Semantic Retriever, Query Validator, and Result Hydrator (Phase 3 C3.3)."""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.workspace import Workspace
from backend.app.rag.embeddings.fake_provider import DeterministicFakeEmbeddingProvider
from backend.app.rag.retrieval.exceptions import (
    DocumentScopeException,
    InvalidQueryException,
)
from backend.app.rag.retrieval.query_validator import QueryValidator
from backend.app.rag.retrieval.semantic_retriever import SemanticRetriever
from backend.app.rag.vector_store.chroma_repository import ChromaVectorRepository
from backend.app.rag.vector_store.fake_client import InMemoryChromaClient
from backend.app.rag.vector_store.schemas import VectorRecord


def test_query_validator_validations():
    """Verifies query validation rules for empty, whitespace, and budget truncation."""
    validator = QueryValidator()

    # Empty query
    with pytest.raises(InvalidQueryException) as exc:
        validator.validate_query("")
    assert "cannot be empty" in str(exc.value)

    # Whitespace-only query
    with pytest.raises(InvalidQueryException) as exc:
        validator.validate_query("   \t \n  ")
    assert "whitespace" in str(exc.value)

    # Excessive query length is safely truncated to EMBEDDING_QUERY_MAX_LENGTH (256)
    long_query = "word " * 100
    validated = validator.validate_query(long_query)
    assert len(validated) <= validator.settings.EMBEDDING_QUERY_MAX_LENGTH


def test_query_validator_document_scope(db_session: Session, test_workspace: Workspace):
    """Verifies that requesting documents not in workspace raises DocumentScopeException."""
    validator = QueryValidator()
    foreign_doc_id = uuid.uuid4()

    with pytest.raises(DocumentScopeException) as exc:
        validator.validate_document_scope(
            db=db_session,
            workspace_id=test_workspace.id,
            document_ids=[foreign_doc_id],
        )
    assert str(foreign_doc_id) in str(exc.value)


def test_semantic_retriever_empty_workspace(db_session: Session, test_workspace: Workspace):
    """Verifies that an empty workspace returns an empty result set cleanly without errors."""
    client = InMemoryChromaClient()
    provider = DeterministicFakeEmbeddingProvider()
    repo = ChromaVectorRepository(chroma_client=client, embedding_provider=provider)
    retriever = SemanticRetriever(
        embedding_provider=provider,
        vector_repository=repo,
    )

    response = retriever.retrieve(
        db=db_session,
        workspace_id=test_workspace.id,
        query="How does quantum teleportation work?",
    )

    assert response.workspace_id == test_workspace.id
    assert response.total_results == 0
    assert response.results == []
    assert "total_duration_ms" in response.duration_metrics


def test_semantic_retriever_order_preservation_and_hydration(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies vector cosine distance ordering and PostgreSQL authoritative source hydration."""
    client = InMemoryChromaClient()
    provider = DeterministicFakeEmbeddingProvider()
    repo = ChromaVectorRepository(chroma_client=client, embedding_provider=provider)
    retriever = SemanticRetriever(
        embedding_provider=provider,
        vector_repository=repo,
    )

    # 1. Create a Document in PostgreSQL
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_workspace.owner_user_id,
        original_filename="quantum_paper.pdf",
        storage_key="test/quantum_paper.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1024,
        sha256="a" * 64,
        processing_status="ready",
        processing_stage="ready",
    )
    db_session.add(doc)
    db_session.commit()

    # 2. Create chunks in PostgreSQL
    chunk1_id = uuid.uuid4()
    chunk2_id = uuid.uuid4()

    chunk1 = DocumentChunk(
        id=chunk1_id,
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        content="quantum superposition",
        content_hash="b" * 64,
        page_start=1,
        page_end=1,
        token_count=15,
        parser_version="pymupdf",
        cleaning_version="v1.0",
        chunking_version="semantic-v1",
        source_segments=[{"page_number": 1, "text": "quantum superposition"}],
    )
    chunk2 = DocumentChunk(
        id=chunk2_id,
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=1,
        content="PostgreSQL authoritative text for classical thermodynamics.",
        content_hash="c" * 64,
        page_start=2,
        page_end=2,
        token_count=16,
        parser_version="pymupdf",
        cleaning_version="v1.0",
        chunking_version="semantic-v1",
        source_segments=[{"page_number": 2, "text": "classical thermodynamics"}],
    )
    db_session.add_all([chunk1, chunk2])
    db_session.commit()

    # 3. Index vectors in Chroma
    # We query for "quantum superposition". chunk1 is an exact match so distance will be ~0.
    records = [
        VectorRecord(
            id=str(chunk1_id),
            embedding=provider.encode_query(chunk1.content),
            metadata={
                "chunk_id": str(chunk1_id),
                "document_id": str(doc.id),
                "workspace_id": str(test_workspace.id),
                "chunk_index": 0,
            },
        ),
        VectorRecord(
            id=str(chunk2_id),
            embedding=provider.encode_query(chunk2.content),
            metadata={
                "chunk_id": str(chunk2_id),
                "document_id": str(doc.id),
                "workspace_id": str(test_workspace.id),
                "chunk_index": 1,
            },
        ),
    ]
    repo.upsert_records(records)

    # 4. Perform retrieval
    response = retriever.retrieve(
        db=db_session,
        workspace_id=test_workspace.id,
        query="quantum superposition",
        top_k=5,
    )

    assert response.total_results == 2
    # Verify rank 1 is chunk1 (exact match, lowest distance)
    first_res = response.results[0]
    assert first_res.chunk_id == chunk1_id
    assert first_res.rank == 1
    assert first_res.document_filename == "quantum_paper.pdf"
    assert first_res.content == "quantum superposition"
    assert first_res.page_start == 1
    assert len(first_res.source_segments) == 1
    assert first_res.distance <= response.results[1].distance


def test_semantic_retriever_filters_soft_deleted_documents(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies that chunks from soft-deleted documents are strictly excluded from retrieval."""
    client = InMemoryChromaClient()
    provider = DeterministicFakeEmbeddingProvider()
    repo = ChromaVectorRepository(chroma_client=client, embedding_provider=provider)
    retriever = SemanticRetriever(
        embedding_provider=provider,
        vector_repository=repo,
    )

    now_utc = datetime.now(timezone.utc)
    # Create soft-deleted document
    deleted_doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_workspace.owner_user_id,
        original_filename="deleted_notes.pdf",
        storage_key="test/deleted_notes.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=512,
        sha256="d" * 64,
        processing_status="deleted",
        deleted_at=now_utc,
    )
    db_session.add(deleted_doc)
    db_session.commit()

    chunk_id = uuid.uuid4()
    chunk = DocumentChunk(
        id=chunk_id,
        workspace_id=test_workspace.id,
        document_id=deleted_doc.id,
        chunk_index=0,
        content="Secret information from a deleted document.",
        content_hash="e" * 64,
        page_start=1,
        page_end=1,
        token_count=10,
        parser_version="pymupdf",
        cleaning_version="v1.0",
        chunking_version="semantic-v1",
    )
    db_session.add(chunk)
    db_session.commit()

    # Index in Chroma
    repo.upsert_records([
        VectorRecord(
            id=str(chunk_id),
            embedding=provider.encode_query(chunk.content),
            metadata={
                "chunk_id": str(chunk_id),
                "document_id": str(deleted_doc.id),
                "workspace_id": str(test_workspace.id),
            },
        )
    ])

    # Search: must return 0 results because document is soft-deleted
    response = retriever.retrieve(
        db=db_session,
        workspace_id=test_workspace.id,
        query="Secret information",
    )
    assert response.total_results == 0
    assert response.results == []
