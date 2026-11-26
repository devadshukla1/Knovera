"""Schemas for Knovera Semantic Vector Retrieval (Phase 3 C3.3)."""

from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class SemanticSearchRequest(BaseModel):
    """Input payload for semantic vector search."""

    query: str = Field(..., min_length=1, max_length=1000, description="Natural language search query")
    document_ids: Optional[List[uuid.UUID]] = Field(None, description="Optional document filter within workspace")
    top_k: int = Field(default=10, ge=1, le=50, description="Maximum number of chunks to retrieve")


class SemanticSearchResult(BaseModel):
    """Ranked evidence chunk with authoritative PostgreSQL content and source provenance."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    workspace_id: uuid.UUID
    document_filename: str
    content: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    slide_number: Optional[int] = None
    section_title: Optional[str] = None
    source_segments: List[Dict[str, Any]] = Field(default_factory=list)
    distance: float = Field(..., description="Chroma cosine distance (lower is more similar)")
    rank: int = Field(..., ge=1, description="1-based retrieval ranking order")
    embedding_model: str
    embedding_revision: str


class SemanticSearchResponse(BaseModel):
    """Complete response container for semantic search query."""

    workspace_id: uuid.UUID
    query: str
    total_results: int
    results: List[SemanticSearchResult]
    duration_metrics: Dict[str, float] = Field(default_factory=dict)


class BM25SearchRequest(BaseModel):
    """Input payload for BM25 lexical keyword search."""

    query: str = Field(..., min_length=1, max_length=1000, description="Keyword search query")
    document_ids: Optional[List[uuid.UUID]] = Field(None, description="Optional document filter within workspace")
    top_k: int = Field(default=10, ge=1, le=50, description="Maximum number of chunks to retrieve")


class BM25SearchResult(BaseModel):
    """Lexically ranked evidence chunk with BM25 Okapi score and PostgreSQL provenance."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    workspace_id: uuid.UUID
    document_filename: str
    content: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    slide_number: Optional[int] = None
    section_title: Optional[str] = None
    source_segments: List[Dict[str, Any]] = Field(default_factory=list)
    bm25_score: float = Field(..., description="BM25 Okapi score (higher is more relevant)")
    rank: int = Field(..., ge=1, description="1-based BM25 ranking order")
    distance: float = Field(default=0.0, description="Compatibility alias for ContextBuilder")
    embedding_model: str = "bm25_okapi"
    embedding_revision: str = "v1"


class BM25SearchResponse(BaseModel):
    """Response container for BM25 lexical search query."""

    workspace_id: uuid.UUID
    query: str
    total_results: int
    results: List[BM25SearchResult]
    duration_metrics: Dict[str, float] = Field(default_factory=dict)


class HybridSearchRequest(BaseModel):
    """Input payload for hybrid (dense + BM25) retrieval."""

    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    document_ids: Optional[List[uuid.UUID]] = Field(None, description="Optional document filter within workspace")
    top_k: int = Field(default=10, ge=1, le=50, description="Maximum fused candidates to return")
    mode: str = Field(default="hybrid", description="Retrieval mode: 'hybrid', 'semantic', or 'bm25'")
    rerank: Optional[bool] = Field(default=None, description="Whether to apply Cross-Encoder reranking (defaults to RERANKER_ENABLED)")


class HybridSearchResult(BaseModel):
    """Fused evidence chunk combining dense semantic and BM25 lexical rankings via RRF and optional Cross-Encoder reranking."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    workspace_id: uuid.UUID
    document_filename: str
    content: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    slide_number: Optional[int] = None
    section_title: Optional[str] = None
    source_segments: List[Dict[str, Any]] = Field(default_factory=list)
    rrf_score: float = Field(..., description="Reciprocal Rank Fusion score")
    rank: int = Field(..., ge=1, description="1-based effective ranking order (reranked if reranker ran, else RRF rank)")
    dense_rank: Optional[int] = Field(None, description="1-based rank in dense retrieval if present")
    bm25_rank: Optional[int] = Field(None, description="1-based rank in BM25 retrieval if present")
    vector_distance: Optional[float] = Field(None, description="Chroma cosine distance if present")
    bm25_score: Optional[float] = Field(None, description="BM25 Okapi score if present")
    reranker_score: Optional[float] = Field(None, description="Cross-Encoder raw logit relevance score if reranked")
    reranker_rank: Optional[int] = Field(None, description="1-based rank after Cross-Encoder reranking if performed")
    retrieval_sources: List[str] = Field(default_factory=list, description="Retrievers that found chunk (e.g. ['semantic', 'bm25'])")
    distance: float = Field(default=0.0, description="Compatibility distance for ContextBuilder")
    embedding_model: str = "hybrid_rrf"
    embedding_revision: str = "v1"


class HybridSearchResponse(BaseModel):
    """Response container for hybrid search query."""

    workspace_id: uuid.UUID
    query: str
    mode: str = "hybrid"
    reranked: bool = False
    total_results: int
    results: List[HybridSearchResult]
    candidate_results: Optional[List[HybridSearchResult]] = Field(
        None,
        description="Pre-reranking candidate pool before reranker filtering (for candidate-stage recall evaluation)",
    )
    duration_metrics: Dict[str, float] = Field(default_factory=dict)
