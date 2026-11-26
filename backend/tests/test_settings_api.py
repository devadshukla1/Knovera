"""Tests for Settings and LLM provider configuration endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import get_settings


@pytest.fixture
def client(monkeypatch):
    from backend.app.api.v1.endpoints import settings as settings_ep
    settings = get_settings()
    orig_key = settings.GROQ_API_KEY
    orig_model = settings.GROQ_MODEL
    monkeypatch.setattr(settings_ep, "_update_env_file", lambda k, v: None)
    yield TestClient(app)
    settings.GROQ_API_KEY = orig_key
    settings.GROQ_MODEL = orig_model


def test_get_llm_settings(client):
    response = client.get("/api/v1/settings/llm")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "groq"
    assert "model" in data
    assert "is_configured" in data


def test_update_and_test_llm_settings_flow(client):
    # Test updating key
    test_key = "gsk_testdummykey1234567890abcdef"
    res = client.post("/api/v1/settings/llm", json={"api_key": test_key})
    assert res.status_code == 200
    data = res.json()
    assert data["is_configured"] is True
    assert data["masked_api_key"] == "gsk_...cdef"

    # Test get reflects masked key
    get_res = client.get("/api/v1/settings/llm")
    assert get_res.status_code == 200
    assert get_res.json()["masked_api_key"] == "gsk_...cdef"


def test_connection_test_invalid_key_fails(client):
    # Connection test with dummy key should fail gracefully with HTTP 502
    res = client.post("/api/v1/settings/llm/test-connection", json={"api_key": "gsk_invalid_test_key"})
    assert res.status_code == 502
    assert "connection test failed" in res.json()["detail"].lower()
