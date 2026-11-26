"""Tests for BM25 Lexical Retrieval & Tokenization (Phase 4 C4.1)."""

import math
import uuid
import pytest
from backend.app.rag.retrieval.bm25.cache import BM25IndexCache
from backend.app.rag.retrieval.bm25.index import BM25ChunkDocument, BM25WorkspaceIndex
from backend.app.rag.retrieval.bm25.retriever import BM25Retriever
from backend.app.rag.retrieval.bm25.tokenizer import BM25Tokenizer


def test_tokenizer_technical_terms():
    tokenizer = BM25Tokenizer()
    text = (
        "Explain C++, C#, TCP/IP, Python 3.12, PostgreSQL, FastAPI, "
        "BM25, RAG, and GPT-4 in Machine Learning."
    )
    tokens = tokenizer.tokenize(text)
    assert "c++" in tokens
    assert "c#" in tokens
    assert "tcp/ip" in tokens
    assert "python" in tokens
    assert "postgresql" in tokens
    assert "fastapi" in tokens
    assert "bm25" in tokens
    assert "rag" in tokens
    assert "gpt-4" in tokens
    assert "machine" in tokens
    assert "learning" in tokens


def test_tokenizer_unicode_normalization_and_case_folding():
    tokenizer = BM25Tokenizer()
    # Unicode NFKC normalization and case folding
    text = "ＦａｓｔＡＰＩ　ａｎｄ　Ｐｙｔｈｏｎ"
    tokens = tokenizer.tokenize(text)
    assert tokens == ["fastapi", "and", "python"]


def test_tokenizer_preserves_repeated_terms_and_order():
    tokenizer = BM25Tokenizer()
    text = "TCP/IP vs TCP/IP protocols"
    tokens = tokenizer.tokenize(text)
    assert tokens == ["tcp/ip", "vs", "tcp/ip", "protocols"]
    assert tokens.count("tcp/ip") == 2


def test_tokenizer_handles_empty_and_whitespace():
    tokenizer = BM25Tokenizer()
    assert tokenizer.tokenize("") == []
    assert tokenizer.tokenize("   \n\t  ") == []
    assert tokenizer.tokenize("!@#$%^&*()") == []


def test_bm25_scoring_exact_match_and_ranking():
    ws_id = uuid.uuid4()
    doc1_id = uuid.uuid4()
    doc2_id = uuid.uuid4()
    chunk1_id = uuid.uuid4()
    chunk2_id = uuid.uuid4()

    chunks = [
        BM25ChunkDocument(
            chunk_id=chunk1_id,
            document_id=doc1_id,
            workspace_id=ws_id,
            content="TCP/IP is a suite of communication protocols used to interconnect network devices.",
        ),
        BM25ChunkDocument(
            chunk_id=chunk2_id,
            document_id=doc2_id,
            workspace_id=ws_id,
            content="Python and FastAPI are popular tools for building backend web APIs.",
        ),
    ]

    index = BM25WorkspaceIndex(workspace_id=ws_id, chunks=chunks)
    assert index.corpus_size == 2

    # Query for TCP/IP
    results = index.search(query="TCP/IP protocols", top_k=5)
    assert len(results) == 1
    assert results[0][0] == chunk1_id
    assert results[0][1] > 0.0

    # Query for Python FastAPI
    results2 = index.search(query="Python FastAPI", top_k=5)
    assert len(results2) == 1
    assert results2[0][0] == chunk2_id
    assert results2[0][1] > 0.0


def test_bm25_document_length_normalization():
    ws_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    c_short_id = uuid.uuid4()
    c_long_id = uuid.uuid4()

    # Both documents have term 'quantum' twice, but c_long has 50 filler words
    chunks = [
        BM25ChunkDocument(
            chunk_id=c_short_id,
            document_id=doc_id,
            workspace_id=ws_id,
            content="quantum physics quantum mechanics",
        ),
        BM25ChunkDocument(
            chunk_id=c_long_id,
            document_id=doc_id,
            workspace_id=ws_id,
            content="quantum quantum " + "filler word word word " * 15,
        ),
    ]

    index = BM25WorkspaceIndex(workspace_id=ws_id, chunks=chunks, b=0.75, k1=1.5)
    results = index.search(query="quantum", top_k=2)

    assert len(results) == 2
    # Shorter chunk should have higher score due to document length normalization (b > 0)
    assert results[0][0] == c_short_id
    assert results[0][1] > results[1][1]


def test_bm25_document_filtering():
    ws_id = uuid.uuid4()
    doc1_id = uuid.uuid4()
    doc2_id = uuid.uuid4()
    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()

    chunks = [
        BM25ChunkDocument(
            chunk_id=c1_id,
            document_id=doc1_id,
            workspace_id=ws_id,
            content="PostgreSQL database queries and indexing.",
        ),
        BM25ChunkDocument(
            chunk_id=c2_id,
            document_id=doc2_id,
            workspace_id=ws_id,
            content="PostgreSQL database replication and failover.",
        ),
    ]

    index = BM25WorkspaceIndex(workspace_id=ws_id, chunks=chunks)
    # Filter only doc2_id
    results = index.search(query="PostgreSQL database", document_ids=[doc2_id], top_k=5)
    assert len(results) == 1
    assert results[0][0] == c2_id


