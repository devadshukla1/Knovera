"""Deterministic Fake Cross-Encoder provider for isolated unit tests without Hugging Face downloads."""

from typing import Any, List, Optional


class FakeCrossEncoder:
    """Thread-safe, lightweight fake Cross-Encoder for tests.

    Provides deterministic scoring based on lexical term overlap or configurable fixed scores.
    """

    def __init__(self, fixed_score: Optional[float] = None) -> None:
        self.fixed_score = fixed_score
        self.call_count = 0
        self.last_pairs: List[List[str]] = []

    def predict(
        self,
        sentences: List[List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        **kwargs: Any,
    ) -> List[float]:
        self.call_count += 1
        self.last_pairs = sentences

        if self.fixed_score is not None:
            return [self.fixed_score] * len(sentences)

        scores: List[float] = []
        for pair in sentences:
            if not pair or len(pair) < 2:
                scores.append(0.0)
                continue
            query = pair[0].lower()
            passage = pair[1].lower()

            q_tokens = set(query.split())
            p_tokens = set(passage.split())
            overlap = len(q_tokens.intersection(p_tokens))

            # Return a realistic raw logit score (e.g. -5.0 base + 2.5 per matching token)
            raw_logit = -5.0 + (2.5 * overlap)
            scores.append(round(raw_logit, 4))

        return scores
