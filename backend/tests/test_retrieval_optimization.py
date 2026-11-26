"""Unit tests for retrieval optimization experiment runner and Pareto analysis (Phase 4 C4.8)."""

import pytest

from backend.app.core.config import get_settings
from backend.scripts.optimize_retrieval import (
    compute_pareto_frontier,
    generate_configuration_space,
    select_best_configuration,
)


def test_generate_configuration_space_bounds_and_determinism():
    configs1 = generate_configuration_space(max_configurations=10, seed=42)
    configs2 = generate_configuration_space(max_configurations=10, seed=42)

    assert len(configs1) == 10
    # Determinism: same seed produces identical configurations
    assert configs1 == configs2

    # Baseline is always config index 0
    assert configs1[0]["name"] == "config_00_baseline"
    assert configs1[0]["dense_top_k"] == 20
    assert configs1[0]["bm25_top_k"] == 20
    assert configs1[0]["bm25_k1"] == 1.5
    assert configs1[0]["bm25_b"] == 0.75
    assert configs1[0]["rrf_k"] == 60


def test_compute_pareto_frontier_identifies_non_dominated():
    # Setup candidate runs:
    # Run A: High quality (nDCG=0.95, Recall=0.90), high latency (p95=50ms)
    # Run B: Medium quality (nDCG=0.92, Recall=0.88), very low latency (p95=15ms)
    # Run C: Dominated by A (nDCG=0.90, Recall=0.85, p95=60ms) -> should be excluded from Pareto
    # Run D: Rejected due to regression -> should be excluded
    run_a = {
        "config": {"name": "run_a"},
        "metrics": {"ndcg@10": 0.95, "recall@10": 0.90, "mrr@10": 1.0},
        "p95_latency_ms": 50.0,
        "status": "accepted",
    }
    run_b = {
        "config": {"name": "run_b"},
        "metrics": {"ndcg@10": 0.92, "recall@10": 0.88, "mrr@10": 1.0},
        "p95_latency_ms": 15.0,
        "status": "accepted",
    }
    run_c = {
        "config": {"name": "run_c"},
        "metrics": {"ndcg@10": 0.90, "recall@10": 0.85, "mrr@10": 0.8},
        "p95_latency_ms": 60.0,
        "status": "accepted",
    }
    run_d = {
        "config": {"name": "run_d"},
        "metrics": {"ndcg@10": 0.99, "recall@10": 0.99, "mrr@10": 1.0},
        "p95_latency_ms": 10.0,
        "status": "rejected",
    }

    pareto = compute_pareto_frontier([run_a, run_b, run_c, run_d])
    pareto_names = [r["config"]["name"] for r in pareto]

    assert "run_a" in pareto_names
    assert "run_b" in pareto_names
    # Dominated and rejected runs must not be in Pareto frontier
    assert "run_c" not in pareto_names
    assert "run_d" not in pareto_names


def test_select_best_configuration_strategy():
    run_high_qual = {
        "config": {"name": "high_qual"},
        "metrics": {"ndcg@10": 0.95, "recall@10": 0.95, "mrr@10": 1.0},
        "p95_latency_ms": 25.0,
        "status": "accepted",
    }
    run_low_qual = {
        "config": {"name": "low_qual"},
        "metrics": {"ndcg@10": 0.90, "recall@10": 0.90, "mrr@10": 0.9},
        "p95_latency_ms": 15.0,
        "status": "accepted",
    }

    winner, reason = select_best_configuration([run_high_qual, run_low_qual], baseline_run=run_low_qual)
    assert winner["config"]["name"] == "high_qual"
    assert "Selected 'high_qual' on Pareto frontier" in reason


def test_production_configuration_not_mutated():
    settings_before = get_settings()
    original_k1 = settings_before.BM25_K1
    original_b = settings_before.BM25_B
    original_dense_k = settings_before.DENSE_RETRIEVAL_TOP_K

    # Running configuration space generation or selection does NOT alter active settings
    _ = generate_configuration_space(max_configurations=5, seed=123)

    settings_after = get_settings()
    assert settings_after.BM25_K1 == original_k1
    assert settings_after.BM25_B == original_b
    assert settings_after.DENSE_RETRIEVAL_TOP_K == original_dense_k
