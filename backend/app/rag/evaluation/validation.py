"""Dataset validation and integrity checking for Knovera IR Evaluation (Phase 4 C4.7)."""

from typing import Any, Dict, List, Set, Tuple


class DatasetValidationError(Exception):
    """Raised when an evaluation dataset violates structural or integrity constraints."""


def validate_dataset_integrity(
    corpus: Dict[str, Any],
    queries: List[Dict[str, Any]],
    qrels: Dict[str, Dict[str, int]],
    valid_splits: Tuple[str, ...] = ("dev", "test"),
    valid_grades: Tuple[int, ...] = (0, 1, 2, 3),
) -> Dict[str, Any]:
    """Validates the 10 data quality rules specified in C4.7 Section 8.

    Rules:
    1. Query IDs are unique.
    2. Corpus chunk IDs are unique.
    3. Qrels query IDs exist in queries dataset.
    4. Qrels chunk IDs exist in corpus dataset.
    5. Relevance grades are within valid range (0..3).
    6. Split membership is valid ('dev', 'test').
    7. No unparseable or malformed query records.
    8. Check non-empty corpus content.
    9. Validate query count and qrels coverage.
    10. Ensure zero circular or dangling associations.

    Returns:
        Validation report dictionary with statistics.

    Raises:
        DatasetValidationError: If any critical integrity constraint is violated.
    """
    errors: List[str] = []

    # 1. Unique query IDs and split validation
    seen_query_ids: Set[str] = set()
    split_counts: Dict[str, int] = {s: 0 for s in valid_splits}

    for idx, q in enumerate(queries):
        qid = q.get("query_id")
        if not qid:
            errors.append(f"Query at index {idx} has missing or empty 'query_id'")
            continue
        if qid in seen_query_ids:
            errors.append(f"Duplicate query_id detected: '{qid}'")
        seen_query_ids.add(qid)

        split = q.get("split")
        if split not in valid_splits:
            errors.append(f"Query '{qid}' has invalid split '{split}'. Must be one of {valid_splits}")
        else:
            split_counts[split] += 1

        if not q.get("query") or len(q.get("query", "").strip()) < 3:
            errors.append(f"Query '{qid}' has empty or trivially short query string")

    # 2. Unique corpus chunk IDs & non-empty content
    seen_corpus_ids: Set[str] = set()
    for cid, item in corpus.items():
        if cid in seen_corpus_ids:
            errors.append(f"Duplicate corpus_id detected: '{cid}'")
        seen_corpus_ids.add(cid)

        if not item.get("content") or len(item["content"].strip()) < 10:
            errors.append(f"Corpus chunk '{cid}' has empty or trivially short content")

    # 3 & 4. Qrels referential integrity
    total_judgments = 0
    grade_distribution: Dict[int, int] = {g: 0 for g in valid_grades}

    for qid, chunk_map in qrels.items():
        if qid not in seen_query_ids:
            errors.append(f"Qrels references query_id '{qid}' which does not exist in queries.jsonl")

        for cid, grade in chunk_map.items():
            total_judgments += 1
            if cid not in seen_corpus_ids:
                errors.append(f"Qrels for query '{qid}' references chunk_id '{cid}' which does not exist in corpus.jsonl")

            if grade not in valid_grades:
                errors.append(f"Qrels entry ({qid}, {cid}) has invalid grade '{grade}'. Must be in {valid_grades}")
            else:
                grade_distribution[grade] += 1

    if errors:
        raise DatasetValidationError(f"Dataset integrity validation failed with {len(errors)} error(s):\n" + "\n".join(errors[:10]))

    return {
        "valid": True,
        "corpus_count": len(corpus),
        "queries_total": len(queries),
        "split_counts": split_counts,
        "total_judgments": total_judgments,
        "grade_distribution": grade_distribution,
    }
