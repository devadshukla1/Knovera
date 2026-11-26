"""Pydantic Models and Schemas for Knovera Knowledge Graph (Phase 7).

Defines structured contracts for extracted mentions, normalized nodes,
typed relationships, validation results, NetworkX graph projections,
and persisted versioned snapshots.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.ml.knowledge_graph.ontology import NodeType


class ExtractionMethod(str, Enum):
    """Method used for extraction."""

    DETERMINISTIC = "deterministic"
    LLM = "llm"
    HYBRID = "hybrid"


class Modality(str, Enum):
    """Epistemic modality or certainty of an extracted relationship."""

    CERTAIN = "certain"
    HYPOTHETICAL = "hypothetical"
    UNCERTAIN = "uncertain"


class RelationshipValidationStatus(str, Enum):
    """Centralized validation status for knowledge graph relationships."""

    CANDIDATE = "candidate"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class SnapshotStatus(str, Enum):
    """Status lifecycle for knowledge graph snapshots."""

    QUEUED = "queued"
    BUILDING = "building"
    PERSISTING = "persisting"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    STALE = "stale"


class ExtractedMention(BaseModel):
    """An exact surface text mention extracted from a document chunk."""

    model_config = ConfigDict(from_attributes=True)

    surface_form: str
    start_offset: int
    end_offset: int
    chunk_id: Optional[str] = None
    context_snippet: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extraction_method: str = ExtractionMethod.DETERMINISTIC.value


class ExtractedConcept(BaseModel):
    """An extracted candidate concept or entity before full workspace normalization."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    normalized_name: str
    category: str
    node_type: str = NodeType.CONCEPT.value
    description: Optional[str] = None
    mentions: List[ExtractedMention] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extraction_method: str = ExtractionMethod.DETERMINISTIC.value


class NormalizedNode(BaseModel):
    """A canonical knowledge graph node resolved and deduplicated across the workspace."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    workspace_id: Optional[str] = None
    name: str
    normalized_name: str
    category: str
    node_type: str = NodeType.CONCEPT.value
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    mentions: List[ExtractedMention] = Field(default_factory=list)


class RelationshipEvidenceRecord(BaseModel):
    """Specific textual span supporting an extracted relationship."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    evidence_text: str
    start_offset: int
    end_offset: int
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ExtractedRelationship(BaseModel):
    """A typed relationship connecting two nodes with verifiable evidence."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    source_node_name: str
    target_node_name: str
    source_node_id: Optional[str] = None
    target_node_id: Optional[str] = None
    predicate: str
    inverse_predicate: Optional[str] = None
    is_negated: bool = False
    modality: str = Modality.CERTAIN.value
    qualifiers: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[RelationshipEvidenceRecord] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extraction_method: str = ExtractionMethod.DETERMINISTIC.value
    validation_status: str = RelationshipValidationStatus.CANDIDATE.value


class RelationshipValidationResult(BaseModel):
    """Auditable result of validating an extracted candidate relationship."""

    model_config = ConfigDict(from_attributes=True)

    relationship_id: Optional[str] = None
    source_node_id: Optional[str] = None
    target_node_id: Optional[str] = None
    source_node_name: str
    target_node_name: str
    predicate: str
    status: str = RelationshipValidationStatus.CANDIDATE.value
    validation_method: str = "deterministic"
    ontology_version: str = "1.0.0"
    endpoint_valid: bool = False
    predicate_valid: bool = False
    evidence_valid: bool = False
    mentions_valid: bool = True
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    validated_at: Optional[datetime] = None


class RelationshipValidationReport(BaseModel):
    """Comprehensive validation run summary for an extraction batch."""

    model_config = ConfigDict(from_attributes=True)

    workspace_id: str
    extraction_run_id: Optional[str] = None
    candidate_count: int = 0
    validated_count: int = 0
    needs_review_count: int = 0
    rejected_count: int = 0
    invalid_endpoint_count: int = 0
    invalid_predicate_count: int = 0
    invalid_evidence_count: int = 0
    stale_evidence_count: int = 0
    workspace_integrity_failures: int = 0
    negation_findings: int = 0
    modality_findings: int = 0
    duplicate_relationship_count: int = 0
    contradiction_warnings: int = 0
    validation_duration_ms: float = 0.0
    validation_policy_version: str = "1.0.0"
    results: List[RelationshipValidationResult] = Field(default_factory=list)


class GraphNodeData(BaseModel):
    """Normalized node structure inside the serialized NetworkX graph."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    normalized_name: str
    node_kind: str  # "concept" or "entity"
    node_type: str  # category from ontology
    workspace_id: str
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    ontology_version: str = "1.0.0"


