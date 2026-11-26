"""Exceptions for Knovera Embedding Services (Phase 3 C3.1)."""


class EmbeddingException(Exception):
    """Base exception for all embedding-related errors."""

    def __init__(self, message: str, error_code: str = "embedding_error") -> None:
        super().__init__(message)
        self.error_code = error_code


class ModelLoadError(EmbeddingException):
    """Raised when the embedding model cannot be loaded from disk or remote cache."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="model_load_failed")


class DimensionMismatchError(EmbeddingException):
    """Raised when generated vector dimensions do not match the expected collection dimension."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="dimension_mismatch")


class EmptyInputError(EmbeddingException):
    """Raised when an empty string or empty text batch is submitted for embedding."""

    def __init__(self, message: str = "Input text cannot be empty or solely whitespace.") -> None:
        super().__init__(message, error_code="empty_embedding_input")


class InvalidInputError(EmbeddingException):
    """Raised when embedding input fails validation constraints."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="invalid_embedding_input")
