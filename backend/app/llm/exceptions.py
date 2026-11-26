"""Provider-neutral LLM exceptions and taxonomy (Phase 3 C3.4)."""

from typing import Optional


class LLMException(Exception):
    """Base exception for all LLM and provider-related failures."""

    def __init__(self, message: str, provider: Optional[str] = None, error_code: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider or "unknown"
        self.error_code = error_code or "llm_error"

    def __str__(self) -> str:
        return f"[{self.provider.upper()}:{self.error_code}] {self.message}"


class ProviderConfigurationError(LLMException):
    """Raised when provider configuration or credentials are missing, invalid, or malformed."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(message, provider=provider, error_code="configuration_error")


class ProviderAuthenticationError(LLMException):
    """Raised when provider authentication fails (e.g. HTTP 401, invalid API key). Non-retryable."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(message, provider=provider, error_code="authentication_error")


class ProviderRateLimitError(LLMException):
    """Raised when provider rate limits / quota thresholds are exceeded (e.g. HTTP 429). Retryable."""

    def __init__(self, message: str, provider: Optional[str] = None, retry_after: Optional[float] = None) -> None:
        super().__init__(message, provider=provider, error_code="rate_limit_exceeded")
        self.retry_after = retry_after


class ProviderTimeoutError(LLMException):
    """Raised when an HTTP or generation request to the provider times out. Retryable."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(message, provider=provider, error_code="timeout")


class ProviderUnavailableError(LLMException):
    """Raised when the provider service is offline, unreachable, or returning 5xx. Retryable."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(message, provider=provider, error_code="service_unavailable")


class ProviderContextLengthError(LLMException):
    """Raised when input tokens exceed the verified context window of the target model. Non-retryable."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(message, provider=provider, error_code="context_length_exceeded")


class ProviderInvalidRequestError(LLMException):
    """Raised when the request payload is rejected by the provider (e.g. HTTP 400/422). Non-retryable."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(message, provider=provider, error_code="invalid_request")


class ProviderGenerationError(LLMException):
    """Raised when generation returns empty, malformed, or unparseable output."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(message, provider=provider, error_code="generation_failed")


def is_retryable_llm_error(exc: Exception) -> bool:
    """Evaluates whether an LLM exception qualifies for bounded retry with backoff."""
    return isinstance(exc, (ProviderRateLimitError, ProviderTimeoutError, ProviderUnavailableError))
