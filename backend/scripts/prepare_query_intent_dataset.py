"""Dataset Preprocessing and Splitting Pipeline for Query Intent Classification (Phase 5 C5.2 / C5.3).

Executes end-to-end preparation:
1. Loads raw query intent records
2. Validates records against taxonomy and schema
3. Applies conservative text preprocessing (preserving technical tokens and question words)
4. Generates deterministic stratified train/dev/test splits
5. Exports processed and split datasets with an updated manifest.json
"""

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
from typing import Any, Dict, List, Tuple

from backend.app.ml.query_intent.dataset_validator import (
    DatasetValidationError,
    DatasetValidationReport,
    QueryIntentDatasetValidator,
)
from backend.app.ml.query_intent.preprocessing import (
    PREPROCESSING_VERSION,
    PreprocessedQuery,
    QueryPreprocessor,
)
from backend.app.ml.query_intent.taxonomy import (
    TAXONOMY_VERSION,
    TaxonomyRegistry,
)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Loads a JSONL file into a list of dictionaries."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as e:
                raise ValueError(f"Malformed JSON at {path}:{line_num}: {e}")
    return records


def write_jsonl(records: List[Dict[str, Any]], path: Path) -> None:
    """Writes a list of dictionaries to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def stratified_split_records(
    records: List[Dict[str, Any]],
    train_ratio: float = 0.70,
    dev_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Deterministically splits records into train, dev, and test sets.

    Groups records by normalized query text to prevent identical queries
    from leaking across splits, and stratifies across intent categories.
    """
    total_ratio = train_ratio + dev_ratio + test_ratio
    if not math.isclose(total_ratio, 1.0, rel_tol=1e-3):
        raise ValueError(f"Split ratios must sum to 1.0, got {total_ratio}")

    rng = random.Random(random_seed)

    # 1. Group records by intent and by normalized query text
    # Intent -> List of [group_of_identical_records]
    intent_groups: Dict[str, List[List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for rec in records:
        intent = rec["intent"]
        norm_key = rec.get("normalized_text", rec["query_text"].lower().strip())
        intent_groups[intent][norm_key].append(rec)

    train_records: List[Dict[str, Any]] = []
    dev_records: List[Dict[str, Any]] = []
    test_records: List[Dict[str, Any]] = []

    # 2. Stratify each intent category independently
    for intent, groups_dict in sorted(intent_groups.items()):
        groups_list = list(groups_dict.values())
        # Shuffle group ordering deterministically
        rng.shuffle(groups_list)

        n_groups = len(groups_list)
        n_train = int(round(n_groups * train_ratio))
        n_dev = int(round(n_groups * dev_ratio))
        # Ensure at least 1 dev and 1 test if we have at least 5 groups
        if n_groups >= 5:
            n_dev = max(1, n_dev)
            n_test = max(1, n_groups - n_train - n_dev)
            n_train = n_groups - n_dev - n_test
        else:
            n_test = n_groups - n_train - n_dev

        train_groups = groups_list[:n_train]
        dev_groups = groups_list[n_train : n_train + n_dev]
        test_groups = groups_list[n_train + n_dev :]

        for grp in train_groups:
            for item in grp:
                item_copy = dict(item)
                item_copy["split"] = "train"
                train_records.append(item_copy)

        for grp in dev_groups:
            for item in grp:
                item_copy = dict(item)
                item_copy["split"] = "dev"
                dev_records.append(item_copy)

        for grp in test_groups:
            for item in grp:
                item_copy = dict(item)
                item_copy["split"] = "test"
                test_records.append(item_copy)

    # Deterministic sort by example_id
    train_records.sort(key=lambda x: x["example_id"])
    dev_records.sort(key=lambda x: x["example_id"])
    test_records.sort(key=lambda x: x["example_id"])

    return train_records, dev_records, test_records


def build_manifest(
    raw_count: int,
    processed_count: int,
    train_count: int,
    dev_count: int,
    test_count: int,
    report: DatasetValidationReport,
    random_seed: int,
) -> Dict[str, Any]:
    """Assembles reproducible manifest metadata."""
    return {
        "dataset_name": "knovera_query_intent_benchmark",
        "taxonomy_version": TAXONOMY_VERSION,
        "preprocessing_version": PREPROCESSING_VERSION,
        "random_seed": random_seed,
        "summary": {
            "total_raw_examples": raw_count,
            "total_processed_examples": processed_count,
            "train_examples": train_count,
            "dev_examples": dev_count,
            "test_examples": test_count,
            "category_count": len(report.examples_per_category),
            "unreviewed_count": report.unreviewed_example_count,
            "duplicate_count": report.duplicate_count,
        },
        "class_distribution": {
            "counts": report.examples_per_category,
            "percentages": report.category_distribution,
        },
        "split_distribution": report.examples_per_split,
        "source_type_distribution": report.source_type_distribution,
        "splits": {
            "train": {"path": "splits/train.jsonl", "count": train_count, "ratio": round(train_count / processed_count, 3)},
            "dev": {"path": "splits/dev.jsonl", "count": dev_count, "ratio": round(dev_count / processed_count, 3)},
            "test": {"path": "splits/test.jsonl", "count": test_count, "ratio": round(test_count / processed_count, 3)},
        },
    }


def run_pipeline(
    raw_path: Path,
    dataset_dir: Path,
    random_seed: int = 42,
    train_ratio: float = 0.70,
    dev_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> DatasetValidationReport:
    """Executes the complete dataset preparation pipeline."""
    print("=" * 70)
    print("KNOVERA QUERY INTENT DATASET PREPARATION PIPELINE")
    print(f"Taxonomy Version:      {TAXONOMY_VERSION}")
    print(f"Preprocessing Version: {PREPROCESSING_VERSION}")
    print(f"Random Seed:           {random_seed}")
    print("=" * 70)

    # 1. Load Raw Records
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw dataset file not found at {raw_path}")
    raw_records = load_jsonl(raw_path)
    print(f"\n[1/5] Loaded {len(raw_records)} raw records from {raw_path}")

    # 2. Validate Raw Records
    validator = QueryIntentDatasetValidator(expected_taxonomy_version=TAXONOMY_VERSION)
    raw_report = validator.validate_records(raw_records, require_splits=False)
    if not raw_report.is_valid:
        raise DatasetValidationError(
            f"Raw dataset validation failed with {len(raw_report.errors)} errors: {raw_report.errors[:5]}"
        )
    print(f"[2/5] Raw dataset validation PASSED ({raw_report.total_examples} valid records)")

    # 3. Preprocess Text
    preprocessor = QueryPreprocessor()
    processed_records = []
    redaction_count = 0
    truncation_count = 0

    for rec in raw_records:
        preprocessed: PreprocessedQuery = preprocessor.preprocess(rec["query_text"])
        if preprocessed.was_redacted:
            redaction_count += 1
        if preprocessed.was_truncated:
            truncation_count += 1

        rec_copy = dict(rec)
        rec_copy["query_text"] = preprocessed.sanitized_text
        rec_copy["normalized_text"] = preprocessed.normalized_text
        rec_copy["was_redacted"] = preprocessed.was_redacted
        rec_copy["was_truncated"] = preprocessed.was_truncated
        rec_copy["preprocessing_version"] = preprocessed.preprocessing_version
        processed_records.append(rec_copy)

    print(
        f"[3/5] Preprocessed {len(processed_records)} queries "
        f"(Redacted: {redaction_count}, Truncated: {truncation_count})"
    )

    # 4. Stratified Train / Dev / Test Split
    train_recs, dev_recs, test_recs = stratified_split_records(
        processed_records,
        train_ratio=train_ratio,
        dev_ratio=dev_ratio,
        test_ratio=test_ratio,
        random_seed=random_seed,
    )
    print(
        f"[4/5] Generated Stratified Splits: "
        f"Train={len(train_recs)}, Dev={len(dev_recs)}, Test={len(test_recs)}"
    )

    # 5. Export Datasets & Validate Split Invariants
    all_split_recs = train_recs + dev_recs + test_recs
    split_report = validator.validate_records(all_split_recs, require_splits=True)
    if not split_report.is_valid:
        raise DatasetValidationError(
            f"Split dataset validation failed with {len(split_report.errors)} errors: {split_report.errors[:5]}"
        )

    processed_path = dataset_dir / "processed" / "query_intents_processed.jsonl"
    splits_dir = dataset_dir / "splits"
    train_path = splits_dir / "train.jsonl"
    dev_path = splits_dir / "dev.jsonl"
    test_path = splits_dir / "test.jsonl"
    manifest_path = dataset_dir / "manifest.json"

    write_jsonl(all_split_recs, processed_path)
    write_jsonl(train_recs, train_path)
    write_jsonl(dev_recs, dev_path)
    write_jsonl(test_recs, test_path)

    manifest_data = build_manifest(
        raw_count=len(raw_records),
        processed_count=len(processed_records),
        train_count=len(train_recs),
        dev_count=len(dev_recs),
        test_count=len(test_recs),
        report=split_report,
        random_seed=random_seed,
    )

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print(f"[5/5] Exported all artifacts to {dataset_dir}:")
    print(f"  - Processed: {processed_path}")
    print(f"  - Train:     {train_path}")
    print(f"  - Dev:       {dev_path}")
    print(f"  - Test:      {test_path}")
    print(f"  - Manifest:  {manifest_path}")

    # Print Class Distribution Report Table
    print("\n" + "=" * 70)
    print("CLASS DISTRIBUTION REPORT")
    print("=" * 70)
    print(f"{'Category':<25} | {'Train':<7} | {'Dev':<7} | {'Test':<7} | {'Total':<7} | {'Pct %':<6}")
    print("-" * 70)

    train_cat_counts = Counter(r["intent"] for r in train_recs)
    dev_cat_counts = Counter(r["intent"] for r in dev_recs)
    test_cat_counts = Counter(r["intent"] for r in test_recs)

    for cat_id in sorted(split_report.examples_per_category.keys()):
        tot = split_report.examples_per_category[cat_id]
        tr = train_cat_counts[cat_id]
        dv = dev_cat_counts[cat_id]
        te = test_cat_counts[cat_id]
        pct = split_report.category_distribution[cat_id]
        print(f"{cat_id:<25} | {tr:<7} | {dv:<7} | {te:<7} | {tot:<7} | {pct:<6.2f}%")

    print("-" * 70)
    print(
        f"{'TOTAL':<25} | {len(train_recs):<7} | {len(dev_recs):<7} | "
        f"{len(test_recs):<7} | {len(all_split_recs):<7} | 100.00%"
    )
    print("=" * 70)

    return split_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Knovera Query Intent Dataset")
    parser.add_argument(
        "--raw-path",
        type=Path,
        default=Path("data/query_intent/raw/query_intents.jsonl"),
        help="Path to raw query intent jsonl file",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("data/query_intent"),
        help="Base directory for query intent dataset",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for splitting")
    parser.add_argument("--train-ratio", type=float, default=0.70, help="Train split ratio")
    parser.add_argument("--dev-ratio", type=float, default=0.15, help="Dev split ratio")
    parser.add_argument("--test-ratio", type=float, default=0.15, help="Test split ratio")

    args = parser.parse_args()

    run_pipeline(
        raw_path=args.raw_path,
        dataset_dir=args.dataset_dir,
        random_seed=args.seed,
        train_ratio=args.train_ratio,
        dev_ratio=args.dev_ratio,
        test_ratio=args.test_ratio,
    )


if __name__ == "__main__":
    main()
