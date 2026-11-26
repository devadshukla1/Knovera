"""Offline Evaluation Framework for Bayesian Knowledge Tracing (Phase 9 C9.9).

Implements:
- Leakage-free dataset splitting (learner holdout & temporal holdout)
- Sequential one-step-ahead response prediction protocol
- Multi-metric evaluation (Log Loss, Brier Score, Accuracy, AUC-ROC)
- Calibration binning & Expected Calibration Error (ECE)
- Multi-baseline benchmarking (global rate, concept rate, zero-transition baseline)
- Model readiness qualification gates
"""

from collections import defaultdict
import math
import random
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from backend.app.core.logging import get_logger
from backend.app.ml.bkt.inference import BKTParameters, BayesianKnowledgeTracer

logger = get_logger("knovera.ml.bkt.evaluation")


class ObservationStep:
    """A single ordered correctness observation in a learner sequence."""

    def __init__(
        self,
        learner_id: str,
        concept_id: str,
        question_id: str,
        is_correct: bool,
        step_index: int,
        timestamp: Optional[str] = None,
    ):
        self.learner_id = learner_id
        self.concept_id = concept_id
        self.question_id = question_id
        self.is_correct = is_correct
        self.step_index = step_index
        self.timestamp = timestamp


class BKTEvaluationDataset:
    """Container of learner sequences structured for offline evaluation."""

    def __init__(self, sequences: List[List[ObservationStep]]):
        self.sequences = sequences

    @property
    def total_observations(self) -> int:
        return sum(len(seq) for seq in self.sequences)

    @property
    def total_learners(self) -> int:
        return len({step.learner_id for seq in self.sequences for step in seq})

    @property
    def total_concepts(self) -> int:
        return len({step.concept_id for seq in self.sequences for step in seq})


