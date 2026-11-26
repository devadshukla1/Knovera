"""Tests for Knovera liveness and readiness health endpoints.

Validates that:
- Liveness returns 200 OK.
- Readiness returns 200 OK when both PostgreSQL and ChromaDB are reachable.
- Readiness returns 503 Service Unavailable when PostgreSQL is down.
- Readiness returns 503 Service Unavailable when ChromaDB is down.
- Readiness returns 503 Service Unavailable when both are down.
- Both root (/health, /health/ready) and versioned (/api/v1/health, /api/v1/health/ready) routes work.
- Zero credential leakage occurs under all conditions (passwords, DSNs, stack traces).
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings


def assert_zero_credential_leakage(response_text: str) -> None:
    """Verifies that no secrets, credentials, hosts, or tracebacks leak in response."""
    settings = get_settings()
    forbidden_tokens = [
        settings.POSTGRES_PASSWORD.get_secret_value(),
        "change_me_locally",
        "postgresql+psycopg",
        "Traceback (most recent call last)",
        "POSTGRES_PASSWORD",
        "AUTH_SECRET_KEY",
        settings.AUTH_SECRET_KEY.get_secret_value(),
        f"{settings.POSTGRES_USER}:",
    ]
    for token in forbidden_tokens:
        if token:
            assert token not in response_text, f"Credential leakage detected: {token} found in response body"


def test_liveness_root(client: TestClient) -> None:
    """GET /health returns 200 OK with expected liveness payload."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "Knovera"
    assert data["version"] == "1.0.0"
    assert "environment" in data
    assert_zero_credential_leakage(response.text)


def test_liveness_versioned(client: TestClient) -> None:
    """GET /api/v1/health returns 200 OK with expected liveness payload."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "Knovera"
    assert data["version"] == "1.0.0"
    assert "environment" in data
    assert_zero_credential_leakage(response.text)


def test_readiness_both_healthy(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /health/ready returns 200 OK when both database and ChromaDB are healthy."""
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.health.check_database_connectivity",
        lambda: (True, 1.45, None),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.health.check_chroma_connectivity",
        lambda: (True, 2.10, None),
    )

    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["services"]["database"]["status"] == "connected"
    assert data["services"]["database"]["latency_ms"] == 1.45
    assert data["services"]["vector_store"]["status"] == "connected"
    assert data["services"]["vector_store"]["latency_ms"] == 2.10
    assert_zero_credential_leakage(response.text)


def test_readiness_versioned_both_healthy(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/v1/health/ready returns 200 OK when both services are healthy."""
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.health.check_database_connectivity",
        lambda: (True, 0.95, None),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.health.check_chroma_connectivity",
        lambda: (True, 1.80, None),
    )

    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["services"]["database"]["status"] == "connected"
    assert data["services"]["vector_store"]["status"] == "connected"
    assert_zero_credential_leakage(response.text)


def test_readiness_database_down(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /health/ready returns 503 Service Unavailable when PostgreSQL is disconnected."""
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.health.check_database_connectivity",
        lambda: (False, None, "Database service unavailable"),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.health.check_chroma_connectivity",
        lambda: (True, 2.30, None),
    )

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["services"]["database"]["status"] == "disconnected"
    assert data["services"]["database"]["error"] == "Database service unavailable"
    assert data["services"]["vector_store"]["status"] == "connected"
    assert data["services"]["vector_store"]["latency_ms"] == 2.30
    assert_zero_credential_leakage(response.text)


def test_readiness_chromadb_down(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /health/ready returns 503 Service Unavailable when ChromaDB is disconnected."""
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.health.check_database_connectivity",
        lambda: (True, 1.15, None),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.health.check_chroma_connectivity",
        lambda: (False, None, "Vector store service unavailable"),
    )

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["services"]["database"]["status"] == "connected"
    assert data["services"]["database"]["latency_ms"] == 1.15
    assert data["services"]["vector_store"]["status"] == "disconnected"
    assert data["services"]["vector_store"]["error"] == "Vector store service unavailable"
    assert_zero_credential_leakage(response.text)


def test_readiness_both_down(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /health/ready returns 503 Service Unavailable when both services are disconnected."""
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.health.check_database_connectivity",
        lambda: (False, None, "Database service unavailable"),
    )
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.health.check_chroma_connectivity",
        lambda: (False, None, "Vector store service unavailable"),
    )

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["services"]["database"]["status"] == "disconnected"
    assert data["services"]["database"]["error"] == "Database service unavailable"
    assert data["services"]["vector_store"]["status"] == "disconnected"
    assert data["services"]["vector_store"]["error"] == "Vector store service unavailable"
    assert_zero_credential_leakage(response.text)


def test_readiness_live_offline_graceful_degradation(client: TestClient) -> None:
    """Without mocks, when services are offline, /health/ready returns 503 safely without crashing."""
    response = client.get("/health/ready")
    # In local testing without Docker running, services are offline
    assert response.status_code in (200, 503)
    data = response.json()
    assert data["status"] in ("ready", "not_ready")
    assert "services" in data
    assert "database" in data["services"]
    assert "vector_store" in data["services"]
    assert_zero_credential_leakage(response.text)
