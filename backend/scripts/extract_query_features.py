"""Feature Extraction Inspection CLI for Knovera Query Intent Classification (Phase 5 C5.4).

Fits word, character, and combined TF-IDF feature extractors strictly on the training split
and outputs vocabulary statistics, sparsity metrics, and technical token verifications.
"""

import argparse
from pathlib import Path
import time
from typing import List

from backend.app.ml.query_intent.features import (
    TECHNICAL_TOKEN_PATTERN,
    build_feature_pipeline,
    compute_feature_stats,
)
from backend.scripts.prepare_query_intent_dataset import load_jsonl


def run_feature_inspection(
    train_path: Path = Path("data/query_intent/splits/train.jsonl"),
) -> None:
    print("=" * 70)
    print("KNOVERA QUERY INTENT TF-IDF FEATURE EXTRACTION INSPECTION (C5.4)")
    print("=" * 70)

    if not train_path.exists():
        raise FileNotFoundError(f"Training split not found at {train_path}")

    train_records = load_jsonl(train_path)
    X_train: List[str] = [r["normalized_text"] for r in train_records]
    print(f"Loaded {len(X_train)} training queries from {train_path}\n")

    feature_types = ["word", "char", "combined"]
    stats_list = []

    for ft in feature_types:
        print(f"--- Fitting '{ft}' TF-IDF on Training Data ---")
        pipeline = build_feature_pipeline(feature_type=ft)  # type: ignore

        start = time.perf_counter()
        X_mat = pipeline.fit_transform(X_train)
        duration = time.perf_counter() - start

        stats = compute_feature_stats(pipeline, X_mat, feature_type=ft, duration_seconds=duration)
        stats_list.append(stats)

        print(f"  Shape:               {stats.matrix_shape}")
        print(f"  Word Vocab Size:     {stats.word_vocabulary_size}")
        print(f"  Char Vocab Size:     {stats.char_vocabulary_size}")
        print(f"  Total Dimensions:    {stats.total_features}")
        print(f"  Non-Zero Entries:    {stats.non_zero_count}")
        print(f"  Density:             {stats.density * 100:.4f}%")
        print(f"  Fitting Time:        {stats.duration_seconds * 1000:.2f} ms\n")

    # Technical Token Verification on the Combined Pipeline
    print("--- Technical Identifier Preservation Check ---")
    combined_pipeline = build_feature_pipeline(feature_type="combined")
    combined_pipeline.fit(X_train)

    # Word vectorizer is the first transformer in FeatureUnion
    word_vec = combined_pipeline.transformer_list[0][1]
    vocab = word_vec.vocabulary_

    test_tokens = [
        "c++", "tcp/ip", "bm25", "tf-idf", "postgresql",
        "fastapi", "k-means", "gpt-4", "rag", "svm", "api", "sql"
    ]

    for tok in test_tokens:
        in_vocab = tok in vocab
        status = "PRESENT" if in_vocab else "NOT IN TRAIN VOCAB (Expected if not in train text)"
        print(f"  Token '{tok}': {status}")

    print("\nFeature extraction verification completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect TF-IDF Feature Extraction")
    parser.add_argument(
        "--train-path",
        type=Path,
        default=Path("data/query_intent/splits/train.jsonl"),
        help="Path to training split jsonl",
    )
    args = parser.parse_args()
    run_feature_inspection(train_path=args.train_path)


if __name__ == "__main__":
    main()
