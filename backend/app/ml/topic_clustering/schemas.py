"""Pydantic schemas and data contracts for Knovera Topic Discovery (Phase 6 C6.1–C6.6)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ClusteringChunkRecord(BaseModel):
    """Normalized metadata record for a document chunk in a clustering dataset."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(..., description="UUID string of the document chunk")
    document_id: str = Field(..., description="UUID string of the parent document")
    workspace_id: str = Field(..., description="UUID string of the workspace")
    chunk_index: int = Field(..., description="0-based sequential index within the document")
    page_number: Optional[int] = Field(None, description="1-based page number if available (e.g. from PDF)")
    token_count: Optional[int] = Field(None, description="Number of tokens estimated in the chunk")
    content_hash: str = Field(..., description="SHA-256 hash of the canonical chunk text")
    text_preview: str = Field(..., description="Truncated preview snippet of chunk text (up to 200 chars)")


class DatasetManifest(BaseModel):
    """Manifest describing a versioned clustering dataset snapshot."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str = Field(..., description="Unique deterministic or timestamped snapshot identifier")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of snapshot generation",
    )
    workspace_id: str = Field(..., description="UUID string of workspace")
    chunk_count: int = Field(..., description="Number of chunks included in dataset")
    embedding_model: str = Field(..., description="Identifier of embedding model used (e.g. all-MiniLM-L6-v2)")
    embedding_dimension: int = Field(..., description="Dimension of embedding vectors (e.g. 384)")
    normalization: str = Field(default="l2", description="Normalization type applied to embeddings (e.g. l2)")
    corpus_hash: str = Field(..., description="SHA-256 hash over sorted content hashes of all included chunks")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary additional metadata")


class ClusterAssignment(BaseModel):
    """Assignment record linking a document chunk to a discovered cluster."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(..., description="UUID string of chunk")
    cluster_id: int = Field(..., description="0-indexed cluster identifier")
    distance_to_centroid: float = Field(..., description="Euclidean distance from chunk embedding to centroid")
    is_representative: bool = Field(
        default=False,
        description="Whether this chunk is among the top-N nearest representative chunks to centroid",
    )


class ClusterStats(BaseModel):
    """Aggregate statistics for an individual discovered topic cluster."""

    model_config = ConfigDict(frozen=True)

    cluster_id: int = Field(..., description="0-indexed cluster identifier")
    size: int = Field(..., description="Number of chunks assigned to this cluster")
    proportion: float = Field(..., description="Fraction of total workspace chunks belonging to cluster (0.0 - 1.0)")
    min_distance: float = Field(..., description="Minimum Euclidean distance from any chunk to centroid")
    mean_distance: float = Field(..., description="Mean Euclidean distance of chunks to centroid")
    max_distance: float = Field(..., description="Maximum Euclidean distance of chunks to centroid")
    representative_chunk_ids: List[str] = Field(
        default_factory=list,
        description="Ordered list of top representative chunk IDs (closest to centroid)",
    )


class KMeansMetrics(BaseModel):
    """Clustering quality evaluation metrics for a specific K value."""

    model_config = ConfigDict(frozen=True)

    k: int = Field(..., description="Number of clusters evaluated")
    inertia: float = Field(..., description="Within-cluster sum of squared distances (WCSS)")
    silhouette_euclidean: Optional[float] = Field(
        None, description="Silhouette score computed using Euclidean distance (-1.0 to 1.0)"
    )
    silhouette_cosine: Optional[float] = Field(
        None, description="Silhouette score computed using Cosine distance (-1.0 to 1.0)"
    )
    davies_bouldin: Optional[float] = Field(
        None, description="Davies-Bouldin index (lower indicates better clustering separation)"
    )
    calinski_harabasz: Optional[float] = Field(
        None, description="Calinski-Harabasz score (variance ratio criterion, higher is better)"
    )


class KMeansEvaluationResult(BaseModel):
    """Result of evaluating candidate K values across clustering metrics."""

    model_config = ConfigDict(frozen=True)

    candidate_k_evaluations: List[KMeansMetrics] = Field(
        default_factory=list, description="Evaluations across all tested K values"
    )
    recommended_k: Optional[int] = Field(None, description="Heuristically recommended optimal K value")
    evaluation_summary: Dict[str, Any] = Field(
        default_factory=dict, description="Summary diagnostics and selection rationales"
    )


class ModelManifest(BaseModel):
    """Manifest describing a trained and persisted K-Means topic model."""

    model_config = ConfigDict(frozen=True)

    model_version: str = Field(..., description="Version identifier of model (e.g. kmeans_v1_k4)")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of model training",
    )
    snapshot_id: str = Field(..., description="Snapshot ID of training dataset")
    workspace_id: str = Field(..., description="UUID string of workspace")
    k: int = Field(..., description="Number of clusters in model")
    random_state: int = Field(default=42, description="Random seed used for deterministic clustering")
    n_init: int = Field(default=20, description="Number of initializations run by K-Means")
    max_iter: int = Field(default=300, description="Maximum iterations for solver")
    algorithm: str = Field(default="lloyd", description="K-Means algorithm variant")
    metrics: KMeansMetrics = Field(..., description="Quality metrics for this fitted model")
    total_chunks: int = Field(..., description="Total chunks clustered")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional model configuration or notes")


