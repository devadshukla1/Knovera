"""Data Leakage and Split Isolation Tests for Query Intent Classification (Phase 5 C5.4–C5.6)."""

from pathlib import Path
import pytest

from backend.app.ml.query_intent.features import build_feature_pipeline
from backend.app.ml.query_intent.taxonomy import TAXONOMY_VERSION
from backend.scripts.prepare_query_intent_dataset import load_jsonl


def test_no_split_id_overlap() -> None:
    """Verifies that example IDs are strictly disjoint across train, dev, and test splits."""
    train_recs = load_jsonl(Path("data/query_intent/splits/train.jsonl"))
    dev_recs = load_jsonl(Path("data/query_intent/splits/dev.jsonl"))
    test_recs = load_jsonl(Path("data/query_intent/splits/test.jsonl"))

    train_ids = {r["example_id"] for r in train_recs}
    dev_ids = {r["example_id"] for r in dev_recs}
    test_ids = {r["example_id"] for r in test_recs}

    assert len(train_ids.intersection(dev_ids)) == 0, "Train and Dev splits share example IDs!"
    assert len(train_ids.intersection(test_ids)) == 0, "Train and Test splits share example IDs!"
    assert len(dev_ids.intersection(test_ids)) == 0, "Dev and Test splits share example IDs!"


def test_tfidf_fitted_strictly_on_train_split() -> None:
    """Verifies that TF-IDF vocabulary does not contain terms present exclusively in held-out splits."""
    train_recs = load_jsonl(Path("data/query_intent/splits/train.jsonl"))
    test_recs = load_jsonl(Path("data/query_intent/splits/test.jsonl"))

    X_train = [r["normalized_text"] for r in train_recs]
    X_test = [r["normalized_text"] for r in test_recs]

    pipeline = build_feature_pipeline(feature_type="word")
    pipeline.fit(X_train)
    train_vocab = set(pipeline.vocabulary_.keys())

    # Find a word that appears in X_test but was not in X_train
    test_words = set()
    for q in X_test:
        test_words.update(q.split())

    train_words = set()
    for q in X_train:
        train_words.update(q.split())

    exclusive_test_words = test_words - train_words
    # If there are exclusive test words, ensure NONE of them leaked into train_vocab
    if exclusive_test_words:
        for word in exclusive_test_words:
            assert word not in train_vocab, f"Data leakage detected! Test word '{word}' found in fitted train vocabulary!"


def test_all_13_categories_represented_in_train_and_dev() -> None:
    """Verifies every one of the 13 taxonomy categories is present in train and dev splits."""
    from backend.app.ml.query_intent.taxonomy import TaxonomyRegistry

    all_categories = set(TaxonomyRegistry.list_category_ids())

    train_recs = load_jsonl(Path("data/query_intent/splits/train.jsonl"))
    dev_recs = load_jsonl(Path("data/query_intent/splits/dev.jsonl"))
    test_recs = load_jsonl(Path("data/query_intent/splits/test.jsonl"))

    train_cats = {r["intent"] for r in train_recs}
    dev_cats = {r["intent"] for r in dev_recs}
    test_cats = {r["intent"] for r in test_recs}

    assert train_cats == all_categories
    assert dev_cats == all_categories
    assert test_cats == all_categories
