"""Evidence selection adhering to diversity and token budget constraints (Phase 3 C3.5)."""

from typing import Dict, List, Tuple
import uuid

from backend.app.rag.context.token_budget import estimate_tokens
from backend.app.rag.retrieval.schemas import SemanticSearchResult


class EvidenceSelector:
    """Selects top-ranked evidence subject to diversity and token budget boundaries."""

    def __init__(
        self,
        max_chunks: int = 8,
        max_chunks_per_document: int = 4,
    ) -> None:
        self.max_chunks = max_chunks
        self.max_chunks_per_document = max_chunks_per_document

    def select(
        self,
        candidates: List[SemanticSearchResult],
        evidence_token_budget: int,
    ) -> Tuple[List[Tuple[SemanticSearchResult, bool]], int]:
        """Selects candidates while enforcing per-document diversity and total token budget.

        Returns:
            Tuple of list[(selected_result, is_truncated)], omitted_count.
        """
        selected: List[Tuple[SemanticSearchResult, bool]] = []
        doc_counts: Dict[uuid.UUID, int] = {}
        tokens_used = 0
        omitted_count = 0

        for candidate in candidates:
            if len(selected) >= self.max_chunks:
                omitted_count += 1
                continue

            # Diversity enforcement
            current_doc_count = doc_counts.get(candidate.document_id, 0)
            if current_doc_count >= self.max_chunks_per_document:
                omitted_count += 1
                continue

            chunk_tokens = estimate_tokens(candidate.content)

            # Check if chunk fits fully within remaining budget
            if tokens_used + chunk_tokens <= evidence_token_budget:
                selected.append((candidate, False))
                tokens_used += chunk_tokens
                doc_counts[candidate.document_id] = current_doc_count + 1
            elif evidence_token_budget - tokens_used >= 60:
                # If at least 60 tokens remain, excerpt at sentence boundary
                remaining_tokens = evidence_token_budget - tokens_used
                approx_char_budget = remaining_tokens * 3

                # Attempt sentence truncation
                content = candidate.content
                truncated_text = content[:approx_char_budget]
                last_period = truncated_text.rfind(".")
                if last_period > 40:
                    truncated_text = truncated_text[: last_period + 1]

                # Update candidate content with truncated text
                truncated_candidate = candidate.model_copy(update={"content": truncated_text})
                selected.append((truncated_candidate, True))
                tokens_used += estimate_tokens(truncated_text)
                doc_counts[candidate.document_id] = current_doc_count + 1
                break  # Budget exhausted
            else:
                omitted_count += 1

        return selected, omitted_count
