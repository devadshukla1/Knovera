"""Knovera Hybrid & Vector Retrieval Module (Phase 3 C3.3, Phase 4 C4.1–C4.3)."""

from backend.app.rag.retrieval.bm25.retriever import BM25Retriever
from backend.app.rag.retrieval.exceptions import (
    DocumentScopeException,
    InvalidQueryException,
    RetrievalException,
)
from backend.app.rag.retrieval.hybrid_retriever import HybridRetriever
from backend.app.rag.retrieval.query_validator import QueryValidator
from backend.app.rag.retrieval.result_hydrator import ResultHydrator
from backend.app.rag.retrieval.rrf import FusedCandidate, ReciprocalRankFusion
from backend.app.rag.retrieval.schemas import (
    BM25SearchRequest,
    BM25SearchResponse,
    BM25SearchResult,
    HybridSearchRequest,
    HybridSearchResponse,
    HybridSearchResult,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResult,
)
from backend.app.rag.retrieval.semantic_retriever import SemanticRetriever

__all__ = [
    "SemanticRetriever",
    "BM25Retriever",
    "HybridRetriever",
    "ReciprocalRankFusion",
    "FusedCandidate",
    "QueryValidator",
    "ResultHydrator",
    "SemanticSearchRequest",
    "SemanticSearchResult",
    "SemanticSearchResponse",
    "BM25SearchRequest",
    "BM25SearchResult",
    "BM25SearchResponse",
    "HybridSearchRequest",
    "HybridSearchResult",
    "HybridSearchResponse",
    "RetrievalException",
    "InvalidQueryException",
    "DocumentScopeException",
]
