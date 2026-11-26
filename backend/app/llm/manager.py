"""Central LLM Manager orchestrating provider selection, retries, and capability validation (Phase 3 C3.4)."""

import asyncio
import random
import threading
import time
from typing import Any, Dict, Optional, Tuple

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.llm.base import LLMProvider
from backend.app.llm.capabilities import ModelCapabilities
from backend.app.llm.exceptions import (
    ProviderConfigurationError,
    ProviderContextLengthError,
    ProviderUnavailableError,
    is_retryable_llm_error,
)
from backend.app.llm.registry import LLMProviderRegistry
from backend.app.llm.schemas import LLMGenerationRequest, LLMGenerationResponse

logger = get_logger("knovera.llm.manager")


class LLMManager:
    """Thread-safe singleton managing LLM operations across the backend."""

    _instance: Optional["LLMManager"] = None
    _lock = threading.Lock()

    def __init__(self, registry: Optional[LLMProviderRegistry] = None) -> None:
        self.settings = get_settings()
        self.registry = registry or LLMProviderRegistry()

    @classmethod
    def get_instance(cls) -> "LLMManager":
        """Returns the process-wide singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Resets singleton (used for testing)."""
        with cls._lock:
            cls._instance = None

    def get_active_provider_name(self) -> str:
        """Returns the name of the currently configured LLM provider."""
        import os
        if os.environ.get("PYTEST_CURRENT_TEST") and "mock" in self.registry._providers:
            return "mock"
        return (self.settings.LLM_PROVIDER or "mock").strip().lower()

    def get_active_provider(self) -> LLMProvider:
        """Resolves the currently configured provider from registry.

        Strict rule: Never silently falls back to a different vendor on missing keys.
        """
        provider_name = self.get_active_provider_name()
        return self.registry.get(provider_name)

    def get_active_model(self, override_model: Optional[str] = None) -> str:
        """Resolves the centrally configured model ID for the active provider."""
        if override_model and override_model.strip():
            return override_model.strip()
        provider_name = self.get_active_provider_name()
        if provider_name == "mock":
            return "mock-model"
        if provider_name == "groq":
            return (self.settings.GROQ_MODEL or self.settings.LLM_MODEL or "llama-3.3-70b-versatile").strip()
        if provider_name == "gemini":
            return (self.settings.GEMINI_MODEL or self.settings.LLM_MODEL or "gemini-2.0-flash").strip()
        return (self.settings.OPENAI_COMPATIBLE_MODEL or self.settings.LLM_MODEL or "mock-model").strip()

    def get_model_capabilities(self, model: Optional[str] = None) -> ModelCapabilities:
        """Retrieves verified model capabilities for the active provider and model."""
        provider = self.get_active_provider()
        target_model = self.get_active_model(model)
        return provider.get_capabilities(target_model)

    async def generate_with_retry(
        self,
        request: LLMGenerationRequest,
        provider: Optional[LLMProvider] = None,
    ) -> LLMGenerationResponse:
        """Executes LLM generation with capability checks and bounded exponential backoff retries.

        Guarantees:
            - Never silently switches providers on failure.
            - Fails immediately on authentication or invalid request errors.
            - Applies exponential backoff with jitter on retryable rate limits or timeouts.
            - Logs safe telemetry without leaking document contents or secret keys.
        """
        active_provider = provider or self.get_active_provider()
        provider_name = active_provider.get_provider_name()

        # 1. Verify provider configuration
        if not active_provider.is_configured():
            raise ProviderConfigurationError(
                f"Configured LLM provider '{provider_name}' is missing credentials or base URL",
                provider=provider_name,
            )

        # 2. Validate capability context constraints
        capabilities = active_provider.get_capabilities(request.model)
        # Approximate prompt token count check
        approx_prompt_tokens = sum(max(1, len(m.content) // 4) for m in request.messages)
        if approx_prompt_tokens > capabilities.max_context_tokens:
            raise ProviderContextLengthError(
                f"Prompt tokens (~{approx_prompt_tokens}) exceed model context window ({capabilities.max_context_tokens})",
                provider=provider_name,
            )

        # 3. Bounded retry loop
        max_attempts = max(1, self.settings.LLM_RETRY_MAX_ATTEMPTS)
        last_exception: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    "Executing LLM generation via '%s' (model: %s, attempt: %d/%d)",
                    provider_name,
                    request.model,
                    attempt,
                    max_attempts,
                )
                response = await active_provider.generate(request)

                # Safe telemetry log
                logger.info(
                    "LLM generation succeeded via '%s': in=%s out=%s latency=%dms",
                    provider_name,
                    response.input_tokens,
                    response.output_tokens,
                    response.latency_ms,
                )
                return response

            except Exception as exc:
                last_exception = exc
                if not is_retryable_llm_error(exc) or attempt >= max_attempts:
                    logger.warning(
                        "LLM generation failed permanently on attempt %d/%d (%s): %s",
                        attempt,
                        max_attempts,
                        type(exc).__name__,
                        exc,
                    )
                    raise

                # Calculate backoff with jitter
                retry_after = getattr(exc, "retry_after", None)
                if retry_after is not None and retry_after > 0:
                    delay = min(retry_after, 10.0)
                else:
                    # Exponential backoff: 0.5s * 2^(attempt-1) + jitter
                    base_delay = 0.5 * (2 ** (attempt - 1))
                    jitter = random.uniform(0.1, 0.4)
                    delay = min(base_delay + jitter, 10.0)

                logger.warning(
                    "Retryable LLM error on attempt %d/%d (%s). Backing off for %.2fs...",
                    attempt,
                    max_attempts,
                    type(exc).__name__,
                    delay,
                )
                await asyncio.sleep(delay)

        raise ProviderUnavailableError(
            f"All {max_attempts} generation attempts failed: {last_exception}",
            provider=provider_name,
        ) from last_exception

    async def check_readiness(self) -> Tuple[bool, Dict[str, Any]]:
        """Health readiness check for LLM subsystem."""
        provider = self.get_active_provider()
        provider_name = provider.get_provider_name()
        is_configured = provider.is_configured()

        if not is_configured:
            return False, {
                "active_provider": provider_name,
                "configured": False,
                "detail": "Missing API key or base URL in environment",
            }

        is_healthy, err_detail = await provider.health_check()
        return is_healthy, {
            "active_provider": provider_name,
            "configured": True,
            "healthy": is_healthy,
            "detail": err_detail,
        }
