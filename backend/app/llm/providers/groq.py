"""Groq Cloud API provider adapter (Phase 3 C3.4)."""

from typing import Optional
import httpx

from backend.app.llm.exceptions import ProviderConfigurationError
from backend.app.llm.providers.openai_compatible import OpenAICompatibleProvider
from backend.app.llm.schemas import LLMGenerationRequest, LLMGenerationResponse

GROQ_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(OpenAICompatibleProvider):
    """Adapter for Groq Cloud fast-inference open models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        effective_base_url = base_url or GROQ_DEFAULT_BASE_URL
        super().__init__(
            base_url=effective_base_url,
            api_key=api_key,
            provider_name="groq",
            client=client,
        )

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        if not self._api_key:
            raise ProviderConfigurationError(
                "AI Service Configuration Error: Server administrator has not configured "
                "GROQ_API_KEY in the backend environment (.env). Please contact your system "
                "administrator to configure the server credentials.",
                provider="groq",
            )
        return await super().generate(request)
