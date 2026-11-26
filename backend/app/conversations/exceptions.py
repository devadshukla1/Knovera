"""Exceptions for Knovera conversation management and message submission (Phase 3 C3.9)."""


class ConversationException(Exception):
    """Base exception for conversation errors."""


class ConversationNotFoundError(ConversationException):
    """Raised when a requested conversation is not found."""


class ConversationAccessDeniedError(ConversationException):
    """Raised when an authenticated user attempts to access another user's conversation."""


class DuplicateMessageRequestError(ConversationException):
    """Raised when a duplicate client request ID is submitted."""


class GenerationAlreadyPendingError(ConversationException):
    """Raised when a previous message in the conversation is still generating."""


class InvalidMessageError(ConversationException):
    """Raised when a message query fails validation (empty, too long, or invalid scope)."""
