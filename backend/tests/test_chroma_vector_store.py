"""Tests for ChromaDB Collection Manager and Vector Repository (Phase 3 C3.2)."""

import uuid
import pytest

from backend.app.rag.embeddings.fake_provider import DeterministicFakeEmbeddingProvider
from backend.app.rag.vector_store.collection_manager import (
    ChromaCollectionManager,
    sanitize_collection_name,
)
from backend.app.rag.vector_store.chroma_repository import ChromaVectorRepository
from backend.app.rag.vector_store.fake_client import InMemoryChromaClient
from backend.app.rag.vector_store.schemas import VectorRecord


def test_sanitize_collection_name():
    """Verifies collection name sanitization conforms to Chroma naming rules."""
    assert sanitize_collection_name("valid_name-123") == "valid_name-123"
    assert sanitize_collection_name("sentence-transformers/all-MiniLM-L6-v2") == "sentence-transformers_all-MiniLM-L6-v2"
    assert sanitize_collection_name("a!@#$%^&*()b") == "a_b"
    assert len(sanitize_collection_name("x" * 100)) <= 63


def test_collection_manager_deterministic_naming():
    """Verifies deterministic naming based on model ID, revision, and dimension."""
    client = InMemoryChromaClient()
    manager = ChromaCollectionManager(client)

    name1 = manager.generate_collection_name(
        model_id="sentence-transformers/all-MiniLM-L6-v2",
        model_revision="main",
        dimension=384,
    )
    name2 = manager.generate_collection_name(
        model_id="sentence-transformers/all-MiniLM-L6-v2",
        model_revision="main",
        dimension=384,
    )
    assert name1 == name2
    assert "384" in name1
    assert "all-MiniLM-L6-v2" in name1 or "all_MiniLM_L6_v2" in name1

    # Different dimension yields different collection name
    name_dim = manager.generate_collection_name(
        model_id="sentence-transformers/all-MiniLM-L6-v2",
        model_revision="main",
        dimension=768,
    )
    assert name1 != name_dim


def test_collection_creation_and_metadata():
    """Verifies collection creation initializes cosine metric and metadata tags."""
    client = InMemoryChromaClient()
    manager = ChromaCollectionManager(client)

    col = manager.get_or_create_collection(
        model_id="test-model",
        model_revision="v1",
        dimension=384,
    )
    assert col is not None
    assert col.metadata.get("hnsw:space") == "cosine"
    assert col.metadata.get("embedding_dimension") == 384
    assert col.metadata.get("embedding_model") == "test-model"


def test_vector_repository_batch_upsert_and_idempotency():
    """Verifies batch upserts, count, and idempotent re-upserting."""
    client = InMemoryChromaClient()
    provider = DeterministicFakeEmbeddingProvider(dimension=384)
    repo = ChromaVectorRepository(chroma_client=client, embedding_provider=provider)

    ws_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_1 = uuid.uuid4()
    chunk_2 = uuid.uuid4()

    records = [
        VectorRecord(
            id=str(chunk_1),
            embedding=provider.encode_query("First chunk on quantum superposition."),
            metadata={
                "chunk_id": str(chunk_1),
                "document_id": str(doc_id),
                "workspace_id": str(ws_id),
                "chunk_index": 0,
            },
        ),
        VectorRecord(
            id=str(chunk_2),
            embedding=provider.encode_query("Second chunk on quantum entanglement."),
            metadata={
                "chunk_id": str(chunk_2),
                "document_id": str(doc_id),
                "workspace_id": str(ws_id),
                "chunk_index": 1,
            },
        ),
    ]

    upserted = repo.upsert_records(records)
    assert upserted == 2
    col = repo.get_active_collection()
    assert col.count() == 2

    # Idempotent re-upsert: count must remain 2
    upserted_again = repo.upsert_records(records)
    assert upserted_again == 2
    assert col.count() == 2


