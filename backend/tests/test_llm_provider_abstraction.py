"""Tests for LLM Provider Abstraction, Registry, Manager, and Adapters (Phase 3 C3.4)."""

import json
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from backend.app.llm.capabilities import get_model_capabilities
from backend.app.llm.exceptions import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderContextLengthError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.gemini import GeminiProvider
from backend.app.llm.providers.groq import GroqProvider
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.llm.providers.openai_compatible import (
    OpenAICompatibleProvider,
    validate_base_url,
)
from backend.app.llm.registry import LLMProviderRegistry
from backend.app.llm.schemas import (
    ChatMessage,
    LLMGenerationRequest,
    MessageRole,
)


def test_registry_registration_and_lookup():
    """Verifies provider registry registration, case-insensitivity, and unknown provider rejection."""
    registry = LLMProviderRegistry()
    assert "mock" in registry.available_providers()

    custom_mock = MockLLMProvider()
    registry.register("custom", custom_mock)
    assert registry.get("custom") is custom_mock
    assert registry.get("CUSTOM") is custom_mock

    with pytest.raises(ProviderConfigurationError) as exc:
        registry.get("nonexistent_vendor")
    assert "Unknown or unregistered" in str(exc.value)


def test_validate_base_url_ssrf_protection():
    """Verifies that generic OpenAI base URL blocks non-HTTP and cloud metadata IPs."""
    assert validate_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert validate_base_url("http://localhost:11434/v1") == "http://localhost:11434/v1"

    # Reject non-http schemes
    with pytest.raises(ProviderConfigurationError) as exc:
        validate_base_url("ftp://internal.server")
    assert "Only http and https" in str(exc.value)

    # Reject cloud metadata IP
    with pytest.raises(ProviderConfigurationError) as exc:
        validate_base_url("http://169.254.169.254/latest/meta-data")
    assert "blocked" in str(exc.value)


@pytest.mark.asyncio
async def test_mock_provider_generation_and_normalisation():
    """Verifies MockLLMProvider generates normalised LLMGenerationResponse."""
    provider = MockLLMProvider(default_response="Custom mock answer.")
    request = LLMGenerationRequest(
        model="mock-model",
        messages=[
            ChatMessage(role=MessageRole.SYSTEM, content="System prompt"),
            ChatMessage(role=MessageRole.USER, content="User question"),
        ],
        temperature=0.2,
        max_output_tokens=500,
    )

    response = await provider.generate(request)
    assert response.content == "Custom mock answer."
    assert response.provider == "mock"
    assert response.requested_model == "mock-model"
    assert response.finish_reason == "stop"
    assert response.input_tokens is not None and response.input_tokens > 0
    assert response.output_tokens is not None and response.output_tokens > 0
    assert response.latency_ms >= 0


@pytest.mark.asyncio
async def test_mock_provider_json_mode():
    """Verifies MockLLMProvider default JSON output adheres to StructuredAnswerDraft schema."""
    provider = MockLLMProvider()
    request = LLMGenerationRequest(
        model="mock-model",
        messages=[ChatMessage(role=MessageRole.USER, content="What is knowledge?")],
        response_format="json_object",
    )

    response = await provider.generate(request)
    parsed = json.loads(response.content)
    assert "answer" in parsed
    assert "claims" in parsed
    assert "insufficient_evidence" in parsed


@pytest.mark.asyncio
async def test_llm_manager_retry_on_rate_limit():
    """Verifies that LLMManager retries on transient rate limit and succeeds."""
    mock_provider = MockLLMProvider()
    # First attempt fails with rate limit, second attempt succeeds
    mock_provider.set_error_simulation("rate_limit")

    registry = LLMProviderRegistry()
    registry.register("mock", mock_provider)
    manager = LLMManager(registry=registry)

    # Patch sleep to keep test instantaneous
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # After 1 failure, clear error simulation
        async def clear_err(*args):
            mock_provider.set_error_simulation(None)

        mock_sleep.side_effect = clear_err

        request = LLMGenerationRequest(
            model="mock-model",
            messages=[ChatMessage(role=MessageRole.USER, content="Test retry")],
        )

        response = await manager.generate_with_retry(request, provider=mock_provider)
        assert response is not None
        assert mock_sleep.called
        assert len(mock_provider.call_history) == 2