class GraphEdgeData(BaseModel):
    """Directed multigraph edge structure inside the serialized NetworkX graph."""

    model_config = ConfigDict(from_attributes=True)

    id: str  # relationship_id
    source: str  # source node id
    target: str  # target node id
    predicate: str
    inverse_predicate: Optional[str] = None
    polarity: str = "positive"  # "positive" or "negative"
    is_negated: bool = False
    modality: str = Modality.CERTAIN.value
    qualifiers: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    source_chunk_ids: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    validation_status: str = RelationshipValidationStatus.VALIDATED.value
    extraction_run_id: Optional[str] = None
    workspace_id: str


class GraphMetadata(BaseModel):
    """Graph-level metadata accompanying the serialized graph."""

    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    workspace_id: str
    extraction_run_id: Optional[str] = None
    ontology_version: str = "1.0.0"
    relationship_ontology_version: str = "1.0.0"
    graph_schema_version: str = "1.0.0"
    builder_version: str = "1.0.0"
    source_snapshot_hash: Optional[str] = None
    created_at: str


class GraphStatistics(BaseModel):
    """Detailed structural metrics for a constructed NetworkX MultiDiGraph."""

    model_config = ConfigDict(from_attributes=True)

    total_nodes: int = 0
    concept_count: int = 0
    entity_count: int = 0
    total_edges: int = 0
    isolated_node_count: int = 0
    connected_components_count: int = 0
    strongly_connected_components_count: int = 0
    parallel_edge_count: int = 0
    self_loop_count: int = 0
    average_degree: float = 0.0
    max_in_degree: int = 0
    max_out_degree: int = 0
    predicate_distribution: Dict[str, int] = Field(default_factory=dict)
    node_type_distribution: Dict[str, int] = Field(default_factory=dict)


class GraphSnapshotManifest(BaseModel):
    """Sidecar manifest stored with the graph snapshot artifact."""

    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    workspace_id: str
    extraction_run_id: Optional[str] = None
    source_snapshot_hash: Optional[str] = None
    validation_policy_version: str = "1.0.0"
    ontology_version: str = "1.0.0"
    relationship_ontology_version: str = "1.0.0"
    graph_schema_version: str = "1.0.0"
    builder_version: str = "1.0.0"
    serialization_format: str = "json_node_link"
    created_at: str
    statistics: GraphStatistics
    artifact_checksum: str
    python_version: str
    networkx_version: str


class SerializedGraphDocument(BaseModel):
    """Authoritative project-owned JSON schema for graph snapshot artifacts."""

    model_config = ConfigDict(from_attributes=True)

    schema_version: str = "1.0.0"
    graph: GraphMetadata
    nodes: List[GraphNodeData] = Field(default_factory=list)
    edges: List[GraphEdgeData] = Field(default_factory=list)
    statistics: Optional[GraphStatistics] = None


class PipelineExtractionResult(BaseModel):
    """Complete summary of knowledge extraction run across a set of chunks."""

    model_config = ConfigDict(from_attributes=True)

    workspace_id: str
    nodes: List[NormalizedNode] = Field(default_factory=list)
    relationships: List[ExtractedRelationship] = Field(default_factory=list)
    total_chunks_processed: int = 0
    total_mentions_extracted: int = 0
    total_nodes_extracted: int = 0
    total_relationships_extracted: int = 0
    duration_ms: float = 0.0
    run_id: Optional[str] = None
    extraction_method: str = ExtractionMethod.DETERMINISTIC.value
