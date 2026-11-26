"""Abstract base protocol for LLM providers (Phase 3 C3.4)."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple

from backend.app.llm.capabilities import ModelCapabilities
from backend.app.llm.schemas import LLMGenerationRequest, LLMGenerationResponse


class LLMProvider(ABC):
    """Abstract interface for language model generation providers."""

    @abstractmethod
    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        """Executes generation against the target model with normalised request and response."""
        ...

    @abstractmethod
    async def health_check(self) -> Tuple[bool, Optional[str]]:
        """Verifies provider connectivity and credential status.

        Returns:
            Tuple of (is_healthy, error_detail_or_none).
        """
        ...

    @abstractmethod
    def get_capabilities(self, model: str) -> ModelCapabilities:
        """Returns verified or safe model capabilities for the specified model."""
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Returns unique identifier key of this provider (e.g. 'groq', 'gemini')."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if required credentials and endpoints are present."""
        ...
