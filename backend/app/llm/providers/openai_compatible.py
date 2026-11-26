"""Generic OpenAI-compatible chat completion provider adapter (Phase 3 C3.4)."""

import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse
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
from backend.app.llm.schemas import LLMGenerationRequest, LLMGenerationResponse

logger = get_logger("knovera.llm.openai_compatible")


def validate_base_url(url: str) -> str:
    """Validates base URL scheme and blocks cloud metadata endpoints (anti-SSRF)."""
    if not url:
        raise ProviderConfigurationError("Base URL cannot be empty")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ProviderConfigurationError(f"Invalid URL scheme '{parsed.scheme}'. Only http and https are permitted.")

    hostname = (parsed.hostname or "").lower()
    blocked_hosts = {"169.254.169.254", "metadata.google.internal", "instance-data"}
    if hostname in blocked_hosts:
        raise ProviderConfigurationError(f"Access to link-local/cloud metadata address '{hostname}' is blocked.")

    return url.rstrip("/")


class OpenAICompatibleProvider(LLMProvider):
    """Adapter for any API implementing the standard OpenAI chat completions endpoint."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        provider_name: str = "openai_compatible",
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._provider_name = provider_name
        self._raw_base_url = base_url
        self._base_url = validate_base_url(base_url) if base_url else None
        self._api_key = api_key
        self._client = client

    def get_provider_name(self) -> str:
        return self._provider_name

    def is_configured(self) -> bool:
        return bool(self._base_url and self._api_key)

    def get_capabilities(self, model: str) -> ModelCapabilities:
        return get_model_capabilities(provider_name=self._provider_name, model_id=model)

    def _get_client(self, timeout_seconds: float) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))

    async def health_check(self) -> Tuple[bool, Optional[str]]:
        if not self.is_configured():
            return False, f"Provider '{self._provider_name}' is not configured (missing base URL or API key)"

        endpoint = f"{self._base_url}/models"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            client = self._get_client(10.0)
            close_after = self._client is None
            try:
                res = await client.get(endpoint, headers=headers)
                if res.status_code in (200, 404):  # 404 indicates endpoint reachable even if /models is restricted
                    return True, None
                return False, f"Health probe returned HTTP {res.status_code}"
            finally:
                if close_after:
                    await client.aclose()
        except Exception as exc:
            return False, f"Health check connection failed: {exc}"

    async def verify_full_connection(self, model_id: str) -> Dict[str, Any]:
        """Executes distinct verification stages: config -> auth -> model availability -> live inference."""
        if not self.is_configured():
            return {
                "status": "not_configured",
                "credential_configured": False,
                "provider_authenticated": False,
                "model_available": False,
                "inference_ok": False,
                "message": f"Provider '{self._provider_name}' is not configured (missing API key or base URL).",
            }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        client = self._get_client(15.0)
        close_after = self._client is None
        try:
            # Stage 1: Provider authentication & model catalog check
            models_res = await client.get(f"{self._base_url}/models", headers=headers)
            if models_res.status_code in (401, 403):
                return {
                    "status": "authentication_failed",
                    "credential_configured": True,
                    "provider_authenticated": False,
                    "model_available": False,
                    "inference_ok": False,
                    "message": f"Authentication rejected by {self._provider_name} (HTTP {models_res.status_code}). Verify GROQ_API_KEY in backend .env.",
                }
            if models_res.status_code != 200:
                return {
                    "status": "provider_unreachable",
                    "credential_configured": True,
                    "provider_authenticated": False,
                    "model_available": False,
                    "inference_ok": False,
                    "message": f"Provider endpoint returned HTTP {models_res.status_code}.",
                }

            available_models = [m.get("id") for m in models_res.json().get("data", []) if isinstance(m, dict)]
            if model_id and available_models and model_id not in available_models:
                return {
                    "status": "model_unavailable",
                    "credential_configured": True,
                    "provider_authenticated": True,
                    "model_available": False,
                    "inference_ok": False,
                    "message": f"Configured model '{model_id}' is not available on this {self._provider_name} account.",
                }

            # Stage 2: Small live inference verification
            inf_res = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": "Reply with OK"}],
                    "max_tokens": 5,
                    "temperature": 0.0,
                },
            )
            if inf_res.status_code in (401, 403):
                return {
                    "status": "authentication_failed",
                    "credential_configured": True,
                    "provider_authenticated": False,
                    "model_available": True,
                    "inference_ok": False,
                    "message": f"Inference rejected by {self._provider_name} (HTTP {inf_res.status_code}).",
                }
            if inf_res.status_code != 200:
                return {
                    "status": "inference_failed",
                    "credential_configured": True,
                    "provider_authenticated": True,
                    "model_available": True,
                    "inference_ok": False,
                    "message": f"Inference test failed (HTTP {inf_res.status_code}): {inf_res.text[:160]}",
                }

            choices = inf_res.json().get("choices", [])
            if not choices or choices[0].get("message", {}).get("content") is None:
                return {
                    "status": "inference_failed",
                    "credential_configured": True,
                    "provider_authenticated": True,
                    "model_available": True,
                    "inference_ok": False,
                    "message": "Inference test returned empty completion.",
                }

            return {
                "status": "active_ready",
                "credential_configured": True,
                "provider_authenticated": True,
                "model_available": True,
                "inference_ok": True,
                "message": f"Groq Cloud authentication, model '{model_id}', and live inference verified.",
            }
        except Exception as exc:
            return {
                "status": "provider_unreachable",
                "credential_configured": True,
                "provider_authenticated": False,
                "model_available": False,
                "inference_ok": False,
                "message": f"Provider connection error: {exc}",
            }
        finally:
            if close_after:
                await client.aclose()

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        if not self.is_configured():
            raise ProviderConfigurationError(
                f"Provider '{self._provider_name}' is missing base URL or API key",
                provider=self._provider_name,
            )

        endpoint = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        # Format message payloads
        formatted_messages = [{"role": msg.role.value, "content": msg.content} for msg in request.messages]

        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": formatted_messages,
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }

        if request.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}

        start_time = time.perf_counter()
        client = self._get_client(request.timeout_seconds)
        close_after = self._client is None

        try:
            response = await client.post(endpoint, json=payload, headers=headers)
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Map HTTP status codes to provider-neutral exceptions
            if response.status_code == 401 or response.status_code == 403:
                raise ProviderAuthenticationError(
                    f"Authentication rejected by {self._provider_name} (HTTP {response.status_code})",
                    provider=self._provider_name,
                )
            if response.status_code == 429:
                retry_after_str = response.headers.get("retry-after")
                retry_after = float(retry_after_str) if retry_after_str and retry_after_str.isdigit() else None
                raise ProviderRateLimitError(
                    f"Rate limit or quota threshold exceeded on {self._provider_name}",
                    provider=self._provider_name,
                    retry_after=retry_after,
                )
            if response.status_code in (400, 422):
                raise ProviderInvalidRequestError(
                    f"Invalid generation request rejected by {self._provider_name}: {response.text[:200]}",
                    provider=self._provider_name,
                )
            if response.status_code >= 500:
                raise ProviderUnavailableError(
                    f"{self._provider_name} returned server error (HTTP {response.status_code})",
                    provider=self._provider_name,
                )

            if response.status_code != 200:
                raise ProviderGenerationError(
                    f"Unexpected status HTTP {response.status_code} from {self._provider_name}",
                    provider=self._provider_name,
                )

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise ProviderGenerationError(f"No choices returned by {self._provider_name}", provider=self._provider_name)

            message_obj = choices[0].get("message", {})
            content = message_obj.get("content")
            if content is None:
                raise ProviderGenerationError("Empty completion content received", provider=self._provider_name)

            usage = data.get("usage") or {}
            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")

            return LLMGenerationResponse(
                content=content,
                provider=self._provider_name,
                requested_model=request.model,
                actual_model=data.get("model", request.model),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                finish_reason=choices[0].get("finish_reason"),
                request_id=data.get("id"),
                latency_ms=latency_ms,
                usage_metadata=usage,
            )

        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ProviderTimeoutError(
                f"Generation request to {self._provider_name} timed out after {request.timeout_seconds}s",
                provider=self._provider_name,
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise ProviderUnavailableError(
                f"Network connection to {self._provider_name} failed: {exc}",
                provider=self._provider_name,
            ) from exc
        finally:
            if close_after:
                await client.aclose()
