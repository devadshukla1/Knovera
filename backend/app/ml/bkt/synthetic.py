"""Synthetic BKT Data Generator for Ground-Truth Parameter Recovery Testing (Phase 9 C9.5).

Generates simulated learner observation sequences using exact 4-parameter BKT probabilistic dynamics:
1. True initial latent mastery state: S_0 ~ Bernoulli(P(L_0))
2. For each opportunity t:
   - Generate response:
     if mastered (S_t = 1): correct with prob 1 - S, incorrect with prob S (slip)
     if unmastered (S_t = 0): correct with prob G (guess), incorrect with prob 1 - G
   - State transition:
     if unmastered (S_t = 0): transitions to mastered (S_t+1 = 1) with prob T
     if mastered (S_t = 1): remains mastered (S_t+1 = 1)
"""

from typing import List, Optional
import numpy as np

from backend.app.ml.bkt.inference import BKTParameters


def generate_synthetic_bkt_dataset(
    params: BKTParameters,
    num_learners: int = 200,
    sequence_length: int = 15,
    random_seed: int = 42,
) -> List[List[bool]]:
    """Simulates binary observation sequences across synthetic learners with known parameters."""
    rng = np.random.RandomState(random_seed)
    dataset: List[List[bool]] = []

    for _ in range(num_learners):
        seq: List[bool] = []
        # Sample initial knowledge state: 1 = mastered, 0 = unmastered
        state = 1 if rng.uniform() < params.p_init else 0

        for _ in range(sequence_length):
            # Emission: generate observation based on current state
            if state == 1:
                # Mastered: incorrect with slip probability
                is_correct = rng.uniform() >= params.p_slip
            else:
                # Unmastered: correct with guess probability
                is_correct = rng.uniform() < params.p_guess

            seq.append(is_correct)

            # State transition for next step:
            if state == 0:
                if rng.uniform() < params.p_transit:
                    state = 1
            # If state == 1, stays 1 (no forgetting)

        dataset.append(seq)

    return dataset
