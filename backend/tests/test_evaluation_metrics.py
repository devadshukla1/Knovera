"""Unit tests for IR Evaluation Metrics (Recall, Precision, MRR, nDCG, MAP) (Phase 4 C4.6–C4.7)."""

import math
import pytest

from backend.app.rag.evaluation.metrics import (
    QueryEvaluationResult,
    aggregate_metrics,
    average_precision_at_k,
    dcg_at_k,
    deduplicate_preserve_order,
    evaluate_query,
    find_first_relevant_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
)


def test_deduplicate_preserve_order():
    raw = ["doc_A", "doc_B", "doc_A", "doc_C", "doc_B", "doc_D"]
    deduped = deduplicate_preserve_order(raw)
    assert deduped == ["doc_A", "doc_B", "doc_C", "doc_D"]
    assert deduplicate_preserve_order([]) == []


def test_precision_at_k_with_duplicates_and_cutoffs():
    relevant = {"d1", "d3"}
    # Contains duplicate d1
    retrieved = ["d1", "d1", "d2", "d4", "d3", "d5"]

    # Deduplicated list: ["d1", "d2", "d4", "d3", "d5"]
    assert precision_at_k(retrieved, relevant, k=1) == 1.0
    assert pytest.approx(precision_at_k(retrieved, relevant, k=3), rel=1e-4) == 1 / 3
    assert precision_at_k(retrieved, relevant, k=5) == 2 / 5
    assert precision_at_k([], relevant, k=5) == 0.0
    assert precision_at_k(retrieved, set(), k=5) == 0.0


def test_recall_at_k_with_deduplication():
    relevant = {"d1", "d3"}
    # Retrieved has duplicate d1
    retrieved = ["d1", "d1", "d2", "d4", "d3", "d5"]
    # Deduped: ["d1", "d2", "d4", "d3", "d5"]

    assert recall_at_k(retrieved, relevant, k=1) == 0.5
    assert recall_at_k(retrieved, relevant, k=3) == 0.5
    assert recall_at_k(retrieved, relevant, k=4) == 1.0
    assert recall_at_k(retrieved, relevant, k=5) == 1.0
    assert recall_at_k([], relevant, k=5) == 0.0
    assert recall_at_k(retrieved, set(), k=5) == 0.0


def test_reciprocal_rank_at_k_and_first_rank():
    relevant = {"d2", "d5"}
    retrieved = ["d1", "d2", "d3", "d4", "d5"]

    # First relevant doc is at rank 2 (index 1) -> 1/2 = 0.5
    assert reciprocal_rank_at_k(retrieved, relevant, k=1) == 0.0
    assert reciprocal_rank_at_k(retrieved, relevant, k=3) == 0.5
    assert reciprocal_rank_at_k(retrieved, relevant, k=5) == 0.5
    assert find_first_relevant_rank(retrieved, relevant) == 2

    # If first is at rank 1
    assert reciprocal_rank_at_k(["d2", "d1"], relevant, k=3) == 1.0
    assert find_first_relevant_rank(["d2", "d1"], relevant) == 1

    # If no relevant doc in retrieved
    assert reciprocal_rank_at_k(["d99", "d98"], relevant, k=5) == 0.0
    assert find_first_relevant_rank(["d99", "d98"], relevant) is None


def test_dcg_and_ndcg_at_k_graded_relevance():
    qrels = {"d1": 3, "d2": 0, "d3": 2, "d4": 0}
    retrieved = ["d2", "d1", "d3"]

    # DCG calculation:
    # rank 1: d2 (rel 0) -> gain=0
    # rank 2: d1 (rel 3) -> gain=(2^3 - 1)=7, disc=log2(3)=1.5849625 -> 7 / 1.5849625 = 4.416729
    # rank 3: d3 (rel 2) -> gain=(2^2 - 1)=3, disc=log2(4)=2.0 -> 3 / 2.0 = 1.5
    expected_dcg = 0.0 + (7.0 / math.log2(3)) + (3.0 / math.log2(4))
    assert pytest.approx(dcg_at_k(retrieved, qrels, k=3), rel=1e-5) == expected_dcg

    # IDCG calculation (ideal order [3, 2]):
    # rank 1: rel 3 -> gain 7 / log2(2) = 7.0
    # rank 2: rel 2 -> gain 3 / log2(3) = 1.892789
    expected_idcg = 7.0 + (3.0 / math.log2(3))
    expected_ndcg = expected_dcg / expected_idcg

    assert pytest.approx(ndcg_at_k(retrieved, qrels, k=3), rel=1e-5) == expected_ndcg

    # Perfect ranking achieves 1.0
    assert ndcg_at_k(["d1", "d3", "d2"], qrels, k=3) == 1.0
    # Empty retrieved or empty qrels
    assert ndcg_at_k([], qrels, k=3) == 0.0
    assert ndcg_at_k(retrieved, {}, k=3) == 0.0


