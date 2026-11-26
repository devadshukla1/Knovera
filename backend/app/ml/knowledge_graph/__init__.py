"""Knowledge Graph extraction, normalization, relationship mining, graph construction, and persistence package."""

from backend.app.ml.knowledge_graph.concept_extraction import ConceptExtractionService
from backend.app.ml.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from backend.app.ml.knowledge_graph.graph_loader import GraphLoader
from backend.app.ml.knowledge_graph.graph_persistence import GraphPersistenceService
from backend.app.ml.knowledge_graph.graph_serializer import GraphSerializer
from backend.app.ml.knowledge_graph.graph_statistics import GraphStatisticsService
from backend.app.ml.knowledge_graph.normalization import EntityNormalizationService
from backend.app.ml.knowledge_graph.ontology import (
    ConceptType,
    EntityType,
    NodeType,
    ONTOLOGY_VERSION,
    infer_node_type,
    is_valid_category,
)
from backend.app.ml.knowledge_graph.orchestrator import KnowledgeExtractionOrchestrator
from backend.app.ml.knowledge_graph.relationship_extraction import RelationshipExtractionService
from backend.app.ml.knowledge_graph.relationships import (
    RELATIONSHIP_ONTOLOGY_VERSION,
    RelationCategory,
    RelationPredicate,
    get_inverse_predicate,
    is_symmetric_predicate,
    is_valid_predicate,
    validate_predicate_domain_range,
)
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedConcept,
    ExtractedMention,
    ExtractedRelationship,
    ExtractionMethod,
    GraphEdgeData,
    GraphMetadata,
    GraphNodeData,
    GraphSnapshotManifest,
    GraphStatistics,
    Modality,
    NormalizedNode,
    PipelineExtractionResult,
    RelationshipEvidenceRecord,
    RelationshipValidationReport,
    RelationshipValidationResult,
    RelationshipValidationStatus,
    SerializedGraphDocument,
    SnapshotStatus,
)
from backend.app.ml.knowledge_graph.validation import (
    RelationshipValidationService,
    detect_prompt_injection,
    locate_all_spans,
    sanitize_text_for_extraction,
    verify_span,
)

__all__ = [
    "ONTOLOGY_VERSION",
    "RELATIONSHIP_ONTOLOGY_VERSION",
    "NodeType",
    "ConceptType",
    "EntityType",
    "RelationCategory",
    "RelationPredicate",
    "ExtractionMethod",
    "Modality",
    "RelationshipValidationStatus",
    "SnapshotStatus",
    "ExtractedMention",
    "ExtractedConcept",
    "NormalizedNode",
    "RelationshipEvidenceRecord",
    "ExtractedRelationship",
    "RelationshipValidationResult",
    "RelationshipValidationReport",
    "GraphNodeData",
    "GraphEdgeData",
    "GraphMetadata",
    "GraphStatistics",
    "GraphSnapshotManifest",
    "SerializedGraphDocument",
    "PipelineExtractionResult",
    "infer_node_type",
    "is_valid_category",
    "is_valid_predicate",
    "get_inverse_predicate",
    "is_symmetric_predicate",
    "validate_predicate_domain_range",
    "verify_span",
    "locate_all_spans",
    "detect_prompt_injection",
    "sanitize_text_for_extraction",
    "ConceptExtractionService",
    "EntityNormalizationService",
    "RelationshipExtractionService",
    "RelationshipValidationService",
    "KnowledgeGraphBuilder",
    "GraphStatisticsService",
    "GraphSerializer",
    "GraphLoader",
    "GraphPersistenceService",
    "KnowledgeExtractionOrchestrator",
]
