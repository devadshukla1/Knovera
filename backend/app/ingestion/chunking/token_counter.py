"""Token counting abstraction and estimation engines for Knovera."""

from abc import ABC, abstractmethod
import math
import re


class TokenCounter(ABC):
    """Abstract interface for calculating token counts for chunks and budgets."""

    @property
    @abstractmethod
    def method_name(self) -> str:
        """Name/version of the token counting method."""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Returns the number of tokens in the supplied text."""
        pass


class EstimateTokenCounter(TokenCounter):
    """Lightweight, zero-dependency token count estimator.

    Uses an empirical formula combining word-token ratios and character length
    (~1 token per 4 characters / ~1.3 tokens per whitespace-delimited word),
    accounting for punctuation and code tokens.
    """

    def __init__(self, method_name: str = "estimate_v1") -> None:
        self._method_name = method_name
        self._word_regex = re.compile(r"\S+")

    @property
    def method_name(self) -> str:
        return self._method_name

    def count_tokens(self, text: str) -> int:
        if not text or not text.strip():
            return 0

        # Strip whitespace for length
        clean_text = text.strip()
        char_len = len(clean_text)

        # Count whitespace-separated tokens
        words = self._word_regex.findall(clean_text)
        word_count = len(words)

        # Standard heuristic: max of (chars / 4) and (words * 1.25)
        by_chars = char_len / 4.0
        by_words = word_count * 1.25

        estimated = math.ceil(max(by_chars, by_words))
        return max(1, estimated)
