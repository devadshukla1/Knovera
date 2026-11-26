"""Knovera Topic Discovery & K-Means Unsupervised Learning Module (Phase 6)."""

from backend.app.ml.topic_clustering.dataset import (
    ClusteringDatasetManager,
    ClusteringDatasetValidationError,
    ClusteringDatasetValidator,
)
from backend.app.ml.topic_clustering.embedding_service import ChunkEmbeddingService
from backend.app.ml.topic_clustering.keyword_extraction import ClusterKeywordExtractor
from backend.app.ml.topic_clustering.kmeans import KMeansTopicClusterer
from backend.app.ml.topic_clustering.labeling import ClusterLabelingService
from backend.app.ml.topic_clustering.persistence import (
    TopicPersistenceError,
    TopicPersistenceService,
)
from backend.app.ml.topic_clustering.schemas import (
    CandidateKEvaluation,
    ClusterAssignment,
    ClusterSizeDiagnostics,
    ClusterStats,
    ClusteringChunkRecord,
    DatasetManifest,
    KMeansEvaluationResult,
    KMeansMetrics,
    KSelectionReport,
    ModelManifest,
    PerClusterSilhouetteStats,
    SilhouetteAnalysisResult,
    StabilityResult,
    TopicDetail,
    TopicKeyword,
    TopicLabelMetadata,
    TopicRunSummary,
)
from backend.app.ml.topic_clustering.selection import ClusterSelectionService
from backend.app.ml.topic_clustering.silhouette import compute_silhouette_analysis
from backend.app.ml.topic_clustering.stability import compute_clustering_stability

__all__ = [
    # Services
    "ChunkEmbeddingService",
    "ClusteringDatasetManager",
    "ClusteringDatasetValidator",
    "ClusteringDatasetValidationError",
    "KMeansTopicClusterer",
    "ClusterSelectionService",
    "ClusterKeywordExtractor",
    "ClusterLabelingService",
    "TopicPersistenceService",
    "TopicPersistenceError",
    "compute_silhouette_analysis",
    "compute_clustering_stability",
    # Schemas
    "ClusteringChunkRecord",
    "DatasetManifest",
    "ClusterAssignment",
    "ClusterStats",
    "KMeansMetrics",
    "KMeansEvaluationResult",
    "ModelManifest",
    "PerClusterSilhouetteStats",
    "SilhouetteAnalysisResult",
    "StabilityResult",
    "ClusterSizeDiagnostics",
    "CandidateKEvaluation",
    "KSelectionReport",
    "TopicKeyword",
    "TopicLabelMetadata",
    "TopicRunSummary",
    "TopicDetail",
]
