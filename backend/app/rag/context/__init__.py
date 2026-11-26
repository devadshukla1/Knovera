"""Knovera Context Construction Package (Phase 3 C3.5)."""

from backend.app.rag.context.builder import ContextBuilder
from backend.app.rag.context.deduplicator import EvidenceDeduplicator
from backend.app.rag.context.exceptions import (
    ContextBudgetExceededError,
    ContextBuilderException,
    ContextScopeError,
)
from backend.app.rag.context.schemas import ContextPackage, ContextSource
from backend.app.rag.context.selector import EvidenceSelector
from backend.app.rag.context.source_formatter import SourceFormatter
from backend.app.rag.context.token_budget import TokenBudgetCalculator, estimate_tokens

__all__ = [
    "ContextBudgetExceededError",
    "ContextBuilder",
    "ContextBuilderException",
    "ContextPackage",
    "ContextScopeError",
    "ContextSource",
    "EvidenceDeduplicator",
    "EvidenceSelector",
    "SourceFormatter",
    "TokenBudgetCalculator",
    "estimate_tokens",
]
