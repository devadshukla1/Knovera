"""Exceptions for Context Construction (Phase 3 C3.5)."""

class ContextBuilderException(Exception):
    """Base exception for context construction errors."""
    pass


class ContextScopeError(ContextBuilderException):
    """Raised when chunks or documents violate workspace ownership boundaries."""
    pass


class ContextBudgetExceededError(ContextBuilderException):
    """Raised when fixed prompt requirements exceed available model context."""
    pass
