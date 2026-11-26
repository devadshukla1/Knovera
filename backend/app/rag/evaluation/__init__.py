"""Retrieval evaluation and metrics package (Phase 4 C4.6–C4.7)."""

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
from backend.app.rag.evaluation.validation import (
    DatasetValidationError,
    validate_dataset_integrity,
)

__all__ = [
    "QueryEvaluationResult",
    "recall_at_k",
    "precision_at_k",
    "reciprocal_rank_at_k",
    "find_first_relevant_rank",
    "dcg_at_k",
    "ndcg_at_k",
    "average_precision_at_k",
    "deduplicate_preserve_order",
    "evaluate_query",
    "aggregate_metrics",
    "validate_dataset_integrity",
    "DatasetValidationError",
]
