/**
 * TypeScript definitions for Knovera Knowledge Graph (Phase 7 C7.7–C7.9).
 */

export interface GraphSnapshotSummaryItem {
  id: string;
  status: string;
  is_active: boolean;
  created_at: string;
  completed_at?: string | null;
  node_count: number;
  edge_count: number;
  concept_count: number;
  entity_count: number;
  component_count: number;
  isolated_node_count: number;
  extraction_run_id?: string | null;
  ontology_version: string;
}

export interface GraphStatisticsSummary {
  isolated_node_count: number;
  connected_component_count: number;
  density: number;
  self_loops_count: number;
  parallel_edges_count: number;
  predicate_distribution: Record<string, number>;
  node_type_distribution: Record<string, number>;
  node_kind_distribution: Record<string, number>;
}

export interface GraphCapabilities {
  node_search: boolean;
  neighborhood_expansion: boolean;
  relationship_details: boolean;
  source_evidence: boolean;
  path_exploration: boolean;
  snapshot_history: boolean;
}

export interface KnowledgeGraphOverviewResponse {
  workspace_id: string;
  has_graph: boolean;
  snapshot: GraphSnapshotSummaryItem | null;
  statistics: GraphStatisticsSummary | null;
  capabilities: GraphCapabilities;
}

export interface PaginatedGraphSnapshotsResponse {
  items: GraphSnapshotSummaryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GraphNodeItem {
  id: string;
  label: string;
  normalized_name: string;
  node_kind: 'concept' | 'entity' | string;
  node_type?: string | null;
  description?: string | null;
  aliases: string[];
  in_degree: number;
  out_degree: number;
  degree: number;
  connected_relationship_count: number;
  snapshot_id?: string | null;
  learning_status?: 'not_started' | 'in_progress' | 'learned' | 'needs_revision' | string;
}

export interface GraphNodeDetailResponse {
  id: string;
  workspace_id: string;
  label: string;
  normalized_name: string;
  node_kind: 'concept' | 'entity' | string;
  node_type?: string | null;
  description?: string | null;
  aliases: string[];
  ontology_version: string;
  in_degree: number;
  out_degree: number;
  degree: number;
  connected_relationship_count: number;
  mention_count: number;
  supporting_document_count: number;
  snapshot_id?: string | null;
  learning_status?: 'not_started' | 'in_progress' | 'learned' | 'needs_revision' | string;
}

export interface PaginatedGraphNodesResponse {
  items: GraphNodeItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GraphEdgeItem {
  id: string;
  source: string;
  target: string;
  predicate: string;
  inverse_predicate?: string | null;
  polarity: string;
  is_negated: boolean;
  modality: string;
  qualifiers: Record<string, any>;
  confidence: number;
  validation_status: string;
  evidence_count: number;
  source_label?: string | null;
  target_label?: string | null;
}

export interface GraphRelationshipDetailResponse {
  id: string;
  workspace_id: string;
  source_node_id: string;
  source_node_label: string;
  source_node_kind: string;
  target_node_id: string;
  target_node_label: string;
  target_node_kind: string;
  predicate: string;
  inverse_predicate?: string | null;
  polarity: string;
  is_negated: boolean;
  modality: string;
  qualifiers: Record<string, any>;
  confidence: number;
  validation_status: string;
  ontology_version: string;
  extraction_run_id?: string | null;
  evidence_count: number;
  created_at?: string | null;
}

export interface PaginatedGraphRelationshipsResponse {
  items: GraphEdgeItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GraphNeighborhoodResponse {
  root_node_id: string;
  depth: number;
  direction: string;
  nodes: GraphNodeItem[];
  edges: GraphEdgeItem[];
  total_nodes: number;
  total_edges: number;
  is_truncated: boolean;
  available_neighbor_count: number;
}

export interface RelationshipEvidenceItem {
  id: string;
  relationship_id: string;
  chunk_id?: string | null;
  document_id?: string | null;
  document_title: string;
  source_type: string;
  evidence_text: string;
  start_offset: number;
  end_offset: number;
  confidence: number;
  page_start?: number | null;
  page_end?: number | null;
  slide_number?: number | null;
  section_title?: string | null;
  validation_status: string;
  is_source_available: boolean;
}

export interface PaginatedRelationshipEvidenceResponse {
  relationship_id: string;
  items: RelationshipEvidenceItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface NodeMentionItem {
  id: string;
  node_id: string;
  surface_form: string;
  chunk_id?: string | null;
  document_id?: string | null;
  document_title: string;
  source_type: string;
  excerpt: string;
  start_offset: number;
  end_offset: number;
  confidence: number;
  extraction_method: string;
  page_start?: number | null;
  page_end?: number | null;
  slide_number?: number | null;
  section_title?: string | null;
  is_source_available: boolean;
}

export interface PaginatedNodeMentionsResponse {
  node_id: string;
  items: NodeMentionItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GraphPathStep {
  source_node: GraphNodeItem;
  edge: GraphEdgeItem;
  target_node: GraphNodeItem;
}

export interface GraphPathItem {
  path_index: number;
  hop_count: number;
  nodes: GraphNodeItem[];
  edges: GraphEdgeItem[];
  steps: GraphPathStep[];
}

export interface GraphPathsResponse {
  source_node_id: string;
  target_node_id: string;
  max_hops: number;
  path_count: number;
  paths: GraphPathItem[];
  no_path_found: boolean;
}

// ---------------------------------------------------------------------------
// Knovera Mind Map Types
// ---------------------------------------------------------------------------

export type MindMapLevel = 0 | 1 | 2 | 3;
export type MindMapNodeType = 'root' | 'primary' | 'secondary' | 'leaf';
export type LearningStatusType = 'not_started' | 'in_progress' | 'learned' | 'needs_revision';

export interface MindMapSourceRef {
  document_id?: string;
  document_title: string;
  page_number?: number | null;
  excerpt?: string | null;
}

export interface MindMapNodeItem {
  id: string;
  label: string;
  level: number; // 0: Root, 1: Primary, 2: Secondary, 3: Leaf
  node_type: MindMapNodeType | string;
  category?: string | null;
  description?: string | null;
  summary?: string | null;
  parent_id?: string | null;
  children_count: number;
  is_expanded?: boolean;
  learning_status?: LearningStatusType | string;
  difficulty?: 'beginner' | 'intermediate' | 'advanced' | string;
  importance?: 'core' | 'important' | 'supplementary' | string;
  prerequisites?: string[];
  related_concepts?: string[];
  source_documents?: string[];
  source_references?: MindMapSourceRef[];
  source_page?: number | null;
  source_excerpt?: string | null;
  chunk_ids?: string[];
  is_shared_across_documents?: boolean;
  has_conflicting_info?: boolean;
}

export interface MindMapEdgeItem {
  id: string;
  source: string;
  target: string;
  label?: string | null;
}

export interface MindMapTreeResponse {
  workspace_id: string;
  workspace_name: string;
  root_node_id: string;
  nodes: MindMapNodeItem[];
  edges: MindMapEdgeItem[];
  total_nodes: number;
  total_leaves: number;
  depth: number;
  version?: number;
  generated_at?: string | null;
  source_document_ids?: string[];
  source_document_names?: string[];
  source_document_count?: number;
  source_fingerprint?: string | null;
  is_out_of_date?: boolean;
  out_of_date_reason?: string | null;
  merged_concept_count?: number;
}