@pytest.mark.asyncio
async def test_llm_manager_fails_immediately_on_auth_error():
    """Verifies non-retryable authentication errors fail immediately without retry loops."""
    mock_provider = MockLLMProvider(simulate_error="auth")
    registry = LLMProviderRegistry()
    registry.register("mock", mock_provider)
    manager = LLMManager(registry=registry)

    request = LLMGenerationRequest(
        model="mock-model",
        messages=[ChatMessage(role=MessageRole.USER, content="Test auth")],
    )

    with pytest.raises(ProviderAuthenticationError):
        await manager.generate_with_retry(request, provider=mock_provider)

    assert len(mock_provider.call_history) == 1  # No repeated retries


@pytest.mark.asyncio
async def test_llm_manager_enforces_context_length_check():
    """Verifies LLMManager rejects requests exceeding model context window before network call."""
    mock_provider = MockLLMProvider()
    manager = LLMManager()

    # Create message with massive content
    huge_text = "word " * 50000
    request = LLMGenerationRequest(
        model="mock-model",
        messages=[ChatMessage(role=MessageRole.USER, content=huge_text)],
    )

    with pytest.raises(ProviderContextLengthError) as exc:
        await manager.generate_with_retry(request, provider=mock_provider)
    assert "exceed model context window" in str(exc.value)
    assert len(mock_provider.call_history) == 0


@pytest.mark.asyncio
async def test_openai_compatible_adapter_http_mapping():
    """Verifies OpenAICompatibleProvider formats messages and parses response correctly."""
    mock_transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json={
                "id": "chatcmpl-123",
                "model": "gpt-oss-model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "OpenAI compatible response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            },
        )
    )

    async with httpx.AsyncClient(transport=mock_transport) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.com/v1",
            api_key="test-key",
            client=client,
        )

        request = LLMGenerationRequest(
            model="gpt-oss-model",
            messages=[ChatMessage(role=MessageRole.USER, content="Hello server")],
        )

        response = await provider.generate(request)
        assert response.content == "OpenAI compatible response"
        assert response.input_tokens == 20
        assert response.output_tokens == 10
        assert response.total_tokens == 30
        assert response.request_id == "chatcmpl-123"


@pytest.mark.asyncio
async def test_gemini_adapter_http_mapping():
    """Verifies GeminiProvider formats systemInstruction/contents and maps Gemini response."""
    mock_transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Gemini response text"}],
                            "role": "model",
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 25,
                    "candidatesTokenCount": 15,
                    "totalTokenCount": 40,
                },
                "modelVersion": "gemini-2.0-flash",
            },
            headers={"x-goog-request-id": "goog-req-999"},
        )
    )

    async with httpx.AsyncClient(transport=mock_transport) as client:
        provider = GeminiProvider(api_key="test-gemini-key", client=client)

        request = LLMGenerationRequest(
            model="gemini-2.0-flash",
            messages=[
                ChatMessage(role=MessageRole.SYSTEM, content="System prompt"),
                ChatMessage(role=MessageRole.USER, content="User prompt"),
            ],
        )

        response = await provider.generate(request)
        assert response.content == "Gemini response text"
        assert response.provider == "gemini"
        assert response.input_tokens == 25
        assert response.output_tokens == 15
        assert response.total_tokens == 40
        assert response.request_id == "goog-req-999"
        assert response.actual_model == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_groq_adapter_configuration():
    """Verifies GroqProvider inherits OpenAICompatibleProvider with correct defaults."""
    provider = GroqProvider(api_key="gsk_test")
    assert provider.get_provider_name() == "groq"
    assert provider.is_configured() is True
    capabilities = provider.get_capabilities("llama-3.3-70b-versatile")
    assert capabilities.max_context_tokens >= 32768
