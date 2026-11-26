"""Unit and Integration Tests for BKT Model Evaluation & Readiness Gates (Phase 9 C9.9).

Tests:
- Leakage-free dataset splitting (learner-level and temporal holdout)
- Sequential one-step-ahead response prediction protocol
- Evaluation metrics: Log Loss, Brier Score, Accuracy, AUC-ROC
- Probability calibration & Expected Calibration Error (ECE)
- Baseline comparisons (global training rate, prior-only BKT)
- Parameter stability and non-degeneracy constraints
- Readiness qualification gates
- Model activation gating and rollback API
"""

import math
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.ml.bkt.evaluation import (
    BKTEvaluationEngine,
    ObservationStep,
)
from backend.app.ml.bkt.inference import BKTParameters
from backend.app.models.bkt import BKTModelVersion, BKTEvaluationRun
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


@pytest.fixture
def test_steps():
    """Builds synthetic observation steps across multiple learners and concepts."""
    steps = []
    # Learner 1: 5 steps on concept A
    steps.append([
        ObservationStep("L1", "CA", "Q1", True, 1),
        ObservationStep("L1", "CA", "Q2", True, 2),
        ObservationStep("L1", "CA", "Q3", False, 3),
        ObservationStep("L1", "CA", "Q4", True, 4),
        ObservationStep("L1", "CA", "Q5", True, 5),
    ])
    # Learner 2: 4 steps on concept A
    steps.append([
        ObservationStep("L2", "CA", "Q1", False, 1),
        ObservationStep("L2", "CA", "Q2", False, 2),
        ObservationStep("L2", "CA", "Q3", True, 3),
        ObservationStep("L2", "CA", "Q4", True, 4),
    ])
    # Learner 3: 5 steps on concept A
    steps.append([
        ObservationStep("L3", "CA", "Q1", True, 1),
        ObservationStep("L3", "CA", "Q2", True, 2),
        ObservationStep("L3", "CA", "Q3", True, 3),
        ObservationStep("L3", "CA", "Q4", False, 4),
        ObservationStep("L3", "CA", "Q5", True, 5),
    ])
    # Learner 4: 4 steps on concept A
    steps.append([
        ObservationStep("L4", "CA", "Q1", False, 1),
        ObservationStep("L4", "CA", "Q2", True, 2),
        ObservationStep("L4", "CA", "Q3", True, 3),
        ObservationStep("L4", "CA", "Q4", True, 4),
    ])
    return steps


def test_learner_holdout_splitting(test_steps):
    """Verifies that learner holdout strictly partitions learners between train and test without leakage."""
    engine = BKTEvaluationEngine()
    train_seqs, test_seqs = engine.split_learner_holdout(test_steps, test_ratio=0.5, random_seed=42)

    train_learners = {step.learner_id for seq in train_seqs for step in seq}
    test_learners = {step.learner_id for seq in test_seqs for step in seq}

    # Strict partition: No learner in both sets
    assert len(train_learners.intersection(test_learners)) == 0
    assert len(train_learners) + len(test_learners) == 4
    assert len(test_seqs) > 0


def test_temporal_holdout_splitting(test_steps):
    """Verifies that temporal holdout splits sequences chronologically preserving earlier steps for training."""
    engine = BKTEvaluationEngine()
    train_seqs, test_seqs = engine.split_temporal_holdout(test_steps, test_ratio=0.4, min_prefix_length=2)

    assert len(train_seqs) == len(test_steps)
    assert len(test_seqs) == len(test_steps)

    for tr, te in zip(train_seqs, test_seqs):
        # Earliest step in test must have higher step_index than latest step in train
        assert te[0].step_index > tr[-1].step_index


def test_one_step_ahead_prediction_and_metrics(test_steps):
    """Verifies sequential one-step-ahead prediction protocol and statistical metrics."""
    engine = BKTEvaluationEngine()
    params = BKTParameters(p_init=0.30, p_transit=0.15, p_guess=0.20, p_slip=0.10)

    # Evaluate on all sequences
    eval_result = engine.evaluate_model(params, test_sequences=test_steps, train_sequences=test_steps)

    assert eval_result["num_observations"] == 18
    assert eval_result["num_learners"] == 4
    assert 0.0 < eval_result["log_loss"] < 1.5
    assert 0.0 < eval_result["brier_score"] < 0.5
    assert 0.0 <= eval_result["accuracy"] <= 1.0
    assert eval_result["auc_roc"] is not None
    assert 0.0 <= eval_result["auc_roc"] <= 1.0

    # Calibration
    cal = eval_result["calibration_metrics"]
    assert "bins" in cal
    assert len(cal["bins"]) == 5
    assert 0.0 <= cal["ece"] <= 1.0

    # Baselines
    assert "global_rate_baseline" in eval_result["baseline_metrics"]
    assert "zero_transition_bkt_baseline" in eval_result["baseline_metrics"]


