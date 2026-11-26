"""LLM Provider Registry for dynamic adapter discovery and management (Phase 3 C3.4)."""

import threading
from typing import Dict, List, Optional

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.llm.base import LLMProvider
from backend.app.llm.exceptions import ProviderConfigurationError
from backend.app.llm.providers.gemini import GeminiProvider
from backend.app.llm.providers.groq import GroqProvider
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.llm.providers.openai_compatible import OpenAICompatibleProvider

logger = get_logger("knovera.llm.registry")


class LLMProviderRegistry:
    """Thread-safe registry of initialized and configured LLM providers."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._providers: Dict[str, LLMProvider] = {}
        self._lock = threading.Lock()
        self._initialize_default_providers()

    def _initialize_default_providers(self) -> None:
        """Initializes built-in provider adapters from environment settings."""
        # Mock Provider
        self._providers["mock"] = MockLLMProvider()

        # Google Gemini Provider
        gemini_key = self.settings.GEMINI_API_KEY.get_secret_value() if self.settings.GEMINI_API_KEY else None
        self._providers["gemini"] = GeminiProvider(api_key=gemini_key)

        # Groq Provider
        groq_key = self.settings.GROQ_API_KEY.get_secret_value() if self.settings.GROQ_API_KEY else None
        self._providers["groq"] = GroqProvider(api_key=groq_key)

        # Generic OpenAI-Compatible Provider
        openai_key = (
            self.settings.OPENAI_COMPATIBLE_API_KEY.get_secret_value()
            if self.settings.OPENAI_COMPATIBLE_API_KEY
            else None
        )
        self._providers["openai_compatible"] = OpenAICompatibleProvider(
            base_url=self.settings.OPENAI_COMPATIBLE_BASE_URL,
            api_key=openai_key,
        )

    def register(self, name: str, provider: LLMProvider) -> None:
        """Registers or overrides a provider adapter instance (e.g. for testing)."""
        clean_name = name.strip().lower()
        with self._lock:
            self._providers[clean_name] = provider
            logger.info("Registered LLM provider adapter: '%s'", clean_name)

    def get(self, name: str) -> LLMProvider:
        """Retrieves provider by name. Raises ProviderConfigurationError if unknown."""
        clean_name = name.strip().lower()
        with self._lock:
            provider = self._providers.get(clean_name)
            if not provider:
                raise ProviderConfigurationError(
                    f"Unknown or unregistered LLM provider '{clean_name}'. Available: {list(self._providers.keys())}",
                    provider=clean_name,
                )
            return provider

    def available_providers(self) -> List[str]:
        """Returns list of registered provider names."""
        with self._lock:
            return list(self._providers.keys())
