"""Google Gemini API provider adapter (Phase 3 C3.4)."""

import time
from typing import Any, Dict, Optional, Tuple
import httpx

from backend.app.core.logging import get_logger
from backend.app.llm.base import LLMProvider
from backend.app.llm.capabilities import ModelCapabilities, get_model_capabilities
from backend.app.llm.exceptions import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderGenerationError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from backend.app.llm.schemas import (
    LLMGenerationRequest,
    LLMGenerationResponse,
    MessageRole,
)

logger = get_logger("knovera.llm.gemini")

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(LLMProvider):
    """Adapter for Google Generative AI (Gemini) REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = (base_url or GEMINI_API_BASE_URL).rstrip("/")
        self._client = client

    def get_provider_name(self) -> str:
        return "gemini"

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_capabilities(self, model: str) -> ModelCapabilities:
        return get_model_capabilities(provider_name="gemini", model_id=model)

    def _get_client(self, timeout_seconds: float) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))

    async def health_check(self) -> Tuple[bool, Optional[str]]:
        if not self.is_configured():
            return False, "Gemini API key is not configured"

        # Ping model metadata endpoint for connectivity verification
        url = f"{self._base_url}/gemini-2.0-flash?key={self._api_key}"
        try:
            client = self._get_client(10.0)
            close_after = self._client is None
            try:
                res = await client.get(url)
                if res.status_code == 200:
                    return True, None
                if res.status_code in (401, 403):
                    return False, "Invalid or unauthorized Gemini API key"
                return False, f"Gemini health probe returned HTTP {res.status_code}"
            finally:
                if close_after:
                    await client.aclose()
        except Exception as exc:
            return False, f"Gemini connection failed: {exc}"

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        if not self.is_configured():
            raise ProviderConfigurationError("Gemini provider is missing GEMINI_API_KEY", provider="gemini")

        url = f"{self._base_url}/{request.model}:generateContent?key={self._api_key}"

        # Separate system messages from conversation turns
        system_instruction_parts = []
        contents = []

        for msg in request.messages:
            if msg.role == MessageRole.SYSTEM:
                system_instruction_parts.append({"text": msg.content})
            else:
                gemini_role = "user" if msg.role == MessageRole.USER else "model"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": msg.content}],
                })

        generation_config: Dict[str, Any] = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_output_tokens,
        }

        if request.response_format == "json_object":
            generation_config["responseMimeType"] = "application/json"

        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }

        if system_instruction_parts:
            body["systemInstruction"] = {"parts": system_instruction_parts}

        start_time = time.perf_counter()
        client = self._get_client(request.timeout_seconds)
        close_after = self._client is None

        try:
            response = await client.post(url, json=body, headers={"Content-Type": "application/json"})
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Error status mapping
            if response.status_code in (401, 403):
                raise ProviderAuthenticationError(
                    f"Gemini authentication failed (HTTP {response.status_code}): {response.text[:150]}",
                    provider="gemini",
                )
            if response.status_code == 429:
                retry_after_str = response.headers.get("retry-after")
                retry_after = float(retry_after_str) if retry_after_str and retry_after_str.isdigit() else None
                raise ProviderRateLimitError(
                    "Gemini quota or rate limit exceeded",
                    provider="gemini",
                    retry_after=retry_after,
                )
            if response.status_code in (400, 422):
                raise ProviderInvalidRequestError(
                    f"Gemini rejected request: {response.text[:200]}",
                    provider="gemini",
                )
            if response.status_code >= 500:
                raise ProviderUnavailableError(
                    f"Gemini service unavailable (HTTP {response.status_code})",
                    provider="gemini",
                )
            if response.status_code != 200:
                raise ProviderGenerationError(
                    f"Gemini returned unexpected HTTP {response.status_code}",
                    provider="gemini",
                )

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ProviderGenerationError("Gemini returned zero candidates", provider="gemini")

            first_candidate = candidates[0]
            candidate_content = first_candidate.get("content", {})
            parts = candidate_content.get("parts", [])
            if not parts:
                raise ProviderGenerationError("Gemini candidate contains no content parts", provider="gemini")

            text_content = "".join([p.get("text", "") for p in parts])

            usage = data.get("usageMetadata", {})
            input_tokens = usage.get("promptTokenCount")
            output_tokens = usage.get("candidatesTokenCount")
            total_tokens = usage.get("totalTokenCount")

            return LLMGenerationResponse(
                content=text_content,
                provider="gemini",
                requested_model=request.model,
                actual_model=data.get("modelVersion", request.model),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                finish_reason=first_candidate.get("finishReason"),
                request_id=response.headers.get("x-goog-request-id"),
                latency_ms=latency_ms,
                usage_metadata=usage,
            )

        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ProviderTimeoutError(
                f"Gemini generation timed out after {request.timeout_seconds}s",
                provider="gemini",
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise ProviderUnavailableError(f"Gemini network connection failed: {exc}", provider="gemini") from exc
        finally:
            if close_after:
                await client.aclose()