# --- Detailed C6.4 Silhouette & K-Selection Schemas ---

class PerClusterSilhouetteStats(BaseModel):
    """Per-cluster silhouette diagnostics identifying cohesion and borderline memberships."""

    model_config = ConfigDict(frozen=True)

    cluster_id: int
    count: int
    mean_silhouette: float
    median_silhouette: float
    min_silhouette: float
    max_silhouette: float
    negative_count: int
    negative_percentage: float
    is_singleton: bool = False


class SilhouetteAnalysisResult(BaseModel):
    """Comprehensive silhouette evaluation metrics."""

    model_config = ConfigDict(frozen=True)

    metric: str = Field(..., description="Distance metric used: 'euclidean' or 'cosine'")
    overall_mean: float
    overall_median: float
    overall_min: float
    overall_max: float
    negative_count: int
    negative_percentage: float
    is_sampled: bool = False
    sample_size: int
    per_cluster: Dict[int, PerClusterSilhouetteStats] = Field(default_factory=dict)


class StabilityResult(BaseModel):
    """Clustering stability evaluation across multiple random seeds using Adjusted Rand Index."""

    model_config = ConfigDict(frozen=True)

    random_seeds: List[int]
    pairwise_ari: Dict[str, float] = Field(default_factory=dict)
    mean_ari: float
    min_ari: float
    stability_score: float  # Normalized 0.0 - 1.0


class ClusterSizeDiagnostics(BaseModel):
    """Diagnostic metrics evaluating cluster balance and anomaly counts."""

    model_config = ConfigDict(frozen=True)

    total_chunks: int
    min_size: int
    max_size: int
    mean_size: float
    median_size: float
    std_size: float
    max_cluster_proportion: float
    singleton_count: int
    very_small_cluster_count: int  # clusters with <= 2 chunks


class CandidateKEvaluation(BaseModel):
    """Complete evaluation report for a single candidate K."""

    model_config = ConfigDict(frozen=True)

    k: int
    inertia: float
    inertia_drop: Optional[float] = None
    relative_inertia_drop: Optional[float] = None
    duration_ms: float
    euclidean_silhouette: Optional[SilhouetteAnalysisResult] = None
    cosine_silhouette: Optional[SilhouetteAnalysisResult] = None
    davies_bouldin: Optional[float] = None
    calinski_harabasz: Optional[float] = None
    stability: Optional[StabilityResult] = None
    size_diagnostics: ClusterSizeDiagnostics


class KSelectionReport(BaseModel):
    """Machine-readable K-selection report for a workspace snapshot."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    corpus_snapshot_hash: str
    embedding_model: str
    embedding_dimension: int
    normalization: str
    candidate_k_values: List[int]
    candidates: List[CandidateKEvaluation]
    invalid_candidates: Dict[str, str] = Field(default_factory=dict)  # "k": reason
    recommended_k: Optional[int] = None
    selection_status: str = "conclusive"  # "conclusive", "requires_review", "inconclusive"
    selection_rationale: str
    warnings: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# --- Detailed C6.5 Labelling Schemas ---

class TopicKeyword(BaseModel):
    """Ranked keyword or keyphrase extracted for a cluster."""

    model_config = ConfigDict(frozen=True)

    term: str
    score: float


class TopicLabelMetadata(BaseModel):
    """Rich topic label and provenance for a discovered cluster."""

    model_config = ConfigDict(frozen=True)

    cluster_key: str
    cluster_id: int
    label: str
    description: Optional[str] = None
    label_source: str = "keyword_based"  # "keyword_based", "llm_assisted", "human_reviewed"
    label_status: str = "suggested"      # "suggested", "reviewed", "approved", "needs_review"
    keywords: List[TopicKeyword] = Field(default_factory=list)
    representative_chunk_ids: List[str] = Field(default_factory=list)
    supporting_document_count: int = 0
    supporting_chunk_count: int = 0
    cluster_statistics: Dict[str, Any] = Field(default_factory=dict)


# --- Detailed C6.6 API & Persistence Summary Schemas ---

class TopicRunSummary(BaseModel):
    """Summary of a persistent topic clustering run."""

    model_config = ConfigDict(frozen=True)

    id: str
    workspace_id: str
    snapshot_id: str
    status: str
    k: int
    model_version: str
    is_active: bool
    created_at: str
    completed_at: Optional[str] = None


class TopicDetail(BaseModel):
    """Detail of a persisted topic for API responses."""

    model_config = ConfigDict(frozen=True)

    id: str
    workspace_id: str
    clustering_run_id: str
    cluster_key: str
    label: str
    description: Optional[str] = None
    label_source: str
    label_status: str
    keywords: List[TopicKeyword] = Field(default_factory=list)
    chunk_count: int = 0
    representative_chunk_ids: List[str] = Field(default_factory=list)
