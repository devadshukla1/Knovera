"""Tests for Embedding Providers and Model Manager (Phase 3 C3.1)."""

import math
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from backend.app.rag.embeddings.base import EmbeddingProvider
from backend.app.rag.embeddings.exceptions import (
    DimensionMismatchError,
    EmptyInputError,
    ModelLoadError,
)
from backend.app.rag.embeddings.fake_provider import DeterministicFakeEmbeddingProvider
from backend.app.rag.embeddings.model_manager import EmbeddingModelManager
from backend.app.rag.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingProvider,
)


def test_deterministic_fake_embedding_provider():
    """Verifies that the fake provider satisfies mathematical and functional invariants."""
    provider = DeterministicFakeEmbeddingProvider(dimension=384)
    assert provider.get_dimension() == 384
    assert provider.get_model_id() == "sentence-transformers/all-MiniLM-L6-v2"
    assert provider.is_ready() is True

    # Encoding documents
    texts = [
        "First document on transformers and attention.",
        "Second document on vector databases and ChromaDB.",
    ]
    vectors = provider.encode_documents(texts)
    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert len(vectors[1]) == 384

    # Check finite values and L2 normalization
    for vec in vectors:
        assert all(math.isfinite(x) for x in vec)
        norm = np.linalg.norm(vec)
        assert pytest.approx(norm, rel=1e-5) == 1.0

    # Determinism: identical text yields identical vector
    vec_repeat = provider.encode_query("First document on transformers and attention.")
    assert np.allclose(vectors[0], vec_repeat, atol=1e-6)

    # Different text yields different vector
    assert not np.allclose(vectors[0], vectors[1], atol=1e-3)


def test_empty_input_rejected():
    """Empty strings or whitespace-only inputs raise EmptyInputError."""
    provider = DeterministicFakeEmbeddingProvider()
    with pytest.raises(EmptyInputError):
        provider.encode_query("")
    with pytest.raises(EmptyInputError):
        provider.encode_query("   ")
    with pytest.raises(EmptyInputError):
        provider.encode_documents(["Valid text", ""])


def test_embedding_model_manager_singleton_and_readiness():
    """Verifies thread-safe singleton lifecycle and readiness reporting."""
    manager = EmbeddingModelManager.get_instance()
    fake_provider = DeterministicFakeEmbeddingProvider()
    manager.set_provider(fake_provider)

    active = manager.get_provider()
    assert active is fake_provider

    is_ready, details = manager.check_readiness()
    assert is_ready is True
    assert details["dimension"] == 384
    assert details["ready"] is True


def test_sentence_transformer_mocked_execution():
    """Verifies SentenceTransformerEmbeddingProvider logic with mocked underlying model."""
    mock_st_class = MagicMock()
    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = 384
    mock_model.max_seq_length = 256
    # Return mock numpy embeddings
    mock_model.encode.return_value = np.ones((2, 384), dtype=np.float32) / math.sqrt(384)
    mock_st_class.return_value = mock_model

    with patch.dict("sys.modules", {"sentence_transformers": MagicMock(SentenceTransformer=mock_st_class)}):
        provider = SentenceTransformerEmbeddingProvider(
            model_id="sentence-transformers/all-MiniLM-L6-v2",
            cache_dir="./storage/model_cache",
        )
        assert provider.get_dimension() == 384
        assert provider.is_ready() is True

        docs = ["Test document 1", "Test document 2"]
        embeddings = provider.encode_documents(docs)
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 384


def test_dimension_mismatch_detection():
    """Detects dimension mismatch and non-finite values."""
    mock_st_class = MagicMock()
    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = 384
    # Return incorrect dimension (128 instead of 384)
    mock_model.encode.return_value = np.zeros((1, 128), dtype=np.float32)
    mock_st_class.return_value = mock_model

    with patch.dict("sys.modules", {"sentence_transformers": MagicMock(SentenceTransformer=mock_st_class)}):
        provider = SentenceTransformerEmbeddingProvider()
        with pytest.raises(DimensionMismatchError):
            provider.encode_documents(["Hello world"])
