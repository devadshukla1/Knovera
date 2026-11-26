"""Model and provider capability descriptors for LLM operations (Phase 3 C3.4)."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class ModelCapabilities(BaseModel):
    """Verified capability characteristics for a target language model."""

    model_config = ConfigDict(frozen=True)

    provider_name: str = Field(..., description="Provider identifier")
    model_id: str = Field(..., description="Model identifier")
    max_context_tokens: int = Field(default=8192, ge=512, description="Maximum total context window budget")
    max_output_tokens: int = Field(default=1500, ge=64, description="Maximum allowed completion tokens")
    supports_system_instruction: bool = Field(default=True, description="Supports separate system instruction")
    supports_structured_output: bool = Field(default=True, description="Supports structured/JSON object mode")
    supports_streaming: bool = Field(default=False, description="Supports streaming response mode")
    min_temperature: float = Field(default=0.0, description="Minimum allowed sampling temperature")
    max_temperature: float = Field(default=2.0, description="Maximum allowed sampling temperature")


# Known model specifications from official documentation (conservative baselines)
KNOWN_MODEL_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    # Mock Provider
    "mock-model": {
        "max_context_tokens": 16384,
        "max_output_tokens": 4096,
        "supports_system_instruction": True,
        "supports_structured_output": True,
    },
    # Google Gemini Models
    "gemini-2.0-flash": {
        "max_context_tokens": 1048576,  # 1M tokens
        "max_output_tokens": 8192,
        "supports_system_instruction": True,
        "supports_structured_output": True,
    },
    "gemini-1.5-flash": {
        "max_context_tokens": 1048576,
        "max_output_tokens": 8192,
        "supports_system_instruction": True,
        "supports_structured_output": True,
    },
    "gemini-1.5-pro": {
        "max_context_tokens": 2097152,  # 2M tokens
        "max_output_tokens": 8192,
        "supports_system_instruction": True,
        "supports_structured_output": True,
    },
    # Groq-Hosted Open Models
    "qwen/qwen3.8-27b": {
        "max_context_tokens": 131072,
        "max_output_tokens": 8192,
        "supports_system_instruction": True,
        "supports_structured_output": True,
    },
    "openai/gpt-oss-120b": {
        "max_context_tokens": 131072,
        "max_output_tokens": 8192,
        "supports_system_instruction": True,
        "supports_structured_output": True,
    },
    "openai/gpt-oss-20b": {
        "max_context_tokens": 131072,
        "max_output_tokens": 8192,
        "supports_system_instruction": True,
        "supports_structured_output": True,
    },
    "llama-3.3-70b-versatile": {
        "max_context_tokens": 131072,  # 128k context
        "max_output_tokens": 32768,
        "supports_system_instruction": True,
        "supports_structured_output": True,
    },
    "llama-3.1-8b-instant": {
        "max_context_tokens": 131072,
        "max_output_tokens": 8192,
        "supports_system_instruction": True,
        "supports_structured_output": True,
    },
    "mixtral-8x7b-32768": {
        "max_context_tokens": 32768,
        "max_output_tokens": 4096,
        "supports_system_instruction": True,
        "supports_structured_output": True,
    },
}


def get_model_capabilities(provider_name: str, model_id: str, default_context: int = 8192) -> ModelCapabilities:
    """Resolves model capabilities from verified catalogue or creates safe conservative fallback."""
    clean_model = model_id.strip().lower()
    spec = KNOWN_MODEL_CAPABILITIES.get(clean_model, {})

    return ModelCapabilities(
        provider_name=provider_name,
        model_id=model_id,
        max_context_tokens=spec.get("max_context_tokens", default_context),
        max_output_tokens=spec.get("max_output_tokens", 1500),
        supports_system_instruction=spec.get("supports_system_instruction", True),
        supports_structured_output=spec.get("supports_structured_output", True),
        supports_streaming=spec.get("supports_streaming", False),
    )
