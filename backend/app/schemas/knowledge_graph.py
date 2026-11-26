"""Pydantic v2 schemas for Knowledge Graph API (Phase 7 C7.7).

Provides strongly typed schemas for graph overview, node search, neighborhood exploration,
relationship inspection, source evidence attribution, and path exploration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Snapshots & Overview
# ---------------------------------------------------------------------------

class GraphSnapshotSummaryItem(BaseModel):
    """Summary of a versioned graph snapshot."""

    id: str
    status: str
    is_active: bool
    created_at: str
    completed_at: Optional[str] = None
    node_count: int
    edge_count: int
    concept_count: int
    entity_count: int
    component_count: int = 1
    isolated_node_count: int = 0
    extraction_run_id: Optional[str] = None
    ontology_version: str = "1.0.0"


class GraphStatisticsSummary(BaseModel):
    """Topological metrics and distributions."""

    isolated_node_count: int = 0
    connected_component_count: int = 1
    density: float = 0.0
    self_loops_count: int = 0
    parallel_edges_count: int = 0
    predicate_distribution: Dict[str, int] = Field(default_factory=dict)
    node_type_distribution: Dict[str, int] = Field(default_factory=dict)
    node_kind_distribution: Dict[str, int] = Field(default_factory=dict)


class GraphCapabilities(BaseModel):
    """Advertised API capabilities for the graph."""

    node_search: bool = True
    neighborhood_expansion: bool = True
    relationship_details: bool = True
    source_evidence: bool = True
    path_exploration: bool = True
    snapshot_history: bool = True


class KnowledgeGraphOverviewResponse(BaseModel):
    """Overview response for workspace knowledge graph."""

    workspace_id: str
    has_graph: bool = True
    snapshot: Optional[GraphSnapshotSummaryItem] = None
    statistics: Optional[GraphStatisticsSummary] = None
    capabilities: GraphCapabilities = Field(default_factory=GraphCapabilities)


class PaginatedGraphSnapshotsResponse(BaseModel):
    """Paginated list of historical graph snapshots."""

    items: List[GraphSnapshotSummaryItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

class GraphNodeItem(BaseModel):
    """Graph node item returned in listings, searches, and subgraphs."""

    id: str
    label: str
    normalized_name: str
    node_kind: str  # "concept" or "entity"
    node_type: Optional[str] = None  # Specific category e.g. "algorithm", "technology"
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    in_degree: int = 0
    out_degree: int = 0
    degree: int = 0
    connected_relationship_count: int = 0
    snapshot_id: Optional[str] = None
    learning_status: Optional[str] = "not_started"  # "not_started", "in_progress", "learned", "needs_revision"


class GraphNodeDetailResponse(BaseModel):
    """Detailed metadata for a single canonical knowledge node."""

    id: str
    workspace_id: str
    label: str
    normalized_name: str
    node_kind: str
    node_type: Optional[str] = None
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    ontology_version: str = "1.0.0"
    in_degree: int = 0
    out_degree: int = 0
    degree: int = 0
    connected_relationship_count: int = 0
    mention_count: int = 0
    supporting_document_count: int = 0
    snapshot_id: Optional[str] = None
    learning_status: Optional[str] = "not_started"


class NodeStatusUpdateRequest(BaseModel):
    """Request payload for updating learner status on a concept node."""

    status: str  # "not_started", "in_progress", "learned", "needs_revision"


class PaginatedGraphNodesResponse(BaseModel):
    """Paginated response for node search and browse."""

    items: List[GraphNodeItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Relationships & Edges
# ---------------------------------------------------------------------------

class GraphEdgeItem(BaseModel):
    """Graph edge element representing a validated relationship."""

    id: str  # Unique relationship ID
    source: str  # Subject node ID
    target: str  # Object node ID
    predicate: str  # Predicate relation_type
    inverse_predicate: Optional[str] = None
    polarity: str = "positive"
    is_negated: bool = False
    modality: str = "certain"
    qualifiers: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    validation_status: str = "validated"
    evidence_count: int = 0
    source_label: Optional[str] = None
    target_label: Optional[str] = None


class GraphRelationshipDetailResponse(BaseModel):
    """Detailed representation of a validated relationship edge."""

    id: str
    workspace_id: str
    source_node_id: str
    source_node_label: str
    source_node_kind: str
    target_node_id: str
    target_node_label: str
    target_node_kind: str
    predicate: str
    inverse_predicate: Optional[str] = None
    polarity: str = "positive"
    is_negated: bool = False
    modality: str = "certain"
    qualifiers: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    validation_status: str = "validated"
    ontology_version: str = "1.0.0"
    extraction_run_id: Optional[str] = None
    evidence_count: int = 0
    created_at: Optional[str] = None


class PaginatedGraphRelationshipsResponse(BaseModel):
    """Paginated response for relationships."""

    items: List[GraphEdgeItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Neighborhood Subgraph
# ---------------------------------------------------------------------------

class GraphNeighborhoodResponse(BaseModel):
    """Bounded subgraph around a selected focal node."""

    root_node_id: str
    depth: int
    direction: str
    nodes: List[GraphNodeItem]
    edges: List[GraphEdgeItem]
    total_nodes: int
    total_edges: int
    is_truncated: bool = False
    available_neighbor_count: int = 0


# ---------------------------------------------------------------------------
# Source Evidence & Mentions
# ---------------------------------------------------------------------------

class RelationshipEvidenceItem(BaseModel):
    """Verified source evidence record for a relationship."""

    id: str
    relationship_id: str
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None
    document_title: str
    source_type: str = "application/pdf"
    evidence_text: str
    start_offset: int
    end_offset: int
    confidence: float = 1.0
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    slide_number: Optional[int] = None
    section_title: Optional[str] = None
    validation_status: str = "validated"
    is_source_available: bool = True


class PaginatedRelationshipEvidenceResponse(BaseModel):
    """Paginated list of evidence records supporting a relationship."""

    relationship_id: str
    items: List[RelationshipEvidenceItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class NodeMentionItem(BaseModel):
    """Surface text mention of a node in a document chunk."""

    id: str
    node_id: str
    surface_form: str
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None
    document_title: str
    source_type: str = "application/pdf"
    excerpt: str
    start_offset: int
    end_offset: int
    confidence: float = 1.0
    extraction_method: str = "deterministic"
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    slide_number: Optional[int] = None
    section_title: Optional[str] = None
    is_source_available: bool = True


class PaginatedNodeMentionsResponse(BaseModel):
    """Paginated list of mentions supporting a concept or entity."""

    node_id: str
    items: List[NodeMentionItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Path Exploration
# ---------------------------------------------------------------------------

class GraphPathStep(BaseModel):
    """Single hop in a connection path."""

    source_node: GraphNodeItem
    edge: GraphEdgeItem
    target_node: GraphNodeItem


class GraphPathItem(BaseModel):
    """Ordered sequence of connected nodes and relationship edges."""

    path_index: int
    hop_count: int
    nodes: List[GraphNodeItem]
    edges: List[GraphEdgeItem]
    steps: List[GraphPathStep]


class GraphPathsResponse(BaseModel):
    """Result of path exploration between two nodes."""

    source_node_id: str
    target_node_id: str
    max_hops: int
    path_count: int
    paths: List[GraphPathItem]
    no_path_found: bool = False


# ---------------------------------------------------------------------------
# Hierarchical Interactive Mind Map (Knovera Style)
# ---------------------------------------------------------------------------

class MindMapNodeItem(BaseModel):
    """Hierarchical mind map node (Root -> Primary -> Secondary -> Leaf)."""

    id: str
    label: str
    level: int  # 0: root, 1: primary, 2: secondary, 3: leaf
    node_type: str  # "root", "primary", "secondary", "leaf"
    category: Optional[str] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    parent_id: Optional[str] = None
    children_count: int = 0
    is_expanded: bool = True
    learning_status: str = "not_started"  # "not_started", "in_progress", "learned", "needs_revision"
    difficulty: Optional[str] = "intermediate"  # "beginner", "intermediate", "advanced"
    importance: Optional[str] = "core"  # "core", "important", "supplementary"
    prerequisites: List[str] = Field(default_factory=list)
    related_concepts: List[str] = Field(default_factory=list)
    source_documents: List[str] = Field(default_factory=list)
    source_references: List[Dict[str, Any]] = Field(default_factory=list)
    source_page: Optional[int] = None
    source_excerpt: Optional[str] = None
    chunk_ids: List[str] = Field(default_factory=list)
    is_shared_across_documents: bool = False
    has_conflicting_info: bool = False


class MindMapEdgeItem(BaseModel):
    """Directed edge connecting parent node to child node in the mind map hierarchy."""

    id: str
    source: str
    target: str
    label: Optional[str] = None


class MindMapTreeResponse(BaseModel):
    """Complete hierarchical mind map tree for interactive Knovera visualization."""

    workspace_id: str
    workspace_name: str
    root_node_id: str
    nodes: List[MindMapNodeItem]
    edges: List[MindMapEdgeItem]
    total_nodes: int
    total_leaves: int
    depth: int = 4
    version: int = 1
    generated_at: Optional[str] = None
    source_document_ids: List[str] = Field(default_factory=list)
    source_document_names: List[str] = Field(default_factory=list)
    source_document_count: int = 0
    source_fingerprint: Optional[str] = None
    is_out_of_date: bool = False
    out_of_date_reason: Optional[str] = None
    merged_concept_count: int = 0


class MindMapStatusUpdateRequest(BaseModel):
    """Request to update learning status of a mind map node."""

    status: str

