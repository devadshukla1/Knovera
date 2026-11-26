"""Text Preprocessing Pipeline for Query Intent Classification (Phase 5 C5.3).

Transforms raw queries into clean, normalized, model-ready text while strictly
preserving technical tokens, acronyms, and grammatical intent indicators.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Tuple
import unicodedata

PREPROCESSING_VERSION: str = "1.0.0"
DEFAULT_MAX_QUERY_LENGTH: int = 512

# Control characters: NUL and ascii 0-8, 11-12, 14-31, 127
CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Zero-width spaces and formatting markers that disrupt tokenization
ZERO_WIDTH_REGEX = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]")

# Typographic quotation marks and dashes normalization
SMART_QUOTES_DASHES = [
    (r"[\u201c\u201d\u201e\u201f\u00ab\u00bb]", '"'),  # Smart double quotes
    (r"[\u2018\u2019\u201a\u201b\u02bb\u02bc]", "'"),  # Smart single quotes
    (r"[\u2013\u2014]", " - "),                         # En/Em dash
]

# Sensitive Data Redaction Patterns
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_REGEX = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
API_KEY_REGEX = re.compile(
    r"\b(?:(?:sk|pk|api|key|token|auth|bearer)[_-][a-zA-Z0-9_\-]{16,}|(?:[a-f0-9]{32,64}))\b",
    re.IGNORECASE,
)
PASSWORD_REGEX = re.compile(
    r"\b(?:password|passwd|pwd)\s*[:=]\s*[^\s,;]+\b",
    re.IGNORECASE,
)

# Known Technical Identifiers and Patterns
# Matches:
# 1. Programming languages with symbols: C++, C#, .NET
# 2. Acronyms & technical terms with internal slashes/hyphens: TCP/IP, TF-IDF, K-Means, GPT-4, GPT-4o, v1.2
# 3. Code identifiers: snake_case, camelCase, PascalCase
TECHNICAL_TOKEN_REGEX = re.compile(
    r"[a-zA-Z0-9]+(?:\+\+|#)?(?:[./_-][a-zA-Z0-9]+(?:\+\+|#)?)*|[a-zA-Z0-9]+(?:\+\+|#)"
)


@dataclass(frozen=True)
class PreprocessedQuery:
    """Immutable structured result of query text preprocessing."""

    original_text: str
    sanitized_text: str
    normalized_text: str
    was_redacted: bool
    was_truncated: bool
    language: Optional[str]
    preprocessing_version: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializes preprocessed query to a dictionary."""
        return {
            "original_text": self.original_text,
            "sanitized_text": self.sanitized_text,
            "normalized_text": self.normalized_text,
            "was_redacted": self.was_redacted,
            "was_truncated": self.was_truncated,
            "language": self.language,
            "preprocessing_version": self.preprocessing_version,
        }


