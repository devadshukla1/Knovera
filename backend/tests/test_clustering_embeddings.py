"""Unit tests for ChunkEmbeddingService (Phase 6 C6.1)."""

from datetime import datetime, timezone
import uuid
import numpy as np
import pytest
from unittest.mock import MagicMock

from backend.app.ml.topic_clustering.embedding_service import ChunkEmbeddingService
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.rag.embeddings.fake_provider import DeterministicFakeEmbeddingProvider


def test_normalize_and_validate_standard_vectors():
    service = ChunkEmbeddingService(embedding_provider=DeterministicFakeEmbeddingProvider(dimension=384))
    raw = np.random.RandomState(42).randn(10, 384).astype(np.float32)
    normalized = service.normalize_and_validate(raw, expected_dim=384)

    assert normalized.shape == (10, 384)
    assert normalized.dtype == np.float32
    norms = np.linalg.norm(normalized, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-4)


def test_normalize_and_validate_dimension_mismatch():
    service = ChunkEmbeddingService(embedding_provider=DeterministicFakeEmbeddingProvider(dimension=384))
    raw = np.random.RandomState(42).randn(5, 128).astype(np.float32)
    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        service.normalize_and_validate(raw, expected_dim=384)


def test_normalize_and_validate_nan_inf_detection():
    service = ChunkEmbeddingService(embedding_provider=DeterministicFakeEmbeddingProvider(dimension=384))
    raw = np.random.RandomState(42).randn(5, 384).astype(np.float32)
    raw[2, 50] = np.nan
    with pytest.raises(ValueError, match="NaN or Infinite"):
        service.normalize_and_validate(raw, expected_dim=384)

    raw[2, 50] = np.inf
    with pytest.raises(ValueError, match="NaN or Infinite"):
        service.normalize_and_validate(raw, expected_dim=384)


def test_normalize_and_validate_zero_norm_guard():
    service = ChunkEmbeddingService(embedding_provider=DeterministicFakeEmbeddingProvider(dimension=384))
    raw = np.random.RandomState(42).randn(3, 384).astype(np.float32)
    raw[1, :] = 0.0  # zero norm vector

    normalized = service.normalize_and_validate(raw, expected_dim=384)
    norms = np.linalg.norm(normalized, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-4)
    assert not np.any(np.isnan(normalized))


def test_extract_workspace_chunks_excludes_soft_deleted_documents(db_session):
    ws_id = uuid.uuid4()
    other_ws_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Create documents
    active_doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        uploaded_by_user_id=user_id,
        original_filename="active.pdf",
        storage_key=f"active_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1000,
        sha256="a" * 64,
        processing_status="completed",
    )
    deleted_doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        uploaded_by_user_id=user_id,
        original_filename="deleted.pdf",
        storage_key=f"deleted_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1000,
        sha256="b" * 64,
        processing_status="completed",
        deleted_at=datetime.now(timezone.utc),
    )
    other_ws_doc = Document(
        id=uuid.uuid4(),
        workspace_id=other_ws_id,
        uploaded_by_user_id=user_id,
        original_filename="other.pdf",
        storage_key=f"other_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1000,
        sha256="c" * 64,
        processing_status="completed",
    )
    db_session.add_all([active_doc, deleted_doc, other_ws_doc])
    db_session.flush()

    # Create chunks
    c1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        document_id=active_doc.id,
        chunk_index=0,
        content="Active chunk text 1",
        content_hash="h1" * 32,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    c2 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        document_id=active_doc.id,
        chunk_index=1,
        content="Active chunk text 2",
        content_hash="h2" * 32,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    c_deleted = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        document_id=deleted_doc.id,
        chunk_index=0,
        content="Deleted doc chunk text",
        content_hash="hd" * 32,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    c_other = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=other_ws_id,
        document_id=other_ws_doc.id,
        chunk_index=0,
        content="Other workspace chunk text",
        content_hash="ho" * 32,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    db_session.add_all([c1, c2, c_deleted, c_other])
    db_session.commit()

    service = ChunkEmbeddingService()
    extracted = service.extract_workspace_chunks(db_session, ws_id)

    assert len(extracted) == 2
    extracted_ids = {c.id for c in extracted}
    assert c1.id in extracted_ids
    assert c2.id in extracted_ids
    assert c_deleted.id not in extracted_ids
    assert c_other.id not in extracted_ids


def test_generate_chunk_embeddings_with_chroma_reuse():
    provider = DeterministicFakeEmbeddingProvider(dimension=384)
    provider.encode_documents = MagicMock(wraps=provider.encode_documents)

    mock_chroma_client = MagicMock()
    mock_collection = MagicMock()

    ws_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk1_id = uuid.uuid4()
    chunk2_id = uuid.uuid4()

    c1 = DocumentChunk(
        id=chunk1_id,
        workspace_id=ws_id,
        document_id=doc_id,
        chunk_index=0,
        content="First chunk text",
        content_hash="a" * 64,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    c2 = DocumentChunk(
        id=chunk2_id,
        workspace_id=ws_id,
        document_id=doc_id,
        chunk_index=1,
        content="Second chunk text",
        content_hash="b" * 64,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )

    # Simulate Chroma having embedding for chunk1 but not chunk2
    cached_vec = [0.1] * 384
    mock_chroma_client.get_collection.return_value = mock_collection
    mock_collection.get.return_value = {
        "ids": [str(chunk1_id)],
        "embeddings": [cached_vec],
    }

    service = ChunkEmbeddingService(
        embedding_provider=provider,
        chroma_client=mock_chroma_client,
    )

    records, embeddings = service.generate_chunk_embeddings(
        chunks=[c1, c2],
        reuse_chroma=True,
        force_regenerate=False,
    )

    assert len(records) == 2
    assert embeddings.shape == (2, 384)
    # encode_documents was called only for chunk2 ("Second chunk text")
    provider.encode_documents.assert_called_once_with(["Second chunk text"])

    # Both embeddings are unit normalized
    assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-4)


def test_generate_chunk_embeddings_force_regenerate():
    provider = DeterministicFakeEmbeddingProvider(dimension=384)
    provider.encode_documents = MagicMock(wraps=provider.encode_documents)
    mock_chroma_client = MagicMock()

    ws_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    c1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        document_id=doc_id,
        chunk_index=0,
        content="Force regen chunk",
        content_hash="c" * 64,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )

    service = ChunkEmbeddingService(
        embedding_provider=provider,
        chroma_client=mock_chroma_client,
    )

    records, embeddings = service.generate_chunk_embeddings(
        chunks=[c1],
        reuse_chroma=True,
        force_regenerate=True,
    )

    # Chroma get_collection should not have been called
    mock_chroma_client.get_collection.assert_not_called()
    provider.encode_documents.assert_called_once_with(["Force regen chunk"])
    assert len(records) == 1
    assert embeddings.shape == (1, 384)
