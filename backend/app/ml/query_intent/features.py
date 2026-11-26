"""TF-IDF Feature Extraction Pipeline for Knovera Query Intent Classification (Phase 5 C5.4).

Provides configurable word-level, character-level, and combined TF-IDF feature extractors
with strict technical terminology preservation, sparse representations, and data leakage protection.
"""

from dataclasses import dataclass
import time
from typing import Any, Dict, List, Literal, Optional, Tuple
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion

from backend.app.core.config import get_settings

# Regex pattern capturing technical identifiers, programming languages, acronyms, and alphanumeric terms
TECHNICAL_TOKEN_PATTERN: str = (
    r"[a-zA-Z0-9]+(?:\+\+|#)?(?:[./_-][a-zA-Z0-9]+(?:\+\+|#)?)*|[a-zA-Z0-9]+(?:\+\+|#)"
)

FeatureType = Literal["word", "char", "combined"]


@dataclass(frozen=True)
class FeatureExtractionStats:
    """Statistical summary of an extracted TF-IDF feature matrix."""

    feature_type: str
    sample_count: int
    total_features: int
    word_vocabulary_size: int
    char_vocabulary_size: int
    matrix_shape: Tuple[int, int]
    non_zero_count: int
    density: float
    duration_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        """Serializes statistics to dictionary."""
        return {
            "feature_type": self.feature_type,
            "sample_count": self.sample_count,
            "total_features": self.total_features,
            "word_vocabulary_size": self.word_vocabulary_size,
            "char_vocabulary_size": self.char_vocabulary_size,
            "matrix_shape": list(self.matrix_shape),
            "non_zero_count": self.non_zero_count,
            "density": round(self.density, 6),
            "duration_seconds": round(self.duration_seconds, 4),
        }


def build_word_vectorizer(
    ngram_range: Optional[Tuple[int, int]] = None,
    max_features: Optional[int] = None,
    min_df: int = 1,
    sublinear_tf: bool = True,
    token_pattern: str = TECHNICAL_TOKEN_PATTERN,
) -> TfidfVectorizer:
    """Builds a word-level TF-IDF vectorizer that preserves technical identifiers and question phrasing.

    Args:
        ngram_range: Tuple of (min_n, max_n) for word n-grams (default from settings: (1, 2)).
        max_features: Max vocabulary size (default from settings: 50,000).
        min_df: Minimum document frequency threshold (default 1 for small datasets).
        sublinear_tf: Whether to apply sub-linear term frequency scaling 1 + log(tf).
        token_pattern: Regex pattern matching technical identifiers with symbols.
    """
    settings = get_settings()
    if ngram_range is None:
        ngram_range = (
            settings.QUERY_INTENT_WORD_NGRAM_MIN,
            settings.QUERY_INTENT_WORD_NGRAM_MAX,
        )
    if max_features is None:
        max_features = settings.QUERY_INTENT_WORD_MAX_FEATURES

    return TfidfVectorizer(
        analyzer="word",
        ngram_range=ngram_range,
        max_features=max_features,
        min_df=min_df,
        token_pattern=token_pattern,
        lowercase=True,
        stop_words=None,  # Do not remove question/intent words (what, why, how, compare, etc.)
        sublinear_tf=sublinear_tf,
        use_idf=True,
        smooth_idf=True,
        norm="l2",
    )


def build_char_vectorizer(
    ngram_range: Optional[Tuple[int, int]] = None,
    max_features: Optional[int] = None,
    min_df: int = 1,
    sublinear_tf: bool = True,
) -> TfidfVectorizer:
    """Builds a character-level TF-IDF vectorizer (char_wb) for capturing sub-words and abbreviations.

    Args:
        ngram_range: Tuple of (min_n, max_n) for character n-grams (default: (3, 5)).
        max_features: Max vocabulary size (default: 100,000).
        min_df: Minimum document frequency threshold.
        sublinear_tf: Sublinear term frequency scaling.
    """
    settings = get_settings()
    if ngram_range is None:
        ngram_range = (
            settings.QUERY_INTENT_CHAR_NGRAM_MIN,
            settings.QUERY_INTENT_CHAR_NGRAM_MAX,
        )
    if max_features is None:
        max_features = settings.QUERY_INTENT_CHAR_MAX_FEATURES

    return TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=ngram_range,
        max_features=max_features,
        min_df=min_df,
        lowercase=True,
        sublinear_tf=sublinear_tf,
        use_idf=True,
        smooth_idf=True,
        norm="l2",
    )


def build_feature_pipeline(
    feature_type: FeatureType = "combined",
    word_ngram_range: Optional[Tuple[int, int]] = None,
    char_ngram_range: Optional[Tuple[int, int]] = None,
    word_max_features: Optional[int] = None,
    char_max_features: Optional[int] = None,
    word_weight: float = 1.0,
    char_weight: float = 1.0,
) -> Any:
    """Builds a scikit-learn feature extraction transformer pipeline.

    Supports:
        - "word": Word-level TF-IDF alone.
        - "char": Character-level TF-IDF alone.
        - "combined": FeatureUnion of word and character TF-IDF representations.
    """
    word_vec = build_word_vectorizer(
        ngram_range=word_ngram_range,
        max_features=word_max_features,
    )

    char_vec = build_char_vectorizer(
        ngram_range=char_ngram_range,
        max_features=char_max_features,
    )

    if feature_type == "word":
        return word_vec
    elif feature_type == "char":
        return char_vec
    elif feature_type == "combined":
        return FeatureUnion(
            transformer_list=[
                ("word", word_vec),
                ("char", char_vec),
            ],
            transformer_weights={
                "word": word_weight,
                "char": char_weight,
            },
        )
    else:
        raise ValueError(
            f"Unsupported feature_type '{feature_type}'. Must be 'word', 'char', or 'combined'."
        )


def compute_feature_stats(
    feature_pipeline: Any,
    feature_matrix: sp.spmatrix,
    feature_type: str,
    duration_seconds: float,
) -> FeatureExtractionStats:
    """Extracts vocabulary sizes and sparsity statistics from a fitted feature pipeline and matrix."""
    sample_count, total_features = feature_matrix.shape
    word_vocab_size = 0
    char_vocab_size = 0

    if isinstance(feature_pipeline, FeatureUnion):
        for name, transformer in feature_pipeline.transformer_list:
            if name == "word" and hasattr(transformer, "vocabulary_"):
                word_vocab_size = len(transformer.vocabulary_)
            elif name == "char" and hasattr(transformer, "vocabulary_"):
                char_vocab_size = len(transformer.vocabulary_)
    elif isinstance(feature_pipeline, TfidfVectorizer):
        if feature_pipeline.analyzer == "word" and hasattr(feature_pipeline, "vocabulary_"):
            word_vocab_size = len(feature_pipeline.vocabulary_)
        elif feature_pipeline.analyzer == "char_wb" and hasattr(feature_pipeline, "vocabulary_"):
            char_vocab_size = len(feature_pipeline.vocabulary_)

    non_zero = feature_matrix.nnz
    total_elements = sample_count * total_features
    density = (non_zero / total_elements) if total_elements > 0 else 0.0

    return FeatureExtractionStats(
        feature_type=feature_type,
        sample_count=sample_count,
        total_features=total_features,
        word_vocabulary_size=word_vocab_size,
        char_vocabulary_size=char_vocab_size,
        matrix_shape=(sample_count, total_features),
        non_zero_count=non_zero,
        density=density,
        duration_seconds=duration_seconds,
    )
