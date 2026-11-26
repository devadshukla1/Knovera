"""Knovera LLM Provider Abstraction Package (Phase 3 C3.4)."""

from backend.app.llm.base import LLMProvider
from backend.app.llm.capabilities import ModelCapabilities, get_model_capabilities
from backend.app.llm.exceptions import (
    LLMException,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderContextLengthError,
    ProviderGenerationError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from backend.app.llm.manager import LLMManager
from backend.app.llm.registry import LLMProviderRegistry
from backend.app.llm.schemas import (
    ChatMessage,
    LLMGenerationRequest,
    LLMGenerationResponse,
    MessageRole,
    TokenUsage,
)

__all__ = [
    "ChatMessage",
    "LLMException",
    "LLMGenerationRequest",
    "LLMGenerationResponse",
    "LLMManager",
    "LLMProvider",
    "LLMProviderRegistry",
    "MessageRole",
    "ModelCapabilities",
    "ProviderAuthenticationError",
    "ProviderConfigurationError",
    "ProviderContextLengthError",
    "ProviderGenerationError",
    "ProviderInvalidRequestError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "TokenUsage",
    "get_model_capabilities",
]
