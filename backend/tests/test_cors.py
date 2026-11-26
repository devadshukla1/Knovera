"""Tests for CORS middleware behavior in Knovera FastAPI application."""

from fastapi.testclient import TestClient


def test_cors_preflight_allowed_origin(client: TestClient) -> None:
    """OPTIONS preflight from configured FRONTEND_ORIGIN returns CORS headers."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_cors_simple_request_allowed_origin(client: TestClient) -> None:
    """GET request from configured FRONTEND_ORIGIN returns access-control-allow-origin."""
    headers = {"Origin": "http://localhost:5173"}
    response = client.get("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_disallowed_origin(client: TestClient) -> None:
    """Requests from unauthorized origins do not receive allow-origin header matching the origin."""
    headers = {"Origin": "http://unauthorized-evil-site.com"}
    response = client.get("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") != "http://unauthorized-evil-site.com"