def test_average_precision_at_k():
    relevant = {"d1", "d3"}
    # Retrieved: ["d1", "d2", "d3"]
    # rank 1: d1 (rel) -> P@1 = 1/1 = 1.0
    # rank 2: d2 (not) -> 0
    # rank 3: d3 (rel) -> P@3 = 2/3
    # AP@3 = (1.0 + 2/3) / 2 = 1.6666 / 2 = 0.8333...
    retrieved = ["d1", "d2", "d3"]
    assert pytest.approx(average_precision_at_k(retrieved, relevant, k=3), rel=1e-4) == (1.0 + (2 / 3)) / 2


def test_evaluate_query_relevance_threshold_and_eligibility():
    # qrels with graded relevance: d1 has grade 3, d2 has grade 1, d3 has grade 2
    qrels = {"d1": 3, "d2": 1, "d3": 2}
    retrieved = ["d2", "d1", "d3"]

    # When relevance_threshold=2: d2 (grade 1) is NOT binary relevant, d1 and d3 ARE relevant
    res = evaluate_query(
        retrieved_ids=retrieved,
        qrels=qrels,
        relevance_threshold=2,
        k_values=(1, 2, 3),
        query_id="q_test",
        query="test query",
    )

    assert res.is_evaluable is True
    assert res.relevant_chunks_total == 2  # {d1, d3}
    # rank 1 is d2 (grade 1 < 2), so first relevant is d1 at rank 2
    assert res.first_relevant_rank == 2
    assert res.metrics["recall@1"] == 0.0
    assert res.metrics["recall@2"] == 0.5  # found d1 out of {d1, d3}
    assert res.metrics["recall@3"] == 1.0  # found d1 and d3
    assert res.metrics["mrr@2"] == 0.5     # 1 / 2

    # Query with zero relevant chunks in qrels (e.g. all grade 0 or 1 under threshold 2)
    qrels_empty = {"d2": 1}
    res_empty = evaluate_query(
        retrieved_ids=retrieved,
        qrels=qrels_empty,
        relevance_threshold=2,
        k_values=(1, 2, 3),
        query_id="q_unanswerable",
    )
    assert res_empty.is_evaluable is False
    assert res_empty.relevant_chunks_total == 0
    assert res_empty.metrics["recall@3"] == 0.0


def test_candidate_stage_vs_final_stage_evaluation():
    qrels = {"d1": 3, "d2": 3}
    # Candidate generator found d1 and d2 in top 10
    candidate_ids = ["d3", "d1", "d4", "d2", "d5"]
    # Final reranked only kept top 2: d1 and d3
    final_ids = ["d1", "d3"]

    res = evaluate_query(
        retrieved_ids=final_ids,
        candidate_ids=candidate_ids,
        qrels=qrels,
        relevance_threshold=2,
        k_values=(2, 5),
    )

    # Candidate recall@5 should be 1.0 (found both d1 and d2)
    assert res.candidate_metrics["candidate_recall@5"] == 1.0
    # Final recall@2 is 0.5 (only d1 kept in top 2)
    assert res.metrics["recall@2"] == 0.5


def test_aggregate_metrics_denominator_accounting():
    qrels_eval = {"d1": 3}
    res1 = evaluate_query(["d1"], qrels_eval, relevance_threshold=2, k_values=(5,))  # Recall@5 = 1.0
    res2 = evaluate_query(["d2"], qrels_eval, relevance_threshold=2, k_values=(5,))  # Recall@5 = 0.0

    # Query 3 has NO relevant qrels -> must be excluded from macro denominator
    res3 = evaluate_query(["d1"], {"d1": 1}, relevance_threshold=2, k_values=(5,))  # is_evaluable = False

    agg = aggregate_metrics([res1, res2, res3], total_queries=3)
    assert agg["queries_loaded"] == 3
    assert agg["queries_evaluated"] == 3
    assert agg["queries_evaluable"] == 2
    assert agg["queries_no_relevant"] == 1

    # Macro average across the 2 evaluable queries: (1.0 + 0.0) / 2 = 0.5
    assert agg["recall@5"] == 0.5
