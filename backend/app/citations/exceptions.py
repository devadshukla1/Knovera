"""Exceptions for Knovera citation validation and mapping (Phase 3 C3.8)."""


class CitationException(Exception):
    """Base exception for citation errors."""


class UnknownSourceIdError(CitationException):
    """Raised when an LLM claims a source ID not present in the active context package."""


class CitationWorkspaceMismatchError(CitationException):
    """Raised when a cited chunk does not belong to the authorized workspace."""


class CitationDocumentDeletedError(CitationException):
    """Raised when a cited chunk belongs to a document that has been soft-deleted."""


class CitationProvenanceError(CitationException):
    """Raised when chunk provenance metadata is missing or corrupted."""


class CitationNotFoundError(CitationException):
    """Raised when a requested citation record does not exist in the database."""


class CitationAccessDeniedError(CitationException):
    """Raised when an unauthenticated or unauthorized user attempts to view a citation."""
