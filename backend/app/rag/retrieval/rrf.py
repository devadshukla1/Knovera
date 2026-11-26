"""Reciprocal Rank Fusion (RRF) for Combining Dense and Lexical Candidate Rankings (Phase 4 C4.3)."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import uuid

from backend.app.core.config import get_settings


@dataclass
class FusedCandidate:
    """Unified ranking result representing a chunk fused across retrieval sources."""

    chunk_id: uuid.UUID
    rrf_score: float
    rank: int = 1
    dense_rank: Optional[int] = None
    bm25_rank: Optional[int] = None
    vector_distance: Optional[float] = None
    bm25_score: Optional[float] = None
    retrieval_sources: List[str] = field(default_factory=list)


class ReciprocalRankFusion:
    """Combines multiple independently ranked retrieval candidate lists into a unified ranking.

    Mathematical Formulation:
        RRF(d) = sum_{r in R} 1 / (k + rank_r(d))

    Where:
        - d is a chunk candidate
        - R is the set of retrieval result lists (e.g. dense, lexical)
        - rank_r(d) is the 1-based position of candidate d in result list r
        - k is the RRF ranking constant (default 60)
    """

    def __init__(self, k: Optional[int] = None) -> None:
        settings = get_settings()
        self.k = k if k is not None else settings.RRF_K
        if self.k <= 0:
            raise ValueError(f"RRF ranking constant k must be > 0, got {self.k}")

    def fuse(
        self,
        ranked_lists: Mapping[str, Sequence[Tuple[uuid.UUID, float]]],
        top_k: int = 10,
    ) -> List[FusedCandidate]:
        """Fuses multiple ranked candidate lists into a deduplicated, deterministically ordered list.

        Args:
            ranked_lists: Mapping of source name (e.g., 'semantic', 'bm25') to sequence of (chunk_id, raw_score).
            top_k: Maximum number of fused candidates to return.

        Returns:
            List of FusedCandidate objects ordered by descending RRF score, with stable tie-breaking.
        """
        if not ranked_lists or top_k <= 0:
            return []

        accum: Dict[uuid.UUID, Dict[str, Any]] = {}

        for source_name, candidate_list in ranked_lists.items():
            if not candidate_list:
                continue

            seen_in_source: Set[uuid.UUID] = set()
            rank = 1

            for chunk_id, raw_score in candidate_list:
                if chunk_id in seen_in_source:
                    continue
                seen_in_source.add(chunk_id)

                reciprocal_rank = 1.0 / (self.k + rank)

                if chunk_id not in accum:
                    accum[chunk_id] = {
                        "chunk_id": chunk_id,
                        "rrf_score": 0.0,
                        "dense_rank": None,
                        "bm25_rank": None,
                        "vector_distance": None,
                        "bm25_score": None,
                        "retrieval_sources": [],
                    }

                entry = accum[chunk_id]
                entry["rrf_score"] += reciprocal_rank
                entry["retrieval_sources"].append(source_name)

                norm_source = source_name.lower()
                if norm_source in ("semantic", "dense", "vector"):
                    entry["dense_rank"] = rank
                    entry["vector_distance"] = float(raw_score)
                elif norm_source in ("bm25", "lexical", "keyword"):
                    entry["bm25_rank"] = rank
                    entry["bm25_score"] = float(raw_score)

                rank += 1

        if not accum:
            return []

        # Deterministic sorting: primary rrf_score descending, secondary chunk_id string ascending
        sorted_entries = sorted(
            accum.values(),
            key=lambda e: (-e["rrf_score"], str(e["chunk_id"])),
        )

        fused_results: List[FusedCandidate] = []
        for rank_idx, entry in enumerate(sorted_entries[:top_k], start=1):
            fused_results.append(
                FusedCandidate(
                    chunk_id=entry["chunk_id"],
                    rrf_score=entry["rrf_score"],
                    rank=rank_idx,
                    dense_rank=entry["dense_rank"],
                    bm25_rank=entry["bm25_rank"],
                    vector_distance=entry["vector_distance"],
                    bm25_score=entry["bm25_score"],
                    retrieval_sources=entry["retrieval_sources"],
                )
            )

        return fused_results
