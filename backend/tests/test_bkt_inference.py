"""Tests for Bayesian Knowledge Tracing Mathematical Engine (Phase 9 C9.4).

Verifies:
- Standard 4-parameter BKT formulation
- Exact numerical benchmarks from prompt specification
- Posterior calculation on correct & incorrect observations
- Learning transition calculation
- Parameter boundary validation & error handling
- Monotonicity across sequential observations
- Sequence replay functionality
"""

import math
import pytest

from backend.app.ml.bkt.inference import (
    DEFAULT_BKT_PARAMETERS,
    BKTParameters,
    BayesianKnowledgeTracer,
)


def test_reference_numerical_benchmarks():
    """Verifies the exact numerical values from the Phase 9 C9.4 specification:

    P(L_0) = 0.30, P(G) = 0.20, P(S) = 0.10, P(T) = 0.15.
    """
    params = BKTParameters(
        p_init=0.30,
        p_guess=0.20,
        p_slip=0.10,
        p_transit=0.15,
        version="benchmark_test",
    )
    tracer = BayesianKnowledgeTracer(params)

    # 1. Correct observation
    # P(L | C) = (0.30 * 0.90) / (0.30 * 0.90 + 0.70 * 0.20) = 0.27 / 0.41 ~ 0.6585366
    # P(L_next) = 0.6585366 + (1 - 0.6585366) * 0.15 ~ 0.7097561
    res_c = tracer.update_mastery(current_mastery=0.30, observation=True)
    assert pytest.approx(res_c.prior_mastery, abs=1e-6) == 0.30
    assert pytest.approx(res_c.posterior_mastery, abs=1e-5) == 0.6585366
    assert pytest.approx(res_c.predicted_next_mastery, abs=1e-5) == 0.7097561

    # 2. Incorrect observation
    # P(L | I) = (0.30 * 0.10) / (0.30 * 0.10 + 0.70 * 0.80) = 0.03 / 0.59 ~ 0.0508475
    # P(L_next) = 0.0508475 + (1 - 0.0508475) * 0.15 ~ 0.1932203
    res_i = tracer.update_mastery(current_mastery=0.30, observation=False)
    assert pytest.approx(res_i.prior_mastery, abs=1e-6) == 0.30
    assert pytest.approx(res_i.posterior_mastery, abs=1e-5) == 0.0508475
    assert pytest.approx(res_i.predicted_next_mastery, abs=1e-5) == 0.1932203


def test_distinct_prior_posterior_and_predicted_next():
    """Ensures prior, posterior, and predicted_next are never conflated into a single value."""
    tracer = BayesianKnowledgeTracer()
    res = tracer.update_mastery(current_mastery=0.40, observation=True)

    assert res.prior_mastery != res.posterior_mastery
    assert res.posterior_mastery != res.predicted_next_mastery
    assert res.predicted_next_mastery > res.posterior_mastery > res.prior_mastery


def test_parameter_validation_constraints():
    """Ensures improper parameters are rejected before inference."""
    # Guess >= 0.5
    with pytest.raises(ValueError, match="Guess parameter"):
        BKTParameters(p_init=0.3, p_transit=0.1, p_guess=0.5, p_slip=0.1).validate()

    # Slip >= 0.5
    with pytest.raises(ValueError, match="Slip parameter"):
        BKTParameters(p_init=0.3, p_transit=0.1, p_guess=0.2, p_slip=0.55).validate()

    # Negative value
    with pytest.raises(ValueError, match="must be in"):
        BKTParameters(p_init=-0.1, p_transit=0.1, p_guess=0.2, p_slip=0.1).validate()

    # Value > 1.0
    with pytest.raises(ValueError, match="must be in"):
        BKTParameters(p_init=0.3, p_transit=1.2, p_guess=0.2, p_slip=0.1).validate()

    # NaN / Inf
    with pytest.raises(ValueError, match="must be a finite number"):
        BKTParameters(p_init=float("nan"), p_transit=0.1, p_guess=0.2, p_slip=0.1).validate()


def test_extreme_prior_boundary_cases():
    """Tests extreme prior mastery at 0.0 and 1.0."""
    tracer = BayesianKnowledgeTracer(DEFAULT_BKT_PARAMETERS)

    # Prior 0.0 with correct answer (can happen via guessing)
    res_zero_c = tracer.update_mastery(current_mastery=0.0, observation=True)
    assert res_zero_c.posterior_mastery == 0.0
    # Next mastery increases purely through transition: 0.0 + (1 - 0) * T = T
    assert pytest.approx(res_zero_c.predicted_next_mastery, abs=1e-6) == DEFAULT_BKT_PARAMETERS.p_transit

    # Prior 1.0 with incorrect answer (can happen via slipping)
    res_one_i = tracer.update_mastery(current_mastery=1.0, observation=False)
    # P(L|I) = (1.0 * S) / (1.0 * S + 0 * (1-G)) = 1.0
    assert pytest.approx(res_one_i.posterior_mastery, abs=1e-6) == 1.0
    assert pytest.approx(res_one_i.predicted_next_mastery, abs=1e-6) == 1.0


def test_monotonicity_of_repeated_observations():
    """Consecutive correct answers strictly increase mastery; consecutive incorrect answers decrease posterior."""
    tracer = BayesianKnowledgeTracer()

    # 4 consecutive correct answers
    correct_results = tracer.replay_sequence([True, True, True, True], initial_mastery=0.20)
    for i in range(len(correct_results) - 1):
        assert correct_results[i + 1].predicted_next_mastery > correct_results[i].predicted_next_mastery

    assert correct_results[-1].predicted_next_mastery > 0.85

    # 4 consecutive incorrect answers
    incorrect_results = tracer.replay_sequence([False, False, False, False], initial_mastery=0.80)
    for i in range(len(incorrect_results) - 1):
        assert incorrect_results[i + 1].posterior_mastery < incorrect_results[i].posterior_mastery


def test_observation_probabilities():
    """Probability of correct and incorrect sum to 1.0 under standard model."""
    params = DEFAULT_BKT_PARAMETERS
    for m in [0.0, 0.25, 0.5, 0.75, 1.0]:
        p_c = BayesianKnowledgeTracer.probability_correct(m, params)
        p_i = BayesianKnowledgeTracer.probability_incorrect(m, params)
        assert pytest.approx(p_c + p_i, abs=1e-9) == 1.0
