"""Pydantic schemas for Topic Discovery API (Phase 6 C6.7)."""

from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class TopicKeyword(BaseModel):
    """Ranked keyword or keyphrase extracted for a cluster."""

    model_config = ConfigDict(frozen=True)

    term: str = Field(..., description="Key term or n-gram extracted from cluster content")
    score: float = Field(..., description="c-TF-IDF or keyphrase relevance score")


class TopicRunSummary(BaseModel):
    """Summary of a persistent topic clustering run."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="UUID of the clustering run")
    workspace_id: str = Field(..., description="UUID of the workspace")
    snapshot_id: str = Field(..., description="Corpus snapshot identifier")
    status: str = Field(..., description="Execution status (e.g. 'completed', 'running', 'failed')")
    k: int = Field(..., description="Number of discovered clusters/topics")
    model_version: str = Field(..., description="Version of the model or algorithm")
    is_active: bool = Field(..., description="Whether this is the currently active run for the workspace")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    completed_at: Optional[str] = Field(None, description="ISO 8601 completion timestamp")
    topic_count: Optional[int] = Field(None, description="Number of topics associated with this run")
    total_assignments: Optional[int] = Field(None, description="Total number of chunks assigned in this run")


class TopicSummaryItem(BaseModel):
    """Topic card summary representation for topic explorer list."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="UUID of the topic")
    workspace_id: str = Field(..., description="UUID of the workspace")
    clustering_run_id: str = Field(..., description="UUID of parent clustering run")
    cluster_key: str = Field(..., description="Cluster identifier, e.g. 'cluster_0'")
    label: str = Field(..., description="Descriptive human-readable topic label")
    description: Optional[str] = Field(None, description="Detailed synthesis or topic description")
    label_source: str = Field(..., description="Provenance: 'keyword_based', 'llm_assisted', 'human_reviewed'")
    label_status: str = Field(..., description="Validation status: 'suggested', 'reviewed', 'approved', 'needs_review'")
    keywords: List[TopicKeyword] = Field(default_factory=list, description="Top ranked keywords for this topic")
    chunk_count: int = Field(default=0, description="Total active document chunks assigned to this topic")
    document_count: int = Field(default=0, description="Count of distinct active documents contributing to this topic")
    representative_chunk_ids: List[str] = Field(default_factory=list, description="IDs of representative centroid chunks")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    updated_at: str = Field(..., description="ISO 8601 last update timestamp")


class PaginatedTopicsResponse(BaseModel):
    """Paginated topic explorer response containing run context and topic items."""

    model_config = ConfigDict(frozen=True)

    workspace_id: str = Field(..., description="UUID of the workspace")
    run: Optional[TopicRunSummary] = Field(None, description="Metadata of the clustering run for these topics")
    items: List[TopicSummaryItem] = Field(default_factory=list, description="List of topic summary items")
    total: int = Field(..., description="Total matching topics")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Page size limit")
    total_pages: int = Field(..., description="Total available pages")


class PaginatedTopicRunsResponse(BaseModel):
    """Paginated list of historical topic clustering runs for a workspace."""

    model_config = ConfigDict(frozen=True)

    items: List[TopicRunSummary] = Field(default_factory=list, description="List of clustering run summaries")
    total: int = Field(..., description="Total runs count")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total available pages")


class TopicRunDetailResponse(BaseModel):
    """Full detail of a single clustering run."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="UUID of the clustering run")
    workspace_id: str = Field(..., description="UUID of the workspace")
    snapshot_id: str = Field(..., description="Corpus snapshot identifier")
    status: str = Field(..., description="Run status")
    algorithm: str = Field(..., description="Algorithm name (e.g. 'kmeans')")
    model_version: str = Field(..., description="Model version string")
    embedding_model_id: str = Field(..., description="Underlying dense embedding model")
    embedding_dimension: int = Field(..., description="Embedding dimension")
    k: int = Field(..., description="Optimal/configured number of clusters")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Hyperparameters and config")
    evaluation_metrics: Dict[str, Any] = Field(default_factory=dict, description="Quality evaluation metrics")
    selection_metadata: Dict[str, Any] = Field(default_factory=dict, description="Selection rationales and heuristics")
    corpus_snapshot_hash: str = Field(..., description="Corpus content hash")
    created_by_user_id: Optional[str] = Field(None, description="Creator user ID if available")
    created_at: str = Field(..., description="ISO 8601 created at")
    started_at: Optional[str] = Field(None, description="ISO 8601 started at")
    completed_at: Optional[str] = Field(None, description="ISO 8601 completed at")
    is_active: bool = Field(..., description="Whether this is the workspace's active run")
    topic_count: int = Field(default=0, description="Number of topics persisted in this run")
    total_assignments: int = Field(default=0, description="Total chunk assignments in this run")


class TopicDetailResponse(BaseModel):
    """Comprehensive details for a single topic view."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="UUID of the topic")
    workspace_id: str = Field(..., description="UUID of the workspace")
    clustering_run_id: str = Field(..., description="UUID of parent clustering run")
    cluster_key: str = Field(..., description="Cluster key, e.g. 'cluster_0'")
    label: str = Field(..., description="Topic label")
    description: Optional[str] = Field(None, description="Detailed synthesis or description")
    label_source: str = Field(..., description="Source of label")
    label_status: str = Field(..., description="Review status of label")
    keywords: List[TopicKeyword] = Field(default_factory=list, description="Keywords with weights")
    chunk_count: int = Field(default=0, description="Total active chunks assigned")
    document_count: int = Field(default=0, description="Distinct active documents contributing to this topic")
    representative_chunk_ids: List[str] = Field(default_factory=list, description="Representative chunk IDs")
    cluster_statistics: Dict[str, Any] = Field(default_factory=dict, description="Cohesion & distance statistics")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last updated timestamp")
    run_summary: Optional[TopicRunSummary] = Field(None, description="Parent run metadata summary")


class TopicChunkItem(BaseModel):
    """Detailed chunk record assigned to a topic with source document context."""

    model_config = ConfigDict(frozen=True)

    assignment_id: str = Field(..., description="UUID of assignment record")
    chunk_id: str = Field(..., description="UUID of document chunk")
    document_id: str = Field(..., description="UUID of parent document")
    document_title: str = Field(..., description="Title/filename of parent document")
    chunk_index: int = Field(..., description="0-based sequence index within document")
    distance_to_centroid: Optional[float] = Field(None, description="Distance from embedding to centroid")
    is_representative: bool = Field(default=False, description="Whether marked as representative near centroid")
    page_start: Optional[int] = Field(None, description="Start page number for paginated docs")
    page_end: Optional[int] = Field(None, description="End page number for paginated docs")
    slide_number: Optional[int] = Field(None, description="Slide number for presentation docs")
    section_title: Optional[str] = Field(None, description="Extracted section heading")
    content_preview: str = Field(..., description="Text preview or snippet of chunk content")
    source_type: Optional[str] = Field(None, description="Media or file type of source document")


class PaginatedTopicChunksResponse(BaseModel):
    """Paginated response of chunks assigned to a topic."""

    model_config = ConfigDict(frozen=True)

    topic_id: str = Field(..., description="UUID of topic")
    topic_label: str = Field(..., description="Label of topic")
    items: List[TopicChunkItem] = Field(default_factory=list, description="List of chunk items")
    total: int = Field(..., description="Total assigned active chunks")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size limit")
    total_pages: int = Field(..., description="Total pages")
