"""Dedicated Lexical Tokenizer & Preprocessor for BM25 (Phase 4 C4.1)."""

import re
from typing import List
import unicodedata

# Token regex pattern designed to capture:
# 1. Technical identifiers with symbols (e.g. C++, C#, TCP/IP, GPT-4, v1.2, api_key)
# 2. Words, alphanumeric identifiers, and numbers
# Preserves internal dots, slashes, dashes, underscores, and trailing ++/#.
TOKEN_PATTERN = re.compile(
    r"[a-zA-Z0-9]+(?:\+\+|#)?(?:[./_-][a-zA-Z0-9]+(?:\+\+|#)?)*|[a-zA-Z0-9]+(?:\+\+|#)"
)


class BM25Tokenizer:
    """Dedicated lexical tokenizer that normalizes text and preserves technical terminology."""

    def __init__(self) -> None:
        self.pattern = TOKEN_PATTERN

    def tokenize(self, text: str) -> List[str]:
        """Normalizes and tokenizes text into case-folded lexical tokens.

        Guarantees:
            - Consistent Unicode NFKC normalization.
            - Case folding for case-insensitive lexical matching.
            - Preservation of technical acronyms, compound terms, and programming languages (e.g., C++, C#, TCP/IP, GPT-4).
            - Accurate retention of repeated term counts.
            - No aggressive language-specific stemming.
            - No automatic stopword deletion.
        """
        if not text:
            return []

        # 1. Normalize Unicode (NFKC)
        normalized = unicodedata.normalize("NFKC", text)

        # 2. Case fold
        folded = normalized.lower()

        # 3. Extract tokens matching technical identifier pattern
        tokens = self.pattern.findall(folded)
        return tokens
