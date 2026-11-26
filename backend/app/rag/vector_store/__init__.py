"""Knovera Vector Store and ChromaDB integration package (Phase 3 C3.2)."""

from backend.app.rag.vector_store.collection_manager import ChromaCollectionManager
from backend.app.rag.vector_store.chroma_repository import ChromaVectorRepository
from backend.app.rag.vector_store.exceptions import (
    ChromaUnavailableError,
    CollectionDimensionMismatchError,
    CollectionNotFoundError,
    UpsertFailedError,
    VectorStoreException,
)
from backend.app.rag.vector_store.schemas import (
    CollectionInfo,
    ReconciliationReport,
    VectorRecord,
)

__all__ = [
    "ChromaCollectionManager",
    "ChromaVectorRepository",
    "VectorRecord",
    "CollectionInfo",
    "ReconciliationReport",
    "VectorStoreException",
    "ChromaUnavailableError",
    "CollectionNotFoundError",
    "CollectionDimensionMismatchError",
    "UpsertFailedError",
]