def test_bm25_empty_corpus_and_unknown_terms():
    ws_id = uuid.uuid4()
    empty_index = BM25WorkspaceIndex(workspace_id=ws_id, chunks=[])
    assert empty_index.search(query="anything", top_k=10) == []

    chunk_id = uuid.uuid4()
    single_index = BM25WorkspaceIndex(
        workspace_id=ws_id,
        chunks=[
            BM25ChunkDocument(
                chunk_id=chunk_id,
                document_id=uuid.uuid4(),
                workspace_id=ws_id,
                content="Only english words here.",
            )
        ],
    )
    # Search for term that doesn't exist
    assert single_index.search(query="supercalifragilistic", top_k=5) == []
    # Search with empty query
    assert single_index.search(query="", top_k=5) == []


def test_bm25_index_cache_lifecycle_and_invalidation():
    cache = BM25IndexCache(max_workspaces=2)
    cache.clear()

    ws1_id = uuid.uuid4()
    ws2_id = uuid.uuid4()
    ws3_id = uuid.uuid4()

    # Create dummy indexes manually in cache
    idx1 = BM25WorkspaceIndex(workspace_id=ws1_id, chunks=[])
    idx2 = BM25WorkspaceIndex(workspace_id=ws2_id, chunks=[])
    idx3 = BM25WorkspaceIndex(workspace_id=ws3_id, chunks=[])

    cache._set_index(ws1_id, idx1)
    cache._set_index(ws2_id, idx2)
    assert cache.has_index(ws1_id)
    assert cache.has_index(ws2_id)
    assert cache.cached_workspace_count == 2

    # Invalidate ws1
    assert cache.invalidate(ws1_id) is True
    assert not cache.has_index(ws1_id)
    assert cache.cached_workspace_count == 1

    # Invalidate non-existent
    assert cache.invalidate(uuid.uuid4()) is False

    # Eviction test (max 2)
    cache._set_index(ws1_id, idx1)
    cache._set_index(ws2_id, idx2)
    # Adding ws3 should evict ws1 (oldest accessed)
    cache._set_index(ws3_id, idx3)
    assert cache.cached_workspace_count == 2
    assert not cache.has_index(ws1_id)
    assert cache.has_index(ws2_id)
    assert cache.has_index(ws3_id)


def test_bm25_retriever_service_end_to_end(db_session):
    from datetime import datetime, timezone
    from backend.app.models.document import Document
    from backend.app.models.document_chunk import DocumentChunk
    from backend.app.models.user import User
    from backend.app.models.workspace import Workspace

    # Setup user, workspace, documents, and chunks
    user = User(
        id=uuid.uuid4(),
        email=f"bm25_test_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hash",
        display_name="BM25 Tester",
        status="active",
    )
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name="BM25 Retrieval Workspace",
    )
    doc1 = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="distributed_systems.pdf",
        storage_key=f"test/{uuid.uuid4().hex}_ds.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1024,
        sha256="dummy_hash_1",
        processing_status="ready",
        processing_stage="ready",
    )
    doc2 = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="database_internals.pdf",
        storage_key=f"test/{uuid.uuid4().hex}_db.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=2048,
        sha256="dummy_hash_2",
        processing_status="ready",
        processing_stage="ready",
    )
    c1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc1.id,
        workspace_id=ws.id,
        chunk_index=0,
        content="Raft consensus and Paxos algorithms in distributed networks.",
        token_count=12,
        token_count_method="estimate_v1",
        parser_version="pdfplumber_v1",
        cleaning_version="v1",
        chunking_version="v1",
        content_hash="chash1",
        source_segments=[],
        page_start=1,
        page_end=1,
    )
    c2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc2.id,
        workspace_id=ws.id,
        chunk_index=0,
        content="B-tree index and write-ahead logging (WAL) in PostgreSQL storage engine.",
        token_count=14,
        token_count_method="estimate_v1",
        parser_version="pdfplumber_v1",
        cleaning_version="v1",
        chunking_version="v1",
        content_hash="chash2",
        source_segments=[],
        page_start=1,
        page_end=2,
    )
    db_session.add_all([user, ws, doc1, doc2, c1, c2])
    db_session.commit()

    retriever = BM25Retriever()
    # Invalidate to ensure fresh index build
    retriever.cache.invalidate(ws.id)

    # Search for Raft consensus
    resp = retriever.retrieve(db=db_session, workspace_id=ws.id, query="Raft consensus")
    assert resp.total_results == 1
    assert resp.results[0].chunk_id == c1.id
    assert resp.results[0].document_filename == "distributed_systems.pdf"
    assert resp.results[0].page_start == 1
    assert resp.results[0].rank == 1
    assert resp.results[0].bm25_score > 0

    # Search for WAL PostgreSQL
    resp2 = retriever.retrieve(db=db_session, workspace_id=ws.id, query="WAL PostgreSQL")
    assert resp2.total_results == 1
    assert resp2.results[0].chunk_id == c2.id
    assert resp2.results[0].document_filename == "database_internals.pdf"
    assert resp2.results[0].page_end == 2



