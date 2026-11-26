"""Exceptions for Semantic Retrieval (Phase 3 C3.3)."""


class RetrievalException(Exception):
    """Base exception for semantic search and retrieval operations."""

    def __init__(self, message: str, error_code: str = "retrieval_error") -> None:
        super().__init__(message)
        self.error_code = error_code


class InvalidQueryException(RetrievalException):
    """Raised when query text is empty, invalid, or exceeds configured bounds."""

    def __init__(self, message: str = "Query text is invalid or empty.") -> None:
        super().__init__(message, error_code="invalid_query")


class DocumentScopeException(RetrievalException):
    """Raised when requested document IDs do not belong to the authenticated workspace."""

    def __init__(self, message: str = "One or more selected documents do not belong to this workspace.") -> None:
        super().__init__(message, error_code="document_scope_invalid")