class BKTEvaluationEngine:
    """Evaluates predictive accuracy and calibration of BKT models."""

    def __init__(self, eps: float = 1e-6):
        self.eps = eps

    def split_learner_holdout(
        self,
        sequences: List[List[ObservationStep]],
        test_ratio: float = 0.25,
        random_seed: int = 42,
    ) -> Tuple[List[List[ObservationStep]], List[List[ObservationStep]]]:
        """Splits data by distinct learners to test cross-learner generalization without data leakage."""
        learners = sorted(list({step.learner_id for seq in sequences for step in seq}))
        if len(learners) <= 1:
            # Fallback for single learner: temporal split of sequences
            return self.split_temporal_holdout(sequences, test_ratio=test_ratio)

        rng = random.Random(random_seed)
        shuffled = list(learners)
        rng.shuffle(shuffled)

        n_test = max(1, int(round(len(shuffled) * test_ratio)))
        test_learners = set(shuffled[:n_test])
        train_learners = set(shuffled[n_test:])

        train_seqs = [seq for seq in sequences if seq and seq[0].learner_id in train_learners]
        test_seqs = [seq for seq in sequences if seq and seq[0].learner_id in test_learners]

        return train_seqs, test_seqs

    def split_temporal_holdout(
        self,
        sequences: List[List[ObservationStep]],
        test_ratio: float = 0.30,
        min_prefix_length: int = 2,
    ) -> Tuple[List[List[ObservationStep]], List[List[ObservationStep]]]:
        """Splits each sequence chronologically: earlier steps for training, later for evaluation."""
        train_seqs: List[List[ObservationStep]] = []
        test_seqs: List[List[ObservationStep]] = []

        for seq in sequences:
            if len(seq) <= min_prefix_length:
                train_seqs.append(seq)
                continue

            n_train = max(min_prefix_length, int(round(len(seq) * (1.0 - test_ratio))))
            if n_train >= len(seq):
                n_train = len(seq) - 1

            train_seqs.append(seq[:n_train])
            test_seqs.append(seq[n_train:])

        return train_seqs, test_seqs

    def evaluate_model(
        self,
        params: BKTParameters,
        test_sequences: List[List[ObservationStep]],
        train_sequences: Optional[List[List[ObservationStep]]] = None,
    ) -> Dict[str, Any]:
        """Executes sequential one-step-ahead prediction protocol on held-out sequences."""
        if not test_sequences or sum(len(s) for s in test_sequences) == 0:
            return {
                "num_learners": 0,
                "num_sequences": 0,
                "num_observations": 0,
                "log_loss": 0.0,
                "brier_score": 0.0,
                "accuracy": 0.0,
                "auc_roc": None,
                "calibration_metrics": {"bins": [], "ece": 0.0},
                "baseline_metrics": {},
                "parameter_stability": self._check_parameter_stability(params),
                "readiness_status": "insufficient_data",
                "readiness_notes": "No test observation sequences available for evaluation.",
            }

        tracer = BayesianKnowledgeTracer(params)
        predictions: List[float] = []
        actuals: List[int] = []

        # Run sequential one-step-ahead prediction
        for seq in test_sequences:
            current_mastery = params.p_init
            for step in seq:
                # 1. Predict correctness before revealing outcome
                p_correct = tracer.probability_correct(current_mastery, params)
                predictions.append(p_correct)
                actuals.append(1 if step.is_correct else 0)

                # 2. Update latent mastery state after recording prediction
                update_result = tracer.update_mastery(current_mastery, step.is_correct)
                current_mastery = update_result.predicted_next_mastery

        # Compute Core Predictive Metrics
        log_loss = self._compute_log_loss(predictions, actuals)
        brier = self._compute_brier_score(predictions, actuals)
        accuracy = self._compute_accuracy(predictions, actuals, threshold=0.5)
        auc_roc = self._compute_auc_roc(predictions, actuals)
        calibration = self._compute_calibration(predictions, actuals, n_bins=5)

        # Baseline comparisons
        baselines = self._compute_baselines(actuals, train_sequences, test_sequences, params)

        # Parameter stability check
        stability = self._check_parameter_stability(params)

        # Determine readiness gate qualification
        readiness_status, readiness_notes = self._evaluate_readiness_gates(
            total_observations=len(actuals),
            log_loss=log_loss,
            brier_score=brier,
            stability=stability,
            baselines=baselines,
        )

        num_learners = len({step.learner_id for seq in test_sequences for step in seq})

        return {
            "num_learners": num_learners,
            "num_sequences": len(test_sequences),
            "num_observations": len(actuals),
            "log_loss": round(log_loss, 6),
            "brier_score": round(brier, 6),
            "accuracy": round(accuracy, 4),
            "auc_roc": round(auc_roc, 4) if auc_roc is not None else None,
            "calibration_metrics": calibration,
            "baseline_metrics": baselines,
            "parameter_stability": stability,
            "readiness_status": readiness_status,
            "readiness_notes": readiness_notes,
        }

    # -------------------------------------------------------------------------
    # Metric Calculations
    # -------------------------------------------------------------------------

    def _compute_log_loss(self, preds: List[float], actuals: List[int]) -> float:
        total_loss = 0.0
        for p, y in zip(preds, actuals):
            p_clipped = max(self.eps, min(1.0 - self.eps, p))
            if y == 1:
                total_loss -= math.log(p_clipped)
            else:
                total_loss -= math.log(1.0 - p_clipped)
        return total_loss / len(actuals) if actuals else 0.0

    def _compute_brier_score(self, preds: List[float], actuals: List[int]) -> float:
        total_sq_err = sum((p - y) ** 2 for p, y in zip(preds, actuals))
        return total_sq_err / len(actuals) if actuals else 0.0

    def _compute_accuracy(self, preds: List[float], actuals: List[int], threshold: float = 0.5) -> float:
        correct_predictions = sum(1 for p, y in zip(preds, actuals) if (p >= threshold) == (y == 1))
        return correct_predictions / len(actuals) if actuals else 0.0

    def _compute_auc_roc(self, preds: List[float], actuals: List[int]) -> Optional[float]:
        """Mann-Whitney U statistic calculation for AUC-ROC."""
        positives = [p for p, y in zip(preds, actuals) if y == 1]
        negatives = [p for p, y in zip(preds, actuals) if y == 0]

        if not positives or not negatives:
            # Undefined when only one class is present
            return None

        n_pos = len(positives)
        n_neg = len(negatives)

        # Pairwise comparison
        u_stat = 0.0
        for pos in positives:
            for neg in negatives:
                if pos > neg:
                    u_stat += 1.0
                elif pos == neg:
                    u_stat += 0.5

        return u_stat / (n_pos * n_neg)

    def _compute_calibration(
        self,
        preds: List[float],
        actuals: List[int],
        n_bins: int = 5,
    ) -> Dict[str, Any]:
        """Evaluates reliability calibration across probability bins and Expected Calibration Error (ECE)."""
        bin_width = 1.0 / n_bins
        bins_data: List[Dict[str, Any]] = []
        total_samples = len(actuals)
        total_ece = 0.0

        for i in range(n_bins):
            lower = i * bin_width
            upper = (i + 1) * bin_width
            is_last = (i == n_bins - 1)

            bin_preds: List[float] = []
            bin_actuals: List[int] = []

            for p, y in zip(preds, actuals):
                if (lower <= p < upper) or (is_last and lower <= p <= upper):
                    bin_preds.append(p)
                    bin_actuals.append(y)

            count = len(bin_preds)
            if count > 0:
                pred_mean = sum(bin_preds) / count
                obs_mean = sum(bin_actuals) / count
                bin_err = abs(obs_mean - pred_mean)
                total_ece += (count / total_samples) * bin_err
            else:
                pred_mean = (lower + upper) / 2.0
                obs_mean = 0.0

            bins_data.append({
                "bin_index": i,
                "bin_range": f"{lower:.1f}-{upper:.1f}",
                "sample_count": count,
                "predicted_mean": round(pred_mean, 4),
                "observed_mean": round(obs_mean, 4),
            })

        return {
            "bins": bins_data,
            "ece": round(total_ece, 4),
        }

    def _compute_baselines(
        self,
        actuals: List[int],
        train_sequences: Optional[List[List[ObservationStep]]],
        test_sequences: List[List[ObservationStep]],
        params: BKTParameters,
    ) -> Dict[str, Any]:
        """Calculates performance of competitive baselines on the same held-out observations."""
        # 1. Global training correct rate baseline
        if train_sequences and sum(len(s) for s in train_sequences) > 0:
            train_actuals = [1 if step.is_correct else 0 for seq in train_sequences for step in seq]
            global_rate = sum(train_actuals) / len(train_actuals)
        else:
            global_rate = 0.50

        global_preds = [global_rate] * len(actuals)
        global_log_loss = self._compute_log_loss(global_preds, actuals)
        global_brier = self._compute_brier_score(global_preds, actuals)

        # 2. Prior-only BKT baseline (no learning transition: T = 0.0)
        zero_transit_params = BKTParameters(
            p_init=params.p_init,
            p_transit=0.0001,
            p_guess=params.p_guess,
            p_slip=params.p_slip,
        )
        zt_tracer = BayesianKnowledgeTracer(zero_transit_params)
        zt_preds: List[float] = []
        for seq in test_sequences:
            m = zero_transit_params.p_init
            for step in seq:
                zt_preds.append(zt_tracer.probability_correct(m, zero_transit_params))
                res = zt_tracer.update_mastery(m, step.is_correct)
                m = res.predicted_next_mastery

        zt_log_loss = self._compute_log_loss(zt_preds, actuals)
        zt_brier = self._compute_brier_score(zt_preds, actuals)

        return {
            "global_rate_baseline": {
                "predicted_probability": round(global_rate, 4),
                "log_loss": round(global_log_loss, 6),
                "brier_score": round(global_brier, 6),
            },
            "zero_transition_bkt_baseline": {
                "log_loss": round(zt_log_loss, 6),
                "brier_score": round(zt_brier, 6),
            },
        }

    def _check_parameter_stability(self, params: BKTParameters) -> Dict[str, Any]:
        """Validates that parameters satisfy standard bounded non-degenerate constraints."""
        is_degenerate = (
            params.p_guess > 0.40
            or params.p_slip > 0.40
            or (params.p_guess + params.p_slip >= 1.0)
            or params.p_transit <= 0.0
            or params.p_init <= 0.0
        )
        return {
            "is_degenerate": is_degenerate,
            "guess_valid": params.p_guess <= 0.40,
            "slip_valid": params.p_slip <= 0.40,
            "identifiable": (params.p_guess + params.p_slip < 1.0),
            "p_init": round(params.p_init, 4),
            "p_transit": round(params.p_transit, 4),
            "p_guess": round(params.p_guess, 4),
            "p_slip": round(params.p_slip, 4),
        }

    def _evaluate_readiness_gates(
        self,
        total_observations: int,
        log_loss: float,
        brier_score: float,
        stability: Dict[str, Any],
        baselines: Dict[str, Any],
    ) -> Tuple[str, str]:
        """Applies explicit, transparent readiness policy thresholds."""
        if total_observations < 10:
            return (
                "insufficient_data",
                f"Evaluation sample contains only {total_observations} observations (< 10 threshold).",
            )

        if stability.get("is_degenerate", False):
            return (
                "evaluation_failed",
                "Model parameters violate non-degeneracy constraints (guess or slip > 0.40, or guess+slip >= 1.0).",
            )

        global_brier = baselines.get("global_rate_baseline", {}).get("brier_score", 0.50)

        # Readiness qualification:
        # 1. Brier score must be <= 0.30
        # 2. Log loss must be <= 0.75
        # 3. Model must match or improve over naive global baseline within small margin
        if brier_score <= 0.30 and log_loss <= 0.75:
            if brier_score <= global_brier + 0.05:
                return (
                    "evaluation_passed",
                    f"Model passed statistical validation: LogLoss={log_loss:.4f}, Brier={brier_score:.4f}.",
                )
            else:
                return (
                    "requires_review",
                    f"Predictive error exceeds naive global baseline: BKT Brier={brier_score:.4f} vs Baseline={global_brier:.4f}.",
                )

        return (
            "evaluation_failed",
            f"Predictive quality below acceptance gates: LogLoss={log_loss:.4f} (>0.75) or Brier={brier_score:.4f} (>0.30).",
        )
