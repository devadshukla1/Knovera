"""Structured logging configuration with credential sanitization.

Ensures that passwords, connection strings, authorization tokens, and API keys
are automatically sanitized before being emitted to standard output.
"""

import logging
import re
import sys
from typing import Optional


class SanitizedFormatter(logging.Formatter):
    """Logging formatter that redacts sensitive credentials and tokens from messages."""

    # Redact URL credentials: e.g. postgresql://user:password@host
    URL_CREDENTIALS_PATTERN = re.compile(r"://(?P<user>[^:]+):(?P<password>[^@]+)@")
    # Redact Bearer tokens: e.g. Bearer eyJhbGci...
    BEARER_TOKEN_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE)
    # Redact key-value secrets in logs (e.g. password=..., secret_key=...)
    KEY_VALUE_SECRET_PATTERN = re.compile(
        r"(?i)\b(password|secret|token|api_key|auth_secret_key)\s*[:=]\s*['\"]?([^'\"\s,]+)['\"]?"
    )

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        # Redact URL passwords
        formatted = self.URL_CREDENTIALS_PATTERN.sub(r"://\g<user>:***@", formatted)
        # Redact Bearer tokens
        formatted = self.BEARER_TOKEN_PATTERN.sub(r"\g<1>***", formatted)
        # Redact key-value secrets
        formatted = self.KEY_VALUE_SECRET_PATTERN.sub(r"\1=***", formatted)
        return formatted


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configures root logger with sanitized credential formatting.

    Args:
        log_level: Desired log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        The configured root logger.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Check if a sanitized handler already exists
    has_sanitized_handler = any(
        isinstance(getattr(handler, "formatter", None), SanitizedFormatter)
        for handler in root_logger.handlers
    )

    if not has_sanitized_handler:
        # Clear default unformatted handlers to avoid duplicated output
        root_logger.handlers.clear()

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(numeric_level)
        log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        handler.setFormatter(SanitizedFormatter(log_format))
        root_logger.addHandler(handler)

    return root_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Convenience getter for namespaced loggers."""
    return logging.getLogger(name or "knovera")
