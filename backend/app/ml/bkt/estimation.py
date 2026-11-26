"""BKT Parameter Estimation via Expectation-Maximization (Phase 9 C9.5).

Implements Baum-Welch EM algorithm for 2-state Hidden Markov Model standard BKT:
- State 0: Unmastered (cannot forget, i.e. A[1,0] = 0.0)
- State 1: Mastered
- Multi-restart initialization with deterministic random seeds
- Bounded parameter constraints (G, S < 0.5 to prevent degeneracy)
- Model evaluation metrics (Log-Likelihood, Brier Score, Prediction Accuracy)
- Fallback hierarchy (concept-specific -> global -> baseline)
"""

from dataclasses import asdict, dataclass
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from backend.app.ml.bkt.inference import BKTParameters, BayesianKnowledgeTracer


@dataclass
class BKTEstimationMetrics:
    """Evaluation metrics for a fitted BKT parameter set."""
    log_likelihood: float
    negative_log_likelihood: float
    brier_score: float
    accuracy: float
    num_sequences: int
    num_observations: int
    num_correct: int
    num_incorrect: int
    converged: bool
    iterations: int


@dataclass
class BKTEstimationResult:
    """Output of a BKT parameter estimation run."""
    parameters: BKTParameters
    metrics: BKTEstimationMetrics
    initial_parameters: BKTParameters
    all_restarts: List[Dict[str, Any]]
    is_statistically_supported: bool
    data_quality_notes: List[str]


