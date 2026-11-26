"""Settings and LLM provider configuration endpoints."""

import os
import re
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from pydantic.types import SecretStr

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.groq import GroqProvider

logger = get_logger("knovera.api.settings")
router = APIRouter()


class LLMSettingsResponse(BaseModel):
    provider: str
    model: str
    is_configured: bool
    connection_status: str = "configured"
    status_detail: Optional[str] = None
    credential_configured: bool = False
    provider_authenticated: bool = False
    model_available: bool = False
    inference_ok: bool = False
    masked_api_key: Optional[str] = None


class LLMSettingsUpdateRequest(BaseModel):
    api_key: str = Field(..., min_length=5, description="Groq API key")
    model: Optional[str] = Field(default=None, description="Groq model ID")


class LLMConnectionTestRequest(BaseModel):
    api_key: Optional[str] = Field(default=None, description="Optional key to test before saving")


class LLMConnectionTestResponse(BaseModel):
    status: str
    latency_ms: Optional[float] = None
    model: str
    credential_configured: bool = False
    provider_authenticated: bool = False
    model_available: bool = False
    inference_ok: bool = False
    message: str


def _mask_key(key: Optional[str]) -> Optional[str]:
    if not key or len(key) < 8:
        return None
    return f"{key[:4]}...{key[-4:]}"


def _update_env_file(key: str, value: str) -> None:
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
        return

    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(content):
        new_content = pattern.sub(f"{key}={value}", content)
    else:
        new_content = content.rstrip("\n") + f"\n{key}={value}\n"

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(new_content)


@router.get("/llm", response_model=LLMSettingsResponse, summary="Get LLM configuration and verified health status")
async def get_llm_settings(verify: bool = True) -> LLMSettingsResponse:
    settings = get_settings()
    raw_key = settings.GROQ_API_KEY.get_secret_value() if settings.GROQ_API_KEY else None
    active_model = LLMManager.get_instance().get_active_model()

    if not raw_key:
        return LLMSettingsResponse(
            provider="groq",
            model=active_model,
            is_configured=False,
            connection_status="not_configured",
            status_detail="GROQ_API_KEY is not configured in the backend environment (.env).",
            credential_configured=False,
            provider_authenticated=False,
            model_available=False,
            inference_ok=False,
            masked_api_key=None,
        )

    if not verify:
        return LLMSettingsResponse(
            provider="groq",
            model=active_model,
            is_configured=True,
            connection_status="configured",
            status_detail="API key is configured. Run connection check to verify live inference.",
            credential_configured=True,
            provider_authenticated=False,
            model_available=False,
            inference_ok=False,
            masked_api_key=_mask_key(raw_key),
        )

    provider = GroqProvider(api_key=raw_key)
    diag = await provider.verify_full_connection(active_model)
    return LLMSettingsResponse(
        provider="groq",
        model=active_model,
        is_configured=True,
        connection_status=diag["status"],
        status_detail=diag["message"],
        credential_configured=diag["credential_configured"],
        provider_authenticated=diag["provider_authenticated"],
        model_available=diag["model_available"],
        inference_ok=diag["inference_ok"],
        masked_api_key=_mask_key(raw_key),
    )


@router.post("/llm", response_model=LLMSettingsResponse, summary="Update LLM configuration")
def update_llm_settings(payload: LLMSettingsUpdateRequest) -> LLMSettingsResponse:
    settings = get_settings()
    clean_key = payload.api_key.strip()

    # Update in settings instance
    settings.GROQ_API_KEY = SecretStr(clean_key)
    if payload.model:
        settings.GROQ_MODEL = payload.model.strip()

    # Persist into .env
    try:
        _update_env_file("GROQ_API_KEY", clean_key)
        if payload.model:
            _update_env_file("GROQ_MODEL", payload.model.strip())
    except Exception as exc:
        logger.warning("Failed to persist GROQ_API_KEY to .env: %s", exc)

    # Reinitialize Groq in LLMManager
    try:
        manager = LLMManager.get_instance()
        manager.registry.register("groq", GroqProvider(api_key=clean_key))
    except Exception as exc:
        logger.warning("Failed to refresh LLMManager provider: %s", exc)

    return LLMSettingsResponse(
        provider="groq",
        model=settings.GROQ_MODEL,
        is_configured=True,
        masked_api_key=_mask_key(clean_key),
    )


@router.post("/llm/test-connection", response_model=LLMConnectionTestResponse, summary="Test Groq LLM connection")
async def test_llm_connection(
    payload: Optional[LLMConnectionTestRequest] = None,
) -> LLMConnectionTestResponse:
    settings = get_settings()
    test_key = (payload.api_key.strip() if payload and payload.api_key else None) or (
        settings.GROQ_API_KEY.get_secret_value() if settings.GROQ_API_KEY else None
    )

    if not test_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Groq API key configured or provided to test.",
        )

    provider = GroqProvider(api_key=test_key)
    active_model = LLMManager.get_instance().get_active_model()
    start = time.perf_counter()
    diag = await provider.verify_full_connection(active_model)
    latency_ms = round((time.perf_counter() - start) * 1000.0, 2)

    if diag["status"] != "active_ready":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Groq API connection test failed ({latency_ms}ms): {diag['message']}",
        )

    return LLMConnectionTestResponse(
        status="active_ready",
        latency_ms=latency_ms,
        model=active_model,
        credential_configured=diag["credential_configured"],
        provider_authenticated=diag["provider_authenticated"],
        model_available=diag["model_available"],
        inference_ok=diag["inference_ok"],
        message=f"{diag['message']} ({latency_ms}ms).",
    )
