"""Overlap management between adjacent semantic chunks."""

from typing import List, Optional

from backend.app.ingestion.chunking.token_counter import TokenCounter


class OverlapManager:
    """Extracts sentence-bounded overlap from the end of a previous chunk to preserve context."""

    def __init__(self, target_overlap_tokens: int = 75, token_counter: Optional[TokenCounter] = None) -> None:
        from backend.app.ingestion.chunking.token_counter import EstimateTokenCounter

        self.target_overlap_tokens = target_overlap_tokens
        self.token_counter = token_counter or EstimateTokenCounter()

    def get_sentence_overlap(
        self,
        sentences: List[str],
        previous_section: Optional[str] = None,
        next_section: Optional[str] = None,
    ) -> str:
        """Selects trailing sentences from previous chunk up to target_overlap_tokens.

        Resets overlap if previous_section and next_section are distinctly different major sections.
        """
        if not sentences or self.target_overlap_tokens <= 0:
            return ""

        # If sections differ substantially, do not bleed context across section boundaries
        if previous_section and next_section and previous_section != next_section:
            return ""

        overlap_sentences: List[str] = []
        accumulated_tokens = 0

        # Traverse sentences backwards from end of chunk
        for s in reversed(sentences):
            s_tokens = self.token_counter.count_tokens(s)
            if accumulated_tokens + s_tokens > self.target_overlap_tokens and overlap_sentences:
                break

            overlap_sentences.insert(0, s)
            accumulated_tokens += s_tokens

            if accumulated_tokens >= self.target_overlap_tokens:
                break

        return " ".join(overlap_sentences).strip()
