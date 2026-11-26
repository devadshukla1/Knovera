"""Token estimation heuristics and context-window budgeting (Phase 3 C3.5)."""

import math
from typing import Optional

from backend.app.rag.context.exceptions import ContextBudgetExceededError


def estimate_tokens(text: Optional[str]) -> int:
    """Estimates token count conservatively without requiring external tokenizer weights.

    Formula combines character count (approx 3.8 chars/token) and whitespace words
    (approx 1.3 tokens/word), taking the conservative maximum plus 1 to prevent underestimation.
    """
    if not text or not text.strip():
        return 0

    clean_text = text.strip()
    char_estimate = math.ceil(len(clean_text) / 3.8)
    word_estimate = math.ceil(len(clean_text.split()) * 1.35)

    return max(char_estimate, word_estimate, 1)


class TokenBudgetCalculator:
    """Calculates available input token budget for evidence chunk selection."""

    def __init__(self, safety_margin_tokens: int = 250) -> None:
        self.safety_margin = safety_margin_tokens

    def calculate_evidence_budget(
        self,
        max_context_tokens: int,
        reserved_output_tokens: int,
        system_prompt_tokens: int,
        query_tokens: int,
        history_tokens: int = 0,
    ) -> int:
        """Calculates net remaining tokens available strictly for document evidence.

        Formula:
            Available Evidence Budget =
                Max Context Window
                - System/Instruction Tokens
                - User Query Tokens
                - Conversation History Tokens
                - Reserved Output Tokens
                - Safety Margin
        """
        fixed_overhead = (
            system_prompt_tokens
            + query_tokens
            + history_tokens
            + reserved_output_tokens
            + self.safety_margin
        )

        available = max_context_tokens - fixed_overhead
        if available <= 0:
            raise ContextBudgetExceededError(
                f"Fixed prompt requirements ({fixed_overhead} tokens) exceed total model context window ({max_context_tokens} tokens)"
            )

        return available
