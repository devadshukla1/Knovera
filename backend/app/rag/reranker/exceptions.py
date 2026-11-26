"""Exceptions for Cross-Encoder reranking subsystem (Phase 4 C4.4)."""


class RerankerError(Exception):
    """Base exception for all reranker errors."""


class ModelLoadError(RerankerError):
    """Raised when Cross-Encoder model fails to download or initialize."""


class InferenceError(RerankerError):
    """Raised when Cross-Encoder forward pass fails."""


class InvalidScoreError(InferenceError):
    """Raised when Cross-Encoder outputs invalid (NaN, Inf) scores."""
