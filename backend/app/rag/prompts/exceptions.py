"""Exceptions for Prompt Engineering (Phase 3 C3.6)."""

class PromptException(Exception):
    """Base exception for prompt template and rendering failures."""
    pass


class PromptRenderingError(PromptException):
    """Raised when variable interpolation or template rendering fails."""
    pass


class StructuredOutputParseError(PromptException):
    """Raised when model completion fails JSON parsing or schema validation."""
    pass
