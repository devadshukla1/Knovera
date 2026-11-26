"""Exceptions for Knovera Vector Store and ChromaDB Integration (Phase 3 C3.2)."""


class VectorStoreException(Exception):
    """Base exception for ChromaDB vector store operations."""

    def __init__(self, message: str, error_code: str = "vector_store_error") -> None:
        super().__init__(message)
        self.error_code = error_code


class ChromaUnavailableError(VectorStoreException):
    """Raised when ChromaDB server is offline or unreachable."""

    def __init__(self, message: str = "Vector database service is offline or unreachable.") -> None:
        super().__init__(message, error_code="chroma_unavailable")


class CollectionNotFoundError(VectorStoreException):
    """Raised when the specified vector collection cannot be found."""

    def __init__(self, collection_name: str) -> None:
        super().__init__(f"Chroma collection '{collection_name}' does not exist.", error_code="collection_not_found")
        self.collection_name = collection_name


class CollectionDimensionMismatchError(VectorStoreException):
    """Raised when collection dimension does not match active embedding model dimension."""

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(
            f"Collection dimension mismatch: expected {expected}, actual {actual}",
            error_code="collection_dimension_mismatch",
        )
        self.expected = expected
        self.actual = actual


class UpsertFailedError(VectorStoreException):
    """Raised when batch upsert into ChromaDB fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="vector_upsert_failed")
