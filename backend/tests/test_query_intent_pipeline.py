"""Integration tests for the complete Query Intent Dataset Preparation Pipeline (Phase 5 C5.1–C5.3)."""

import json
from pathlib import Path
import pytest

from backend.app.ml.query_intent.taxonomy import (
    TAXONOMY_VERSION,
    TaxonomyRegistry,
)
from backend.scripts.prepare_query_intent_dataset import (
    load_jsonl,
    run_pipeline,
    stratified_split_records,
)


def test_stratified_split_reproducibility() -> None:
    """Verifies that stratified splitting is fully deterministic and avoids leakage."""
    # Build sample records with 2 intents, 10 records each
    sample_records = []
    for idx in range(10):
        sample_records.append({
            "example_id": f"qi_a_{idx}",
            "query_text": f"Explain mechanism number {idx}",
            "intent": "explanation",
            "normalized_text": f"explain mechanism number {idx}",
        })
        sample_records.append({
            "example_id": f"qi_b_{idx}",
            "query_text": f"What is definition number {idx}",
            "intent": "definition",
            "normalized_text": f"what is definition number {idx}",
        })

    train1, dev1, test1 = stratified_split_records(
        sample_records, train_ratio=0.7, dev_ratio=0.15, test_ratio=0.15, random_seed=42
    )
    train2, dev2, test2 = stratified_split_records(
        sample_records, train_ratio=0.7, dev_ratio=0.15, test_ratio=0.15, random_seed=42
    )

    # Identical seed yields identical splits
    assert [r["example_id"] for r in train1] == [r["example_id"] for r in train2]
    assert [r["example_id"] for r in dev1] == [r["example_id"] for r in dev2]
    assert [r["example_id"] for r in test1] == [r["example_id"] for r in test2]

    # Verify no overlap between train and test
    train_ids = {r["example_id"] for r in train1}
    test_ids = {r["example_id"] for r in test1}
    dev_ids = {r["example_id"] for r in dev1}
    assert len(train_ids.intersection(test_ids)) == 0
    assert len(train_ids.intersection(dev_ids)) == 0
    assert len(dev_ids.intersection(test_ids)) == 0


def test_full_pipeline_execution(tmp_path: Path) -> None:
    """Verifies end-to-end pipeline execution from raw dataset to processed splits."""
    # 1. Create a minimal mock raw dataset
    raw_path = tmp_path / "raw" / "query_intents.jsonl"
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    test_categories = TaxonomyRegistry.list_category_ids()
    records = []
    counter = 1
    for cat_id in test_categories:
        for ex_num in range(5):
            records.append({
                "example_id": f"qi_test_{counter:04d}",
                "query_text": f"Sample query {ex_num} for category {cat_id}",
                "intent": cat_id,
                "attributes": {
                    "requires_conversation_context": False,
                    "requires_multi_source_evidence": False,
                    "requests_explicit_citations": False,
                    "contains_ambiguous_reference": False,
                },
                "source_type": "synthetic_seed",
                "annotation_status": "pending_human_review",
                "taxonomy_version": TAXONOMY_VERSION,
            })
            counter += 1

    with open(raw_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # 2. Run pipeline
    dataset_dir = tmp_path / "dataset"
    report = run_pipeline(
        raw_path=raw_path,
        dataset_dir=dataset_dir,
        random_seed=42,
        train_ratio=0.6,
        dev_ratio=0.2,
        test_ratio=0.2,
    )

    assert report.is_valid is True
    assert report.total_examples == len(records)

    # 3. Verify output files exist
    assert (dataset_dir / "processed" / "query_intents_processed.jsonl").exists()
    assert (dataset_dir / "splits" / "train.jsonl").exists()
    assert (dataset_dir / "splits" / "dev.jsonl").exists()
    assert (dataset_dir / "splits" / "test.jsonl").exists()
    assert (dataset_dir / "manifest.json").exists()

    # 4. Verify reloadability
    train_recs = load_jsonl(dataset_dir / "splits" / "train.jsonl")
    dev_recs = load_jsonl(dataset_dir / "splits" / "dev.jsonl")
    test_recs = load_jsonl(dataset_dir / "splits" / "test.jsonl")

    assert len(train_recs) + len(dev_recs) + len(test_recs) == len(records)
    for r in train_recs:
        assert r["split"] == "train"
        assert "normalized_text" in r
        assert r["taxonomy_version"] == TAXONOMY_VERSION
