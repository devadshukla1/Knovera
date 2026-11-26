"""Integration and security tests for Query Intent API (Phase 5 C5.8)."""

import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.workspace import Workspace


def test_predict_query_intent_unauthenticated(test_client: TestClient) -> None:
    """Verifies that unauthenticated requests to query intent endpoint succeed in local mode."""
    resp = test_client.post("/api/v1/query-intent/predict", json={"query": "What is BM25?"})
    assert resp.status_code == 200


def test_predict_query_intent_authenticated_success(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """Verifies successful intent prediction with structured response schema."""
    payload = {"query": "Compare gradient descent and Adam optimizers in neural networks."}
    resp = test_client.post("/api/v1/query-intent/predict", json=payload, headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "predicted_intent" in data
    assert "top_intents" in data
    assert isinstance(data["top_intents"], list)
    assert len(data["top_intents"]) > 0
    assert "score" in data["top_intents"][0]
    assert "intent" in data["top_intents"][0]
    assert "confidence_type" in data
    assert data["confidence_type"] in (
        "calibrated_probability",
        "uncalibrated_probability",
        "decision_score",
        "unavailable",
    )
    assert data["taxonomy_version"] == "1.0.0"
    assert "prediction_latency_ms" in data
    assert data["prediction_latency_ms"] >= 0.0


def test_predict_query_intent_alternative_route(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """Verifies that the /api/v1/query/intent route alias also functions identically."""
    payload = {"query": "What is the definition of Reciprocal Rank Fusion?"}
    resp = test_client.post("/api/v1/query/intent", json=payload, headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["taxonomy_version"] == "1.0.0"


def test_predict_query_intent_empty_query_rejected(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """Verifies that empty string or whitespace queries return HTTP 422."""
    resp = test_client.post("/api/v1/query-intent/predict", json={"query": ""}, headers=auth_headers)
    assert resp.status_code == 422

    resp_ws = test_client.post("/api/v1/query-intent/predict", json={"query": "   \n\t  "}, headers=auth_headers)
    assert resp_ws.status_code == 422


def test_predict_query_intent_excessively_long_query(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """Verifies that queries exceeding maximum configured limit return HTTP 422."""
    huge_query = "word " * 600
    resp = test_client.post("/api/v1/query-intent/predict", json={"query": huge_query}, headers=auth_headers)
    assert resp.status_code == 422


def test_predict_query_intent_with_valid_workspace(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
) -> None:
    """Verifies that passing a valid, owned workspace ID succeeds."""
    payload = {
        "query": "Where in the paper is the 95% accuracy claim located?",
        "workspace_id": str(test_workspace.id),
    }
    resp = test_client.post("/api/v1/query-intent/predict", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert "predicted_intent" in resp.json()


def test_predict_query_intent_with_inaccessible_workspace(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """Verifies that specifying a non-existent or inaccessible workspace ID returns non-disclosing 404."""
    random_ws = str(uuid.uuid4())
    payload = {
        "query": "Where in the paper is the claim located?",
        "workspace_id": random_ws,
    }
    resp = test_client.post("/api/v1/query-intent/predict", json=payload, headers=auth_headers)
    assert resp.status_code == 404
    assert "Workspace not found" in resp.json()["detail"]


def test_query_intent_readiness_endpoint(test_client: TestClient) -> None:
    """Verifies diagnostic readiness endpoint returns readiness metadata."""
    resp = test_client.get("/api/v1/query-intent/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ready", "unavailable")
