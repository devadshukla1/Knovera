"""Mock LLM Provider for unit testing and offline CI execution (Phase 3 C3.4)."""

import json
import time
from typing import Any, Dict, Optional, Tuple

from backend.app.llm.base import LLMProvider
from backend.app.llm.capabilities import ModelCapabilities, get_model_capabilities
from backend.app.llm.exceptions import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from backend.app.llm.schemas import LLMGenerationRequest, LLMGenerationResponse


class MockLLMProvider(LLMProvider):
    """Deterministic, zero-network mock provider for fast and reliable automated tests."""

    def __init__(
        self,
        default_response: Optional[str] = None,
        simulate_error: Optional[str] = None,
        latency_ms: int = 15,
    ) -> None:
        self._default_response = default_response
        self._simulate_error = simulate_error
        self._latency_ms = latency_ms
        self.call_history: list[LLMGenerationRequest] = []

    def set_response(self, response: str) -> None:
        """Sets simulated text response."""
        self._default_response = response

    def set_error_simulation(self, error_type: Optional[str]) -> None:
        """Sets error simulation flag ('auth', 'rate_limit', 'timeout', 'unavailable', None)."""
        self._simulate_error = error_type

    def get_provider_name(self) -> str:
        return "mock"

    def is_configured(self) -> bool:
        return True

    def get_capabilities(self, model: str) -> ModelCapabilities:
        return get_model_capabilities(provider_name="mock", model_id=model, default_context=16384)

    async def health_check(self) -> Tuple[bool, Optional[str]]:
        if self._simulate_error == "unavailable":
            return False, "Simulated mock provider outage"
        return True, None

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        self.call_history.append(request)

        # Simulate errors if configured
        if self._simulate_error == "auth":
            raise ProviderAuthenticationError("Invalid API key for mock provider", provider="mock")
        if self._simulate_error == "rate_limit":
            raise ProviderRateLimitError("Mock provider rate limit exceeded", provider="mock", retry_after=1.0)
        if self._simulate_error == "timeout":
            raise ProviderTimeoutError("Mock provider timed out", provider="mock")
        if self._simulate_error == "unavailable":
            raise ProviderUnavailableError("Mock provider service 503", provider="mock")

        # Determine response content
        if self._default_response is not None:
            content = self._default_response
        elif request.response_format == "json_object":
            # Generate valid StructuredAnswerDraft JSON by default
            content = json.dumps({
                "answer": f"Mock evidence-based response to: {request.messages[-1].content[:60]}",
                "claims": [
                    {
                        "text": "Evidence-grounded finding derived from provided document chunks.",
                        "source_ids": ["S1"],
                    }
                ],
                "limitations": [],
                "insufficient_evidence": False,
            })
        else:
            content = f"Mock generated answer for query based on {len(request.messages)} messages."

        # Compute simulated token counts (~ 4 characters per token)
        prompt_text = " ".join([m.content for m in request.messages])
        input_tokens = max(1, len(prompt_text) // 4)
        output_tokens = max(1, len(content) // 4)

        return LLMGenerationResponse(
            content=content,
            provider="mock",
            requested_model=request.model,
            actual_model=f"mock-{request.model}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            finish_reason="stop",
            request_id=f"mock-req-{len(self.call_history)}",
            latency_ms=self._latency_ms,
            usage_metadata={"mock_execution": True},
        )
