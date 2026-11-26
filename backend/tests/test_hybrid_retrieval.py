"""Tests for Hybrid Retrieval (Dense + BM25 + RRF) (Phase 4 C4.2)."""

import uuid
import pytest
from unittest.mock import MagicMock

from backend.app.rag.retrieval.hybrid_retriever import HybridRetriever
from backend.app.rag.retrieval.schemas import (
    BM25SearchResult,
    HybridSearchRequest,
    HybridSearchResult,
    SemanticSearchResult,
)


def test_hybrid_retrieval_combines_dense_and_bm25(db_session):
    from backend.app.models.document import Document
    from backend.app.models.document_chunk import DocumentChunk
    from backend.app.models.user import User
    from backend.app.models.workspace import Workspace

    # Setup database models
    user = User(
        id=uuid.uuid4(),
        email=f"hybrid_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hash",
        display_name="Hybrid Tester",
        status="active",
    )
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name="Hybrid Workspace",
    )
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="ai_systems.pdf",
        storage_key=f"test/{uuid.uuid4().hex}_ai.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1024,
        sha256=f"hash_{uuid.uuid4().hex[:8]}",
        processing_status="ready",
        processing_stage="ready",
    )
    # Chunk A: Semantic match for "intelligent agents"
    chunk_a = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        workspace_id=ws.id,
        chunk_index=0,
        content="Autonomous reinforcement learning entities acting in simulated environments.",
        token_count=10,
        token_count_method="estimate_v1",
        parser_version="pdfplumber_v1",
        cleaning_version="v1",
        chunking_version="v1",
        content_hash="h1",
        source_segments=[],
        page_start=1,
        page_end=1,
    )
    # Chunk B: Exact lexical match for "FastAPI" and "PostgreSQL"
    chunk_b = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        workspace_id=ws.id,
        chunk_index=1,
        content="Production web services using FastAPI framework connected to PostgreSQL databases.",
        token_count=11,
        token_count_method="estimate_v1",
        parser_version="pdfplumber_v1",
        cleaning_version="v1",
        chunking_version="v1",
        content_hash="h2",
        source_segments=[],
        page_start=2,
        page_end=2,
    )
    db_session.add_all([user, ws, doc, chunk_a, chunk_b])
    db_session.commit()

    # Mock Dense Retriever (returns chunk_a rank 1, chunk_b rank 2)
    mock_dense = MagicMock()
    mock_dense.vector_repo.query_nearest.return_value = [
        (str(chunk_a.id), 0.15),
        (str(chunk_b.id), 0.45),
    ]

    retriever = HybridRetriever(semantic_retriever=mock_dense)
    # Clear BM25 cache
    retriever.bm25_retriever.cache.invalidate(ws.id)

    # Search for "FastAPI PostgreSQL"
    # BM25 will rank chunk_b #1, while dense ranks chunk_a #1
    response = retriever.retrieve(
        db=db_session,
        workspace_id=ws.id,
        query="FastAPI PostgreSQL",
        top_k=5,
        mode="hybrid",
    )

    assert response.total_results == 2
    # Both chunks must be present in fused response
    result_ids = [r.chunk_id for r in response.results]
    assert chunk_a.id in result_ids
    assert chunk_b.id in result_ids

    # chunk_b has rank 1 in BM25 (1/61) and rank 2 in dense (1/62) -> higher RRF score than chunk_a
    assert response.results[0].chunk_id == chunk_b.id
    assert response.results[0].rank == 1
    assert response.results[0].bm25_rank == 1
    assert response.results[0].dense_rank == 2
    assert "semantic" in response.results[0].retrieval_sources
    assert "bm25" in response.results[0].retrieval_sources


def test_hybrid_retrieval_fallback_when_dense_empty(db_session):
    from backend.app.models.document import Document
    from backend.app.models.document_chunk import DocumentChunk
    from backend.app.models.user import User
    from backend.app.models.workspace import Workspace

    user = User(
        id=uuid.uuid4(),
        email=f"fallback_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hash",
        display_name="Fallback Tester",
        status="active",
    )
    ws = Workspace(id=uuid.uuid4(), owner_user_id=user.id, name="WS")
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="doc.pdf",
        storage_key=f"test/{uuid.uuid4().hex}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=512,
        sha256=f"hash_{uuid.uuid4().hex[:8]}",
        processing_status="ready",
        processing_stage="ready",
    )
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        workspace_id=ws.id,
        chunk_index=0,
        content="BM25 only match for specific unique term.",
        token_count=7,
        token_count_method="estimate_v1",
        parser_version="pdfplumber_v1",
        cleaning_version="v1",
        chunking_version="v1",
        content_hash="h3",
        source_segments=[],
        page_start=1,
        page_end=1,
    )
    db_session.add_all([user, ws, doc, chunk])
    db_session.commit()

    # Dense returns empty
    mock_dense = MagicMock()
    mock_dense.vector_repo.query_nearest.return_value = []

    retriever = HybridRetriever(semantic_retriever=mock_dense)
    retriever.bm25_retriever.cache.invalidate(ws.id)

    response = retriever.retrieve(
        db=db_session,
        workspace_id=ws.id,
        query="unique term",
        mode="hybrid",
    )
    assert response.total_results == 1
    assert response.results[0].chunk_id == chunk.id
    assert response.results[0].bm25_rank == 1
    assert response.results[0].dense_rank is None
    assert response.results[0].retrieval_sources == ["bm25"]


def test_hybrid_retrieval_both_empty(db_session):
    ws_id = uuid.uuid4()
    mock_dense = MagicMock()
    mock_dense.vector_repo.query_nearest.return_value = []

    retriever = HybridRetriever(semantic_retriever=mock_dense)
    retriever.bm25_retriever.cache.invalidate(ws_id)

    response = retriever.retrieve(
        db=db_session,
        workspace_id=ws_id,
        query="nothing here",
        mode="hybrid",
    )
    assert response.total_results == 0
    assert response.results == []