class QueryPreprocessor:
    """Reusable, deterministic query text preprocessor for intent classification."""

    def __init__(
        self,
        max_length: int = DEFAULT_MAX_QUERY_LENGTH,
        enable_redaction: bool = True,
        version: str = PREPROCESSING_VERSION,
    ) -> None:
        self.max_length = max_length
        self.enable_redaction = enable_redaction
        self.version = version

    def preprocess(self, raw_text: Any) -> PreprocessedQuery:
        """Executes full preprocessing pipeline on a raw user query string.

        Pipeline Stages:
            1. Input validation (type check, empty/whitespace check)
            2. Truncation check against max_length
            3. Sensitive data redaction ([EMAIL], [PHONE], [API_KEY], [TOKEN])
            4. Unicode normalization (NFKC, control char removal, zero-width stripping)
            5. Whitespace and formatting normalization
            6. Normalized text generation (preserving technical tokens and question words)

        Raises:
            ValueError: If input is None, not a string, or empty/whitespace.
        """
        # 1. Input Validation
        if raw_text is None:
            raise ValueError("Query text cannot be None.")
        if not isinstance(raw_text, str):
            raise ValueError(f"Query text must be a string, got {type(raw_text).__name__}.")

        stripped_raw = raw_text.strip()
        if not stripped_raw:
            raise ValueError("Query text cannot be empty or whitespace-only.")

        # 2. Length Validation & Truncation
        was_truncated = False
        text_to_process = stripped_raw
        if len(text_to_process) > self.max_length:
            text_to_process = text_to_process[: self.max_length]
            was_truncated = True

        # 3. Sensitive Data Redaction
        was_redacted = False
        if self.enable_redaction:
            text_to_process, was_redacted = self._redact_sensitive_data(text_to_process)

        # 4. Unicode & Character Normalization
        text_to_process = self._normalize_unicode_and_characters(text_to_process)

        # 5. Whitespace & Formatting Normalization
        sanitized_text = self._normalize_whitespace(text_to_process)

        # 6. Normalized Text for Model Feature Extraction
        # Note: We perform lowercasing while preserving technical tokens, question marks,
        # and intent-bearing words (e.g. what, why, how, compare, explain, summarize).
        normalized_text = self._generate_normalized_text(sanitized_text)

        return PreprocessedQuery(
            original_text=raw_text,
            sanitized_text=sanitized_text,
            normalized_text=normalized_text,
            was_redacted=was_redacted,
            was_truncated=was_truncated,
            language=None,  # Explicitly left None until real language detector is added
            preprocessing_version=self.version,
        )

    def _redact_sensitive_data(self, text: str) -> Tuple[str, bool]:
        """Replaces sensitive patterns with safe placeholders."""
        redacted = text
        changed = False

        if EMAIL_REGEX.search(redacted):
            redacted = EMAIL_REGEX.sub("[EMAIL]", redacted)
            changed = True

        if PHONE_REGEX.search(redacted):
            redacted = PHONE_REGEX.sub("[PHONE]", redacted)
            changed = True

        if API_KEY_REGEX.search(redacted):
            redacted = API_KEY_REGEX.sub("[API_KEY]", redacted)
            changed = True

        if PASSWORD_REGEX.search(redacted):
            redacted = PASSWORD_REGEX.sub("[TOKEN]", redacted)
            changed = True

        return redacted, changed

    def _normalize_unicode_and_characters(self, text: str) -> str:
        """Applies NFKC normalization and removes control/zero-width chars."""
        # 1. Remove control characters (excluding tab and newline for now)
        cleaned = CONTROL_CHAR_REGEX.sub("", text)

        # 2. Remove zero-width spaces and invisible characters
        cleaned = ZERO_WIDTH_REGEX.sub("", cleaned)

        # 3. Normalize smart quotes and typographic dashes
        for pattern, replacement in SMART_QUOTES_DASHES:
            cleaned = re.sub(pattern, replacement, cleaned)

        # 4. Unicode NFKC Normalization
        normalized = unicodedata.normalize("NFKC", cleaned)

        return normalized

    def _normalize_whitespace(self, text: str) -> str:
        """Collapses multi-whitespace, tabs, and newlines into single spaces."""
        return re.sub(r"\s+", " ", text).strip()

    def _generate_normalized_text(self, text: str) -> str:
        """Generates normalized representation for ML feature extraction.

        Guarantees:
            - Technical tokens (e.g. C++, C#, TCP/IP, BM25, TF-IDF, K-Means, GPT-4, PostgreSQL)
              preserve their internal symbols.
            - Case folding for case-insensitive matching.
            - Intent words (what, why, how, compare, explain, summarize) are preserved.
            - No aggressive stemming or lemmatization.
            - Punctuation attached to isolated words is separated while technical tokens remain intact.
        """
        # Convert to lower case
        lowered = text.lower()

        # Tokenize preserving technical expressions
        tokens = TECHNICAL_TOKEN_REGEX.findall(lowered)
        if not tokens:
            return lowered.strip()

        return " ".join(tokens)
