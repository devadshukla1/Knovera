"""Information Retrieval evaluation metrics (Phase 4 C4.6–C4.7).

Implements standard, mathematically rigorous IR ranking evaluation metrics:
- Recall@K
- Mean Reciprocal Rank (MRR@K)
- Normalized Discounted Cumulative Gain (nDCG@K) with graded relevance
- Precision@K
- Mean Average Precision (MAP@K)
- Two-stage Candidate vs Final Stage Recall
- Dataset-level Judgment Coverage & Eligibility-aware Macro Aggregation
"""

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


def deduplicate_preserve_order(items: Sequence[str]) -> List[str]:
    """Deduplicates a sequence while strictly preserving the initial appearance order."""
    seen: Set[str] = set()
    deduped: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def precision_at_k(retrieved_ids: Sequence[str], relevant_ids: Set[str], k: int) -> float:
    """Computes Precision@K: Fraction of top-K unique retrieved documents that are relevant."""
    if k <= 0 or not retrieved_ids:
        return 0.0
    deduped = deduplicate_preserve_order(retrieved_ids)
    top_k = deduped[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / k


def recall_at_k(retrieved_ids: Sequence[str], relevant_ids: Set[str], k: int) -> float:
    """Computes Recall@K: Fraction of all known relevant documents retrieved in top-K unique items."""
    if not relevant_ids or k <= 0 or not retrieved_ids:
        return 0.0
    deduped = deduplicate_preserve_order(retrieved_ids)
    top_k = deduped[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / len(relevant_ids)


def reciprocal_rank_at_k(retrieved_ids: Sequence[str], relevant_ids: Set[str], k: int) -> float:
    """Computes Reciprocal Rank at K (1 / rank of first relevant doc, or 0.0 if none in top K)."""
    if not relevant_ids or k <= 0 or not retrieved_ids:
        return 0.0
    deduped = deduplicate_preserve_order(retrieved_ids)
    top_k = deduped[:k]
    for idx, doc_id in enumerate(top_k):
        if doc_id in relevant_ids:
            return 1.0 / (idx + 1)
    return 0.0


def find_first_relevant_rank(retrieved_ids: Sequence[str], relevant_ids: Set[str]) -> Optional[int]:
    """Returns the 1-based rank of the first relevant document in the retrieved list, or None."""
    if not relevant_ids or not retrieved_ids:
        return None
    deduped = deduplicate_preserve_order(retrieved_ids)
    for idx, doc_id in enumerate(deduped):
        if doc_id in relevant_ids:
            return idx + 1
    return None


def dcg_at_k(retrieved_ids: Sequence[str], qrels: Dict[str, int], k: int) -> float:
    """Computes Discounted Cumulative Gain (DCG@K) using standard exponential gain formula:

    DCG@K = sum_{i=1}^K (2^{rel_i} - 1) / log2(i + 1)
    where i is 1-based rank.
    """
    if k <= 0 or not retrieved_ids:
        return 0.0
    deduped = deduplicate_preserve_order(retrieved_ids)
    top_k = deduped[:k]
    dcg = 0.0
    for idx, doc_id in enumerate(top_k):
        rel = qrels.get(doc_id, 0)
        if rel > 0:
            gain = (2 ** rel) - 1
            discount = math.log2(idx + 2)  # idx 0 -> log2(2) = 1.0
            dcg += gain / discount
    return dcg


def ndcg_at_k(retrieved_ids: Sequence[str], qrels: Dict[str, int], k: int) -> float:
    """Computes Normalized Discounted Cumulative Gain (nDCG@K).

    nDCG@K = DCG@K / IDCG@K, where IDCG is the ideal DCG obtained by sorting
    all known positive judged relevance grades in descending order.
    """
    if k <= 0 or not qrels or not retrieved_ids:
        return 0.0

    actual_dcg = dcg_at_k(retrieved_ids, qrels, k)

    # Ideal ranking of all known positive judgments
    ideal_scores = sorted([rel for rel in qrels.values() if rel > 0], reverse=True)[:k]
    if not ideal_scores:
        return 0.0

    idcg = 0.0
    for idx, rel in enumerate(ideal_scores):
        gain = (2 ** rel) - 1
        discount = math.log2(idx + 2)
        idcg += gain / discount

    if idcg <= 0.0:
        return 0.0
    return actual_dcg / idcg


def average_precision_at_k(retrieved_ids: Sequence[str], relevant_ids: Set[str], k: int) -> float:
    """Computes Average Precision (AP@K) for a single query."""
    if not relevant_ids or k <= 0 or not retrieved_ids:
        return 0.0

    deduped = deduplicate_preserve_order(retrieved_ids)
    top_k = deduped[:k]
    hits = 0
    sum_precisions = 0.0

    for idx, doc_id in enumerate(top_k):
        if doc_id in relevant_ids:
            hits += 1
            sum_precisions += hits / (idx + 1)

    total_relevant = min(len(relevant_ids), k)
    if total_relevant == 0:
        return 0.0
    return sum_precisions / total_relevant


@dataclass
class QueryEvaluationResult:
    """Structured container for single-query retrieval evaluation."""

    query_id: str
    query: str
    category: Optional[str] = None
    is_evaluable: bool = True
    relevant_chunks_total: int = 0
    relevant_chunks_retrieved: int = 0
    first_relevant_rank: Optional[int] = None
    known_judgment_count: int = 0
    judgment_coverage: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    candidate_metrics: Optional[Dict[str, float]] = None
    latency_ms: float = 0.0
    retrieved_ids: List[str] = field(default_factory=list)


def evaluate_query(
    retrieved_ids: Sequence[str],
    qrels: Dict[str, int],
    relevance_threshold: int = 2,
    k_values: Tuple[int, ...] = (5, 10, 20, 50),
    query_id: str = "query",
    query: str = "",
    category: Optional[str] = None,
    candidate_ids: Optional[Sequence[str]] = None,
    latency_ms: float = 0.0,
) -> QueryEvaluationResult:
    """Computes all IR metrics for a single query with binary thresholding and graded nDCG."""
    deduped_retrieved = deduplicate_preserve_order(retrieved_ids)

    # Relevant documents are those meeting the binary threshold
    relevant_set = {doc_id for doc_id, grade in qrels.items() if grade >= relevance_threshold}
    total_relevant = len(relevant_set)
    is_evaluable = total_relevant > 0

    first_rank = find_first_relevant_rank(deduped_retrieved, relevant_set)

    # Count how many of the top retrieved results have any judged score in qrels
    max_k = max(k_values) if k_values else len(deduped_retrieved)
    top_slice = deduped_retrieved[:max_k]
    known_count = sum(1 for d in top_slice if d in qrels)
    coverage = round(known_count / len(top_slice), 4) if top_slice else 0.0

    retrieved_hits = sum(1 for d in top_slice if d in relevant_set)

    metrics: Dict[str, float] = {}
    for k in k_values:
        metrics[f"recall@{k}"] = round(recall_at_k(deduped_retrieved, relevant_set, k), 4)
        metrics[f"precision@{k}"] = round(precision_at_k(deduped_retrieved, relevant_set, k), 4)
        metrics[f"mrr@{k}"] = round(reciprocal_rank_at_k(deduped_retrieved, relevant_set, k), 4)
        metrics[f"ndcg@{k}"] = round(ndcg_at_k(deduped_retrieved, qrels, k), 4)
        metrics[f"map@{k}"] = round(average_precision_at_k(deduped_retrieved, relevant_set, k), 4)

    # Candidate-stage evaluation (before reranking) if available
    cand_metrics: Optional[Dict[str, float]] = None
    if candidate_ids is not None:
        cand_deduped = deduplicate_preserve_order(candidate_ids)
        cand_metrics = {}
        for k in k_values:
            cand_metrics[f"candidate_recall@{k}"] = round(recall_at_k(cand_deduped, relevant_set, k), 4)
            cand_metrics[f"candidate_mrr@{k}"] = round(reciprocal_rank_at_k(cand_deduped, relevant_set, k), 4)

    return QueryEvaluationResult(
        query_id=query_id,
        query=query,
        category=category,
        is_evaluable=is_evaluable,
        relevant_chunks_total=total_relevant,
        relevant_chunks_retrieved=retrieved_hits,
        first_relevant_rank=first_rank,
        known_judgment_count=known_count,
        judgment_coverage=coverage,
        metrics=metrics,
        candidate_metrics=cand_metrics,
        latency_ms=latency_ms,
        retrieved_ids=deduped_retrieved,
    )


def aggregate_metrics(
    eval_results: Sequence[QueryEvaluationResult],
    total_queries: int,
) -> Dict[str, Any]:
    """Averages query metrics across evaluable queries with explicit denominator accounting.

    Queries with zero judged relevant chunks are excluded from the macro-average recall
    and nDCG calculations and accounted for separately in `queries_no_relevant`.
    """
    if not eval_results:
        return {
            "queries_loaded": total_queries,
            "queries_evaluated": 0,
            "queries_evaluable": 0,
            "queries_no_relevant": total_queries,
            "coverage": 0.0,
            "avg_judgment_coverage": 0.0,
        }

    evaluable_runs = [r for r in eval_results if r.is_evaluable]
    queries_no_relevant = len(eval_results) - len(evaluable_runs)
    evaluable_count = len(evaluable_runs)

    agg: Dict[str, Any] = {
        "queries_loaded": total_queries,
        "queries_evaluated": len(eval_results),
        "queries_evaluable": evaluable_count,
        "queries_no_relevant": queries_no_relevant,
    }

    if evaluable_count > 0:
        # Aggregate standard ranking metrics across evaluable queries
        sample_metrics = evaluable_runs[0].metrics
        for key in sample_metrics.keys():
            total_val = sum(r.metrics.get(key, 0.0) for r in evaluable_runs)
            agg[key] = round(total_val / evaluable_count, 4)

        # Aggregate candidate-stage metrics if present
        if evaluable_runs[0].candidate_metrics:
            cand_keys = evaluable_runs[0].candidate_metrics.keys()
            for ckey in cand_keys:
                c_total = sum(r.candidate_metrics.get(ckey, 0.0) for r in evaluable_runs if r.candidate_metrics)
                agg[ckey] = round(c_total / evaluable_count, 4)

    # Dataset-level coverage and judgment coverage
    queries_with_results = sum(1 for r in eval_results if len(r.retrieved_ids) > 0)
    agg["coverage"] = round(queries_with_results / total_queries, 4) if total_queries > 0 else 0.0

    avg_cov = sum(r.judgment_coverage for r in eval_results) / len(eval_results)
    agg["avg_judgment_coverage"] = round(avg_cov, 4)

    return agg