def test_auc_roc_single_class_protection():
    """Verifies that AUC-ROC gracefully returns None when held-out data has only one class."""
    engine = BKTEvaluationEngine()
    params = BKTParameters(p_init=0.5, p_transit=0.1, p_guess=0.2, p_slip=0.1)

    all_correct_seqs = [
        [ObservationStep("L1", "CA", "Q1", True, 1), ObservationStep("L1", "CA", "Q2", True, 2)],
        [ObservationStep("L2", "CA", "Q1", True, 1), ObservationStep("L2", "CA", "Q2", True, 2)],
    ]
    eval_result = engine.evaluate_model(params, test_sequences=all_correct_seqs)
    # AUC-ROC must be None, no crash
    assert eval_result["auc_roc"] is None


def test_readiness_gates():
    """Verifies acceptance criteria for model readiness qualification."""
    engine = BKTEvaluationEngine()

    # 1. Insufficient data (< 10 observations)
    sparse_seqs = [[ObservationStep("L1", "CA", "Q1", True, 1)]]
    params = BKTParameters(p_init=0.3, p_transit=0.15, p_guess=0.2, p_slip=0.1)
    res_sparse = engine.evaluate_model(params, test_sequences=sparse_seqs)
    assert res_sparse["readiness_status"] == "insufficient_data"

    # 2. Degenerate parameter values
    deg_params = BKTParameters(p_init=0.3, p_transit=0.15, p_guess=0.40, p_slip=0.40)
    # create valid sample >= 10
    big_seqs = [
        [ObservationStep(f"L{i}", "CA", f"Q{j}", (j % 2 == 0), j) for j in range(1, 4)]
        for i in range(5)
    ]
    res_deg = engine.evaluate_model(deg_params, test_sequences=big_seqs)
    assert res_deg["readiness_status"] in ["evaluation_failed", "requires_review", "evaluation_passed"]


def test_model_activation_gating_and_rollback_api(db_session: Session, test_client: TestClient, test_workspace: Workspace, auth_headers):
    """Verifies that activating a failed model is rejected unless forced, and rollback restores previous version."""
    ws = test_workspace

    # 2. Add an initial active model version
    v1 = BKTModelVersion(
        workspace_id=ws.id,
        model_version="bkt-test-v1",
        model_scope="global",
        p_init=0.30,
        p_transit=0.15,
        p_guess=0.20,
        p_slip=0.10,
        status="active",
        validation_metrics={},
    )
    # 3. Add a candidate model version
    v2 = BKTModelVersion(
        workspace_id=ws.id,
        model_version="bkt-test-v2",
        model_scope="global",
        p_init=0.35,
        p_transit=0.18,
        p_guess=0.22,
        p_slip=0.12,
        status="candidate",
        validation_metrics={},
    )
    db_session.add_all([v1, v2])
    db_session.commit()
    db_session.refresh(v1)
    db_session.refresh(v2)

    # 4. Record a failed evaluation run for v2
    failed_eval = BKTEvaluationRun(
        workspace_id=ws.id,
        model_version_id=v2.id,
        split_method="learner_holdout",
        status="completed",
        readiness_status="evaluation_failed",
        num_learners=5,
        num_sequences=10,
        num_observations=25,
        log_loss=0.88,
        brier_score=0.38,
        accuracy=0.55,
        calibration_metrics={},
        baseline_metrics={},
        parameter_stability={},
        readiness_notes="High predictive log loss",
    )
    db_session.add(failed_eval)
    db_session.commit()

    # 5. Attempt to activate v2 without force -> Should fail with 400
    res = test_client.post(
        f"/api/v1/workspaces/{ws.id}/bkt/models/{v2.id}/activate",
        json={"activate": True, "force": False},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "failed statistical evaluation gates" in res.json()["detail"]

    # 6. Activate v2 with force -> Should succeed
    res_forced = test_client.post(
        f"/api/v1/workspaces/{ws.id}/bkt/models/{v2.id}/activate",
        json={"activate": True, "force": True},
        headers=auth_headers,
    )
    assert res_forced.status_code == 200
    assert res_forced.json()["status"] == "active"

    # Verify v1 is now archived
    db_session.refresh(v1)
    assert v1.status == "archived"

    # 7. Test Rollback endpoint -> Reverts active to v1
    res_rb = test_client.post(
        f"/api/v1/workspaces/{ws.id}/bkt/models/rollback",
        json={"target_version_id": str(v1.id)},
        headers=auth_headers,
    )
    assert res_rb.status_code == 200
    assert res_rb.json()["id"] == str(v1.id)
    assert res_rb.json()["status"] == "active"

    db_session.refresh(v2)
    assert v2.status == "archived"
