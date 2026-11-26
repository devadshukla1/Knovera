"""Unit tests for Query Intent Preprocessing Pipeline (Phase 5 C5.3)."""

import pytest

from backend.app.ml.query_intent.preprocessing import (
    PREPROCESSING_VERSION,
    PreprocessedQuery,
    QueryPreprocessor,
)


@pytest.fixture
def preprocessor() -> QueryPreprocessor:
    return QueryPreprocessor()


def test_input_validation_empty_and_invalid(preprocessor: QueryPreprocessor) -> None:
    """Verifies that invalid, empty, or whitespace-only inputs raise ValueError."""
    with pytest.raises(ValueError, match="cannot be None"):
        preprocessor.preprocess(None)

    with pytest.raises(ValueError, match="must be a string"):
        preprocessor.preprocess(12345)

    with pytest.raises(ValueError, match="cannot be empty or whitespace"):
        preprocessor.preprocess("")

    with pytest.raises(ValueError, match="cannot be empty or whitespace"):
        preprocessor.preprocess("   \t\n  ")


def test_unicode_normalization_and_clean_controls(preprocessor: QueryPreprocessor) -> None:
    """Verifies Unicode NFKC normalization and control character removal."""
    # Control character \x07 (bell) and zero-width space \u200b
    raw_query = "What is\x07 BM25\u200b ranking?"
    result = preprocessor.preprocess(raw_query)
    assert "\x07" not in result.sanitized_text
    assert "\u200b" not in result.sanitized_text
    assert result.sanitized_text == "What is BM25 ranking?"


def test_smart_quotes_and_dashes_normalization(preprocessor: QueryPreprocessor) -> None:
    """Verifies typographic smart quotes and em/en dashes are normalized."""
    raw_query = '“Explain” ‘overfitting’ – dynamic range'
    result = preprocessor.preprocess(raw_query)
    assert '"Explain"' in result.sanitized_text
    assert "'overfitting'" in result.sanitized_text
    assert "-" in result.sanitized_text


def test_whitespace_collapsing(preprocessor: QueryPreprocessor) -> None:
    """Verifies multiple spaces, newlines, and tabs are collapsed."""
    raw_query = "   How   does \t\t gradient \n\n descent \n work?   "
    result = preprocessor.preprocess(raw_query)
    assert result.sanitized_text == "How does gradient descent work?"


def test_sensitive_data_redaction(preprocessor: QueryPreprocessor) -> None:
    """Verifies emails, phone numbers, API keys, and passwords are safely redacted."""
    # Email redaction
    res_email = preprocessor.preprocess("Contact author at user.name@university.edu for the code")
    assert res_email.was_redacted is True
    assert "[EMAIL]" in res_email.sanitized_text
    assert "user.name@university.edu" not in res_email.sanitized_text

    # Phone redaction
    res_phone = preprocessor.preprocess("Call the research office at 555-123-4567")
    assert res_phone.was_redacted is True
    assert "[PHONE]" in res_phone.sanitized_text
    assert "555-123-4567" not in res_phone.sanitized_text

    # API key redaction
    res_key = preprocessor.preprocess("Using key sk-1234567890abcdef123456 to access server")
    assert res_key.was_redacted is True
    assert "[API_KEY]" in res_key.sanitized_text
    assert "sk-1234567890abcdef123456" not in res_key.sanitized_text

    # Password pattern redaction
    res_pwd = preprocessor.preprocess("Connect with password: Secret123Password to postgres")
    assert res_pwd.was_redacted is True
    assert "[TOKEN]" in res_pwd.sanitized_text


def test_prompt_technical_examples_preservation(preprocessor: QueryPreprocessor) -> None:
    """Verifies that all 12 specific technical test cases from the specification preserve their tokens."""
    test_cases = [
        ("What is BM25?", ["what", "is", "bm25"]),
        ("Difference between TF-IDF and BM25?", ["difference", "between", "tf-idf", "and", "bm25"]),
        ("How does C++ memory management work?", ["how", "does", "c++", "memory", "management", "work"]),
        ("Explain TCP/IP.", ["explain", "tcp/ip"]),
        ("Compare PostgreSQL and MySQL.", ["compare", "postgresql", "and", "mysql"]),
        ("Why does overfitting occur?", ["why", "does", "overfitting", "occur"]),
        ("Summarize the uploaded research papers.", ["summarize", "the", "uploaded", "research", "papers"]),
        ("Where does the document mention SVM?", ["where", "does", "the", "document", "mention", "svm"]),
        ("What are the advantages of K-Means?", ["what", "are", "the", "advantages", "of", "k-means"]),
        ("How do I implement RAG using FastAPI?", ["how", "do", "i", "implement", "rag", "using", "fastapi"]),
        ("Show me all the evaluation metrics.", ["show", "me", "all", "the", "evaluation", "metrics"]),
        ("GPT-4 vs GPT-4o", ["gpt-4", "vs", "gpt-4o"]),
    ]

    for raw_query, expected_tokens in test_cases:
        result = preprocessor.preprocess(raw_query)
        assert isinstance(result, PreprocessedQuery)
        for expected_tok in expected_tokens:
            assert expected_tok in result.normalized_text.split(), (
                f"Expected token '{expected_tok}' missing from normalized output '{result.normalized_text}' "
                f"for query '{raw_query}'"
            )


def test_stopword_retention(preprocessor: QueryPreprocessor) -> None:
    """Verifies that intent-bearing question words are strictly NOT deleted."""
    query = "Why and how does cross-entropy loss optimize predictions?"
    result = preprocessor.preprocess(query)
    tokens = result.normalized_text.split()
    assert "why" in tokens
    assert "and" in tokens
    assert "how" in tokens
    assert "does" in tokens


def test_length_truncation_flag() -> None:
    """Verifies that queries exceeding max_length are truncated and flagged."""
    short_limit_preprocessor = QueryPreprocessor(max_length=20)
    long_query = "This is a long query that clearly exceeds twenty characters"
    result = short_limit_preprocessor.preprocess(long_query)
    assert result.was_truncated is True
    assert len(result.sanitized_text) <= 20


def test_deterministic_preprocessing(preprocessor: QueryPreprocessor) -> None:
    """Verifies that preprocessing is completely deterministic."""
    query = "How does C++ TCP/IP client interact with PostgreSQL server?"
    res1 = preprocessor.preprocess(query)
    res2 = preprocessor.preprocess(query)
    assert res1.sanitized_text == res2.sanitized_text
    assert res1.normalized_text == res2.normalized_text
    assert res1.was_redacted == res2.was_redacted
    assert res1.preprocessing_version == PREPROCESSING_VERSION