def test_vector_repository_workspace_filtering_and_isolation():
    """Verifies query_nearest strictly isolates workspace chunks."""
    client = InMemoryChromaClient()
    provider = DeterministicFakeEmbeddingProvider(dimension=384)
    repo = ChromaVectorRepository(chroma_client=client, embedding_provider=provider)

    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()
    doc_a = uuid.uuid4()
    doc_b = uuid.uuid4()

    # Index text in workspace A
    emb_a = provider.encode_query("Knowledge discovery with graphs.")
    repo.upsert_records([
        VectorRecord(
            id="chunk_a",
            embedding=emb_a,
            metadata={"workspace_id": str(ws_a), "document_id": str(doc_a)},
        )
    ])

    # Index identical text in workspace B
    emb_b = provider.encode_query("Knowledge discovery with graphs.")
    repo.upsert_records([
        VectorRecord(
            id="chunk_b",
            embedding=emb_b,
            metadata={"workspace_id": str(ws_b), "document_id": str(doc_b)},
        )
    ])

    # Search in workspace A: must only return chunk_a
    results_a = repo.query_nearest(query_vector=emb_a, workspace_id=ws_a, top_k=10)
    matched_ids_a = [r[0] for r in results_a]
    assert "chunk_a" in matched_ids_a
    assert "chunk_b" not in matched_ids_a

    # Search in workspace B: must only return chunk_b
    results_b = repo.query_nearest(query_vector=emb_b, workspace_id=ws_b, top_k=10)
    matched_ids_b = [r[0] for r in results_b]
    assert "chunk_b" in matched_ids_b
    assert "chunk_a" not in matched_ids_b


def test_vector_repository_document_scoped_filtering():
    """Verifies query_nearest with optional document_ids filter."""
    client = InMemoryChromaClient()
    provider = DeterministicFakeEmbeddingProvider(dimension=384)
    repo = ChromaVectorRepository(chroma_client=client, embedding_provider=provider)

    ws_id = uuid.uuid4()
    doc_1 = uuid.uuid4()
    doc_2 = uuid.uuid4()

    repo.upsert_records([
        VectorRecord(
            id="chunk_doc1",
            embedding=provider.encode_query("Neural attention mechanisms."),
            metadata={"workspace_id": str(ws_id), "document_id": str(doc_1)},
        ),
        VectorRecord(
            id="chunk_doc2",
            embedding=provider.encode_query("Neural attention mechanisms."),
            metadata={"workspace_id": str(ws_id), "document_id": str(doc_2)},
        ),
    ])

    # Filter only to doc_1
    query_vec = provider.encode_query("attention")
    res = repo.query_nearest(query_vector=query_vec, workspace_id=ws_id, document_ids=[doc_1])
    matched_ids = [r[0] for r in res]
    assert "chunk_doc1" in matched_ids
    assert "chunk_doc2" not in matched_ids


def test_vector_repository_deletion_lifecycle():
    """Verifies deletion by document and deletion by workspace."""
    client = InMemoryChromaClient()
    provider = DeterministicFakeEmbeddingProvider(dimension=384)
    repo = ChromaVectorRepository(chroma_client=client, embedding_provider=provider)

    ws_id = uuid.uuid4()
    doc_1 = uuid.uuid4()
    doc_2 = uuid.uuid4()

    repo.upsert_records([
        VectorRecord(
            id="chunk_1",
            embedding=provider.encode_query("Content 1"),
            metadata={"workspace_id": str(ws_id), "document_id": str(doc_1)},
        ),
        VectorRecord(
            id="chunk_2",
            embedding=provider.encode_query("Content 2"),
            metadata={"workspace_id": str(ws_id), "document_id": str(doc_2)},
        ),
    ])

    assert repo.get_active_collection().count() == 2

    # Delete doc_1
    repo.delete_by_document(workspace_id=ws_id, document_id=doc_1)
    assert repo.get_active_collection().count() == 1

    # doc_2 remains
    res = repo.query_nearest(query_vector=provider.encode_query("Content"), workspace_id=ws_id)
    assert [r[0] for r in res] == ["chunk_2"]

    # Delete whole workspace
    repo.delete_by_workspace(workspace_id=ws_id)
    assert repo.get_active_collection().count() == 0