class BKTParameterEstimator:
    """Baum-Welch Expectation-Maximization estimator for 4-parameter BKT."""

    MIN_BOUNDS = {"p_init": 0.01, "p_transit": 0.01, "p_guess": 0.01, "p_slip": 0.01}
    MAX_BOUNDS = {"p_init": 0.95, "p_transit": 0.60, "p_guess": 0.40, "p_slip": 0.35}

    def __init__(
        self,
        max_iter: int = 100,
        tol: float = 1e-5,
        n_restarts: int = 5,
        random_seed: int = 42,
    ):
        self.max_iter = max_iter
        self.tol = tol
        self.n_restarts = n_restarts
        self.random_seed = random_seed

    @classmethod
    def _clamp_params(cls, p_init: float, p_transit: float, p_guess: float, p_slip: float) -> Tuple[float, float, float, float]:
        """Clamps parameters within valid mathematical and non-degenerate bounds."""
        p_init = max(cls.MIN_BOUNDS["p_init"], min(cls.MAX_BOUNDS["p_init"], float(p_init)))
        p_transit = max(cls.MIN_BOUNDS["p_transit"], min(cls.MAX_BOUNDS["p_transit"], float(p_transit)))
        p_guess = max(cls.MIN_BOUNDS["p_guess"], min(cls.MAX_BOUNDS["p_guess"], float(p_guess)))
        p_slip = max(cls.MIN_BOUNDS["p_slip"], min(cls.MAX_BOUNDS["p_slip"], float(p_slip)))
        return p_init, p_transit, p_guess, p_slip

    def _build_hmm_matrices(
        self, p_init: float, p_transit: float, p_guess: float, p_slip: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Builds initial state distribution, transition matrix, and emission matrix.

        States:
        0: Unmastered
        1: Mastered

        Observations:
        0: Incorrect
        1: Correct
        """
        # Initial distribution: [P(not known), P(known)]
        pi = np.array([1.0 - p_init, p_init], dtype=np.float64)

        # Transition matrix: A[i, j] = P(state_t+1 = j | state_t = i)
        # Standard BKT assumes no forgetting: A[1, 0] = 0.0, A[1, 1] = 1.0
        A = np.array([
            [1.0 - p_transit, p_transit],
            [0.0, 1.0],
        ], dtype=np.float64)

        # Emission matrix: B[state, obs]
        # State 0 (unmastered): P(0|0) = 1 - G, P(1|0) = G
        # State 1 (mastered): P(0|1) = S, P(1|1) = 1 - S
        B = np.array([
            [1.0 - p_guess, p_guess],
            [p_slip, 1.0 - p_slip],
        ], dtype=np.float64)

        return pi, A, B

    def _forward(
        self, sequence: List[int], pi: np.ndarray, A: np.ndarray, B: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """Runs the forward algorithm with per-step scaling to prevent underflow."""
        T = len(sequence)
        alpha = np.zeros((T, 2), dtype=np.float64)
        c = np.zeros(T, dtype=np.float64)

        # t = 0
        obs_0 = sequence[0]
        alpha[0] = pi * B[:, obs_0]
        c[0] = np.sum(alpha[0])
        if c[0] <= 1e-15:
            c[0] = 1e-15
        alpha[0] /= c[0]

        # t = 1 .. T-1
        for t in range(1, T):
            obs_t = sequence[t]
            alpha[t] = np.dot(alpha[t - 1], A) * B[:, obs_t]
            c[t] = np.sum(alpha[t])
            if c[t] <= 1e-15:
                c[t] = 1e-15
            alpha[t] /= c[t]

        # Log likelihood of this sequence
        log_likelihood = float(np.sum(np.log(c)))
        return alpha, c, log_likelihood

    def _backward(
        self, sequence: List[int], c: np.ndarray, A: np.ndarray, B: np.ndarray
    ) -> np.ndarray:
        """Runs the backward algorithm using the scaling factors from the forward pass."""
        T = len(sequence)
        beta = np.zeros((T, 2), dtype=np.float64)

        # t = T - 1
        beta[T - 1] = 1.0

        # t = T - 2 .. 0
        for t in range(T - 2, -1, -1):
            obs_next = sequence[t + 1]
            beta[t] = np.dot(A, B[:, obs_next] * beta[t + 1])
            beta[t] /= c[t + 1]

        return beta

    def fit_single_restart(
        self,
        sequences: List[List[bool]],
        initial_params: BKTParameters,
    ) -> Tuple[BKTParameters, float, int, bool]:
        """Runs EM on an observation dataset starting from a single initial parameter set."""
        int_seqs = [[1 if obs else 0 for obs in seq] for seq in sequences if len(seq) > 0]
        if not int_seqs:
            return initial_params, -float("inf"), 0, False

        p_init, p_transit, p_guess, p_slip = self._clamp_params(
            initial_params.p_init,
            initial_params.p_transit,
            initial_params.p_guess,
            initial_params.p_slip,
        )

        prev_ll = -float("inf")
        converged = False
        iteration = 0

        for it in range(self.max_iter):
            iteration = it + 1
            pi, A, B = self._build_hmm_matrices(p_init, p_transit, p_guess, p_slip)

            total_ll = 0.0

            # Sufficient statistics accumulators
            exp_init_mastered = 0.0
            num_seqs = len(int_seqs)

            sum_transit_0_to_1 = 0.0
            sum_stay_in_0 = 0.0

            sum_gamma_0_obs1 = 0.0  # Guess numerator
            sum_gamma_0_all = 0.0   # Guess denominator

            sum_gamma_1_obs0 = 0.0  # Slip numerator
            sum_gamma_1_all = 0.0   # Slip denominator

            for seq in int_seqs:
                T_k = len(seq)
                alpha, c, seq_ll = self._forward(seq, pi, A, B)
                beta = self._backward(seq, c, A, B)
                total_ll += seq_ll

                # Gamma: state occupancy probability at time t
                gamma = alpha * beta
                gamma_sum = np.sum(gamma, axis=1, keepdims=True)
                gamma_sum[gamma_sum <= 1e-15] = 1e-15
                gamma /= gamma_sum

                # P(L_0) statistic
                exp_init_mastered += gamma[0, 1]

                # Transition statistics (for t = 0 .. T-2)
                for t in range(T_k - 1):
                    obs_next = seq[t + 1]
                    xi_t = np.outer(alpha[t], B[:, obs_next] * beta[t + 1]) * A
                    xi_sum = np.sum(xi_t)
                    if xi_sum > 1e-15:
                        xi_t /= xi_sum
                    sum_transit_0_to_1 += xi_t[0, 1]
                    sum_stay_in_0 += xi_t[0, 0]

                # Emission statistics
                for t in range(T_k):
                    obs_t = seq[t]
                    sum_gamma_0_all += gamma[t, 0]
                    sum_gamma_1_all += gamma[t, 1]
                    if obs_t == 1:
                        sum_gamma_0_obs1 += gamma[t, 0]
                    else:
                        sum_gamma_1_obs0 += gamma[t, 1]

            # M-step: Parameter updates
            new_p_init = exp_init_mastered / max(1.0, float(num_seqs))
            denom_transit = sum_stay_in_0 + sum_transit_0_to_1
            new_p_transit = (sum_transit_0_to_1 / denom_transit) if denom_transit > 1e-9 else p_transit
            new_p_guess = (sum_gamma_0_obs1 / sum_gamma_0_all) if sum_gamma_0_all > 1e-9 else p_guess
            new_p_slip = (sum_gamma_1_obs0 / sum_gamma_1_all) if sum_gamma_1_all > 1e-9 else p_slip

            # Clamp parameters
            p_init, p_transit, p_guess, p_slip = self._clamp_params(
                new_p_init, new_p_transit, new_p_guess, new_p_slip
            )

            # Convergence check
            if abs(total_ll - prev_ll) < self.tol:
                converged = True
                break
            prev_ll = total_ll

        fitted = BKTParameters(
            p_init=p_init,
            p_transit=p_transit,
            p_guess=p_guess,
            p_slip=p_slip,
            version=f"fitted_{initial_params.version}",
        )
        return fitted, total_ll, iteration, converged

    def fit(
        self,
        sequences: List[List[bool]],
        model_version: str = "bkt_fitted_model",
    ) -> BKTEstimationResult:
        """Fits BKT parameters across multiple restarts and selects the fit with maximum log-likelihood."""
        valid_seqs = [s for s in sequences if len(s) > 0]
        num_obs = sum(len(s) for s in valid_seqs)
        num_correct = sum(sum(1 for x in s if x) for s in valid_seqs)
        num_incorrect = num_obs - num_correct

        quality_notes: List[str] = []
        is_statistically_supported = True

        if len(valid_seqs) < 5:
            quality_notes.append("Small sample size: fewer than 5 eligible sequences.")
            is_statistically_supported = False
        if num_obs < 25:
            quality_notes.append("Sparse data: fewer than 25 total evaluated observations.")
            is_statistically_supported = False

        rng = np.random.RandomState(self.random_seed)

        # Baseline starting candidate
        initial_candidates = [
            BKTParameters(0.30, 0.15, 0.20, 0.10, version="restart_baseline"),
            BKTParameters(0.20, 0.10, 0.25, 0.15, version="restart_low_prior"),
            BKTParameters(0.50, 0.20, 0.15, 0.08, version="restart_high_prior"),
        ]

        # Add additional random restarts
        while len(initial_candidates) < max(self.n_restarts, 3):
            cand_p_init = float(rng.uniform(0.1, 0.6))
            cand_p_transit = float(rng.uniform(0.05, 0.35))
            cand_p_guess = float(rng.uniform(0.05, 0.30))
            cand_p_slip = float(rng.uniform(0.05, 0.25))
            initial_candidates.append(
                BKTParameters(
                    p_init=cand_p_init,
                    p_transit=cand_p_transit,
                    p_guess=cand_p_guess,
                    p_slip=cand_p_slip,
                    version=f"restart_rand_{len(initial_candidates)}",
                )
            )

        best_params: Optional[BKTParameters] = None
        best_ll = -float("inf")
        best_iter = 0
        best_converged = False
        best_initial = initial_candidates[0]
        restart_records: List[Dict[str, Any]] = []

        for candidate in initial_candidates:
            fitted, ll, iters, converged = self.fit_single_restart(valid_seqs, candidate)
            safe_ll = 0.0 if (math.isinf(ll) or math.isnan(ll)) else round(ll, 4)
            restart_records.append({
                "initial": asdict(candidate),
                "fitted": asdict(fitted),
                "log_likelihood": safe_ll,
                "iterations": iters,
                "converged": converged,
            })
            if ll > best_ll or best_params is None:
                best_ll = ll
                best_params = fitted
                best_iter = iters
                best_converged = converged
                best_initial = candidate

        final_params = BKTParameters(
            p_init=best_params.p_init,
            p_transit=best_params.p_transit,
            p_guess=best_params.p_guess,
            p_slip=best_params.p_slip,
            version=model_version,
        )

        # Compute Brier score and accuracy on fitted model
        brier_score, accuracy = self.evaluate_sequences(valid_seqs, final_params)

        finite_ll = 0.0 if (math.isinf(best_ll) or math.isnan(best_ll)) else round(best_ll, 4)
        finite_nll = 0.0 if (math.isinf(best_ll) or math.isnan(best_ll)) else round(-best_ll, 4)

        metrics = BKTEstimationMetrics(
            log_likelihood=finite_ll,
            negative_log_likelihood=finite_nll,
            brier_score=round(brier_score, 4),
            accuracy=round(accuracy, 4),
            num_sequences=len(valid_seqs),
            num_observations=num_obs,
            num_correct=num_correct,
            num_incorrect=num_incorrect,
            converged=best_converged,
            iterations=best_iter,
        )

        return BKTEstimationResult(
            parameters=final_params,
            metrics=metrics,
            initial_parameters=best_initial,
            all_restarts=restart_records,
            is_statistically_supported=is_statistically_supported,
            data_quality_notes=quality_notes,
        )

    @classmethod
    def evaluate_sequences(
        cls, sequences: List[List[bool]], params: BKTParameters
    ) -> Tuple[float, float]:
        """Calculates one-step-ahead Brier score and accuracy across sequences."""
        squared_errors: List[float] = []
        correct_predictions: int = 0
        total_evaluations: int = 0

        tracer = BayesianKnowledgeTracer(params)

        for seq in sequences:
            mastery = params.p_init
            for obs in seq:
                # One-step-ahead prediction: P(C_t) = L_t * (1 - S) + (1 - L_t) * G
                p_c = tracer.probability_correct(mastery, params)
                obs_val = 1.0 if obs else 0.0

                squared_errors.append((obs_val - p_c) ** 2)
                pred_binary = p_c >= 0.5
                if pred_binary == obs:
                    correct_predictions += 1
                total_evaluations += 1

                # Update mastery to next state
                step_res = tracer.update_mastery(mastery, obs, params)
                mastery = step_res.predicted_next_mastery

        if total_evaluations == 0:
            return 0.0, 0.0

        brier = float(np.mean(squared_errors))
        acc = float(correct_predictions / total_evaluations)
        return brier, acc
