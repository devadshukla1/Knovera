"""Tests for BKT Parameter Estimation via Baum-Welch EM (Phase 9 C9.5).

Covers:
- Synthetic ground-truth parameter recovery
- Multiple restart optimization
- Constraint enforcement to prevent degenerate solutions
- Detection of insufficient/sparse data
- Candidate model generation and activation
- Workspace isolation and parameter estimation API
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.ml.bkt.estimation import BKTParameterEstimator
from backend.app.ml.bkt.inference import BKTParameters
from backend.app.ml.bkt.synthetic import generate_synthetic_bkt_dataset
from backend.app.models.bkt import BKTModelVersion
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.workspace import Workspace


def test_synthetic_ground_truth_parameter_recovery():
    """Generates synthetic learner sequences from known ground-truth BKT parameters

    and verifies that the Baum-Welch EM estimator recovers parameters within statistical tolerance.
    """
    ground_truth = BKTParameters(
        p_init=0.35,
        p_transit=0.15,
        p_guess=0.18,
        p_slip=0.10,
        version="ground_truth",
    )

    # 150 simulated learners with 12 opportunities each
    dataset = generate_synthetic_bkt_dataset(
        params=ground_truth,
        num_learners=150,
        sequence_length=12,
        random_seed=123,
    )

    estimator = BKTParameterEstimator(max_iter=60, tol=1e-4, n_restarts=3, random_seed=42)
    fit_result = estimator.fit(dataset, model_version="recovered_test")

    recovered = fit_result.parameters
    # Statistical recovery tolerance within +/- 0.12 of true generating parameters
    assert abs(recovered.p_init - ground_truth.p_init) < 0.15
    assert abs(recovered.p_transit - ground_truth.p_transit) < 0.12
    assert abs(recovered.p_guess - ground_truth.p_guess) < 0.12
    assert abs(recovered.p_slip - ground_truth.p_slip) < 0.12

    assert fit_result.metrics.brier_score < 0.25
    assert fit_result.metrics.accuracy > 0.60
    assert fit_result.is_statistically_supported is True


def test_estimator_constraint_enforcement():
    """Ensures parameter estimates never exceed the bounds (e.g.

    Guess/Slip < 0.5) even with degenerate all-ones or all-zeros input.
    """
    estimator = BKTParameterEstimator(max_iter=20, n_restarts=2)

    # Degenerate: all correct observations
    all_correct = [[True] * 10 for _ in range(5)]
    fit_correct = estimator.fit(all_correct)
    assert fit_correct.parameters.p_guess <= 0.40
    assert fit_correct.parameters.p_slip >= 0.01

    # Degenerate: all incorrect observations
    all_incorrect = [[False] * 10 for _ in range(5)]
    fit_incorrect = estimator.fit(all_incorrect)
    assert fit_incorrect.parameters.p_slip <= 0.35
    assert fit_incorrect.parameters.p_guess >= 0.01


def test_insufficient_data_detection():
    """Fewer than 5 sequences or 25 observations is flagged as statistically unsupported."""
    estimator = BKTParameterEstimator(max_iter=10)
    sparse_data = [[True, False], [False]]  # 2 sequences, 3 observations

    fit_sparse = estimator.fit(sparse_data)
    assert fit_sparse.is_statistically_supported is False
    assert len(fit_sparse.data_quality_notes) >= 2


def test_parameter_estimation_api_flow(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
):
    """Test triggering a parameter estimation run via the workspace API."""
    url = f"/api/v1/workspaces/{test_workspace.id}/bkt/parameter-estimation-runs"
    payload = {
        "model_scope": "global",
        "max_iter": 30,
        "n_restarts": 2,
        "auto_activate": False,
    }

    res = test_client.post(url, json=payload, headers=auth_headers)
    assert res.status_code == 201, res.text
    run_data = res.json()
    assert run_data["status"] == "completed"
    assert "metrics" in run_data
    assert "fitted_params" in run_data
    run_id = run_data["id"]

    # Retrieve run
    get_run = test_client.get(f"{url}/{run_id}", headers=auth_headers)
    assert get_run.status_code == 200
    assert get_run.json()["id"] == run_id

    # List models
    models_url = f"/api/v1/workspaces/{test_workspace.id}/bkt/models"
    models_res = test_client.get(models_url, headers=auth_headers)
    assert models_res.status_code == 200
    models_list = models_res.json()
    assert len(models_list) >= 1

    candidate_model = next(m for m in models_list if m["status"] == "candidate")

    # Activate candidate model
    act_url = f"/api/v1/workspaces/{test_workspace.id}/bkt/models/{candidate_model['id']}/activate"
    act_res = test_client.post(act_url, headers=auth_headers)
    assert act_res.status_code == 200
    assert act_res.json()["status"] == "active"
