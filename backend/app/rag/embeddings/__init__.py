"""Knovera RAG Embedding Module (Phase 3 C3.1)."""

from backend.app.rag.embeddings.base import EmbeddingProvider
from backend.app.rag.embeddings.exceptions import (
    DimensionMismatchError,
    EmbeddingException,
    EmptyInputError,
    InvalidInputError,
    ModelLoadError,
)
from backend.app.rag.embeddings.fake_provider import DeterministicFakeEmbeddingProvider
from backend.app.rag.embeddings.model_manager import EmbeddingModelManager
from backend.app.rag.embeddings.schemas import (
    EmbeddingBatchResult,
    EmbeddingMetadata,
)
from backend.app.rag.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingProvider,
)

__all__ = [
    "EmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    "DeterministicFakeEmbeddingProvider",
    "EmbeddingModelManager",
    "EmbeddingMetadata",
    "EmbeddingBatchResult",
    "EmbeddingException",
    "ModelLoadError",
    "DimensionMismatchError",
    "EmptyInputError",
    "InvalidInputError",
]
