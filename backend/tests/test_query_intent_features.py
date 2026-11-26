"""Unit tests for TF-IDF Feature Extraction Pipeline (Phase 5 C5.4)."""

import pytest
import scipy.sparse as sp

from backend.app.ml.query_intent.features import (
    TECHNICAL_TOKEN_PATTERN,
    build_char_vectorizer,
    build_feature_pipeline,
    build_word_vectorizer,
    compute_feature_stats,
)


def test_word_vectorizer_preserves_technical_tokens() -> None:
    """Verifies that word-level vectorizer preserves technical symbols and bigrams."""
    vec = build_word_vectorizer(ngram_range=(1, 2))
    corpus = [
        "How does C++ memory management work with TCP/IP and BM25?",
        "Compare TF-IDF and K-Means clustering algorithms.",
    ]
    X = vec.fit_transform(corpus)

    assert sp.issparse(X) is True
    feature_names = set(vec.get_feature_names_out())

    # Technical unigrams
    assert "c++" in feature_names
    assert "tcp/ip" in feature_names
    assert "bm25" in feature_names
    assert "tf-idf" in feature_names
    assert "k-means" in feature_names

    # Bigrams
    assert "c++ memory" in feature_names
    assert "tcp/ip and" in feature_names


def test_char_vectorizer_extracts_subwords() -> None:
    """Verifies that character-level vectorizer extracts char_wb n-grams."""
    vec = build_char_vectorizer(ngram_range=(3, 5))
    corpus = ["What is BM25?"]
    X = vec.fit_transform(corpus)

    assert sp.issparse(X) is True
    feature_names = vec.get_feature_names_out()
    # Should contain subwords bounded by word boundaries
    assert any("bm2" in feat for feat in feature_names)


def test_combined_feature_union_sparsity_and_weights() -> None:
    """Verifies combined FeatureUnion produces sparse matrices with expected dimensions."""
    pipeline = build_feature_pipeline(
        feature_type="combined",
        word_weight=1.5,
        char_weight=0.5,
    )
    corpus = [
        "What is BM25 ranking?",
        "Compare TCP and UDP protocols for network data transfer.",
    ]
    X = pipeline.fit_transform(corpus)

    assert sp.issparse(X) is True
    assert X.shape[0] == 2
    assert X.shape[1] > 20

    stats = compute_feature_stats(pipeline, X, feature_type="combined", duration_seconds=0.01)
    assert stats.sample_count == 2
    assert stats.total_features == X.shape[1]
    assert stats.word_vocabulary_size > 0
    assert stats.char_vocabulary_size > 0
    assert 0.0 < stats.density <= 1.0


def test_feature_pipeline_train_only_fitting_and_transform() -> None:
    """Verifies vectorizer is fitted on training data and transforms test data without fitting."""
    train_queries = ["How does gradient descent update model weights?"]
    test_queries = ["Explain quantum entanglement and superpositions."]

    pipeline = build_feature_pipeline(feature_type="word")
    X_train = pipeline.fit_transform(train_queries)
    assert "gradient" in pipeline.vocabulary_

    # Transform test queries
    X_test = pipeline.transform(test_queries)
    assert X_test.shape[1] == X_train.shape[1]
    # "entanglement" was not in train vocabulary, so it should not appear
    assert "entanglement" not in pipeline.vocabulary_


def test_invalid_feature_type_raises() -> None:
    """Verifies that an unsupported feature_type raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported feature_type"):
        build_feature_pipeline(feature_type="invalid_type")  # type: ignore
