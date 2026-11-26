"""Cross-Encoder reranking service and candidate scoring pipeline (Phase 4 C4.4–C4.5)."""

import math
from typing import Any, Callable, List, Optional, Sequence, Tuple, TypeVar
import uuid

from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import get_logger
from backend.app.rag.reranker.exceptions import (
    InferenceError,
    InvalidScoreError,
    RerankerError,
)
from backend.app.rag.reranker.manager import CrossEncoderModelManager

logger = get_logger("knovera.rag.reranker.service")

T = TypeVar("T")


def format_query_passage_pair(query: str, content: str, section_title: Optional[str] = None) -> List[str]:
    """Prepares a [query, passage] pair, incorporating section context if available."""
    clean_query = query.strip()
    clean_content = content.strip()
    if section_title and section_title.strip():
        passage_text = f"{section_title.strip()}\n{clean_content}"
    else:
        passage_text = clean_content
    return [clean_query, passage_text]


class CrossEncoderReranker:
    """Provides batched Cross-Encoder scoring and deterministic reranking of retrieval candidates."""

    def __init__(
        self,
        manager: Optional[CrossEncoderModelManager] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.manager = manager or CrossEncoderModelManager.get_instance(settings=self.settings)

    def score_pairs(self, pairs: List[List[str]]) -> List[float]:
        """Runs batched inference on [[query, passage], ...] pairs and returns raw logit scores.

        MS MARCO Cross-Encoders output uncalibrated logits where higher values indicate
        higher relevance. Scores are verified to be finite real numbers.
        """
        if not pairs:
            return []

        model = self.manager.get_model()
        batch_size = self.settings.CROSS_ENCODER_BATCH_SIZE

        try:
            raw_scores = model.predict(
                sentences=pairs,
                batch_size=batch_size,
                show_progress_bar=False,
            )
        except Exception as exc:
            logger.error("Cross-Encoder inference failed: %s", exc)
            raise InferenceError(f"Cross-Encoder inference failed: {exc}") from exc

        # Normalize output to List[float]
        scores: List[float] = []
        # Support numpy arrays, torch tensors, or python lists
        iterable_scores = raw_scores.tolist() if hasattr(raw_scores, "tolist") else list(raw_scores)

        for idx, val in enumerate(iterable_scores):
            # If model returned a 1-element list/tuple per pair (e.g. [[score]]), unwrap it
            if isinstance(val, (list, tuple)):
                val = val[0]
            float_val = float(val)
            if math.isnan(float_val) or math.isinf(float_val):
                raise InvalidScoreError(
                    f"Cross-Encoder returned non-finite score {float_val} for candidate pair at index {idx}"
                )
            scores.append(float_val)

        return scores

    def rerank_candidates(
        self,
        query: str,
        candidates: Sequence[T],
        get_content: Callable[[T], str],
        get_section_title: Optional[Callable[[T], Optional[str]]] = None,
        get_rrf_rank: Optional[Callable[[T], int]] = None,
        get_chunk_id: Optional[Callable[[T], Any]] = None,
        top_k: Optional[int] = None,
    ) -> Tuple[List[Tuple[T, float, int]], bool]:
        """Reranks candidate objects using the Cross-Encoder model.

        Returns:
            Tuple of (reranked_tuples, was_reranked), where each tuple contains
            (candidate, reranker_score, new_rank).
            If reranking fails and RERANKER_FAILURE_POLICY == 'rrf_only',
            returns original candidates with fallback scores and was_reranked=False.
        """
        if not candidates:
            return [], True

        # Prepare (query, passage) pairs
        pairs: List[List[str]] = []
        for cand in candidates:
            content = get_content(cand)
            section = get_section_title(cand) if get_section_title else None
            pairs.append(format_query_passage_pair(query, content, section))

        try:
            scores = self.score_pairs(pairs)
        except RerankerError as err:
            policy = (self.settings.RERANKER_FAILURE_POLICY or "error").lower().strip()
            if policy == "rrf_only":
                logger.warning(
                    "Reranker failed with policy 'rrf_only'; falling back to original RRF order: %s",
                    err,
                )
                # Fallback: keep original candidate order, no scores
                fallback_results = [
                    (cand, 0.0, idx + 1)
                    for idx, cand in enumerate(candidates[: (top_k or len(candidates))])
                ]
                return fallback_results, False
            # Otherwise re-raise
            raise

        # Pair candidate with score and metadata for deterministic sorting
        scored_candidates: List[Tuple[T, float, int, str]] = []
        for idx, (cand, score) in enumerate(zip(candidates, scores)):
            rrf_rank = get_rrf_rank(cand) if get_rrf_rank else idx + 1
            chunk_id_str = str(get_chunk_id(cand)) if get_chunk_id else str(idx)
            scored_candidates.append((cand, score, rrf_rank, chunk_id_str))

        # Deterministic sort: score DESC, original rrf_rank ASC, chunk_id ASC
        scored_candidates.sort(key=lambda item: (-item[1], item[2], item[3]))

        # Limit to top_k
        final_k = top_k or len(scored_candidates)
        sliced = scored_candidates[:final_k]

        reranked_output: List[Tuple[T, float, int]] = [
            (item[0], item[1], rank_idx + 1)
            for rank_idx, item in enumerate(sliced)
        ]
        return reranked_output, True
