"""Bayesian Knowledge Tracing (BKT) Mathematical Engine (Phase 9 C9.4).

Framework-independent probabilistic inference for standard 4-parameter BKT:
- Initial mastery: P(L_0)
- Learning transition: P(T)
- Guess: P(G)
- Slip: P(S)

Strictly separates prior mastery, observation posterior, and post-transition predicted mastery.
"""

from dataclasses import dataclass
import math
from typing import List, Optional, Tuple, Union


@dataclass(frozen=True)
class BKTParameters:
    """Four-parameter BKT parameter set."""
    p_init: float  # P(L_0)
    p_transit: float  # P(T)
    p_guess: float  # P(G)
    p_slip: float  # P(S)
    version: str = "default_baseline_v1"

    def validate(self) -> None:
        """Validates that parameters satisfy standard BKT probabilistic constraints."""
        for name, val in [
            ("p_init", self.p_init),
            ("p_transit", self.p_transit),
            ("p_guess", self.p_guess),
            ("p_slip", self.p_slip),
        ]:
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                raise ValueError(f"BKT parameter '{name}' must be a finite number, got {val}")
            if val < 0.0 or val > 1.0:
                raise ValueError(f"BKT parameter '{name}' must be in [0.0, 1.0], got {val}")

        # Guess and slip should be less than 0.5 to avoid degenerate negative correlation with mastery
        if self.p_guess >= 0.5:
            raise ValueError(f"Guess parameter p_guess ({self.p_guess}) should be < 0.5 in standard BKT")
        if self.p_slip >= 0.5:
            raise ValueError(f"Slip parameter p_slip ({self.p_slip}) should be < 0.5 in standard BKT")


# Default defensible baseline parameters
DEFAULT_BKT_PARAMETERS = BKTParameters(
    p_init=0.30,
    p_transit=0.15,
    p_guess=0.20,
    p_slip=0.10,
    version="knovera_baseline_v1",
)


@dataclass(frozen=True)
class BKTUpdateResult:
    """Detailed output of a BKT Bayesian observation update."""
    prior_mastery: float
    observation: bool
    prob_observation: float
    posterior_mastery: float
    predicted_next_mastery: float
    parameters: BKTParameters
    is_valid: bool = True
    error_message: Optional[str] = None


class BayesianKnowledgeTracer:
    """Standard 4-parameter Bayesian Knowledge Tracing inference engine."""

    EPSILON = 1e-12

    def __init__(self, parameters: Optional[BKTParameters] = None):
        if parameters is not None:
            parameters.validate()
            self.params = parameters
        else:
            self.params = DEFAULT_BKT_PARAMETERS

    @classmethod
    def probability_correct(cls, mastery: float, params: BKTParameters) -> float:
        """P(C_t) = L_t * (1 - S) + (1 - L_t) * G"""
        p_c = mastery * (1.0 - params.p_slip) + (1.0 - mastery) * params.p_guess
        return max(cls.EPSILON, min(1.0 - cls.EPSILON, p_c))

    @classmethod
    def probability_incorrect(cls, mastery: float, params: BKTParameters) -> float:
        """P(I_t) = L_t * S + (1 - L_t) * (1 - G)"""
        p_i = mastery * params.p_slip + (1.0 - mastery) * (1.0 - params.p_guess)
        return max(cls.EPSILON, min(1.0 - cls.EPSILON, p_i))

    @classmethod
    def posterior_correct(cls, prior_mastery: float, params: BKTParameters) -> float:
        """Calculates posterior mastery after a correct observation:

        P(L_t | C_t) = [L_t * (1 - S)] / [L_t * (1 - S) + (1 - L_t) * G]
        """
        numerator = prior_mastery * (1.0 - params.p_slip)
        denominator = numerator + (1.0 - prior_mastery) * params.p_guess
        if denominator <= cls.EPSILON:
            return 1.0 if numerator > 0 else 0.0
        post = numerator / denominator
        return max(0.0, min(1.0, post))

    @classmethod
    def posterior_incorrect(cls, prior_mastery: float, params: BKTParameters) -> float:
        """Calculates posterior mastery after an incorrect observation:

        P(L_t | I_t) = [L_t * S] / [L_t * S + (1 - L_t) * (1 - G)]
        """
        numerator = prior_mastery * params.p_slip
        denominator = numerator + (1.0 - prior_mastery) * (1.0 - params.p_guess)
        if denominator <= cls.EPSILON:
            return 0.0
        post = numerator / denominator
        return max(0.0, min(1.0, post))

    @classmethod
    def apply_learning_transition(cls, posterior_mastery: float, params: BKTParameters) -> float:
        """Calculates predicted mastery before next opportunity after learning transition:

        P(L_{t+1}) = P(L_t | O_t) + [1 - P(L_t | O_t)] * T
        """
        next_m = posterior_mastery + (1.0 - posterior_mastery) * params.p_transit
        return max(0.0, min(1.0, next_m))

    def update_mastery(
        self,
        current_mastery: float,
        observation: bool,
        custom_params: Optional[BKTParameters] = None,
    ) -> BKTUpdateResult:
        """Executes a single Bayesian Knowledge Tracing update step.

        Parameters:
        - current_mastery: Probability of mastery before the current opportunity.
        - observation: True if correct, False if incorrect.
        - custom_params: Optional override for concept-specific parameters.

        Returns:
        - BKTUpdateResult with prior, posterior, predicted next mastery, and observation likelihood.
        """
        params = custom_params or self.params
        params.validate()

        if not isinstance(current_mastery, (int, float)) or math.isnan(current_mastery) or math.isinf(current_mastery):
            raise ValueError(f"current_mastery must be a finite float, got {current_mastery}")

        prior = max(0.0, min(1.0, float(current_mastery)))

        if observation:
            p_obs = self.probability_correct(prior, params)
            posterior = self.posterior_correct(prior, params)
        else:
            p_obs = self.probability_incorrect(prior, params)
            posterior = self.posterior_incorrect(prior, params)

        predicted_next = self.apply_learning_transition(posterior, params)

        return BKTUpdateResult(
            prior_mastery=prior,
            observation=observation,
            prob_observation=p_obs,
            posterior_mastery=posterior,
            predicted_next_mastery=predicted_next,
            parameters=params,
            is_valid=True,
        )

    def replay_sequence(
        self,
        observations: List[bool],
        initial_mastery: Optional[float] = None,
        custom_params: Optional[BKTParameters] = None,
    ) -> List[BKTUpdateResult]:
        """Replays an ordered sequence of binary observations from initial state."""
        params = custom_params or self.params
        params.validate()

        current_mastery = (
            initial_mastery if initial_mastery is not None else params.p_init
        )

        results: List[BKTUpdateResult] = []
        for obs in observations:
            step_result = self.update_mastery(
                current_mastery=current_mastery,
                observation=obs,
                custom_params=params,
            )
            results.append(step_result)
            current_mastery = step_result.predicted_next_mastery

        return results
