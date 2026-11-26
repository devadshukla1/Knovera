/**
 * Knovera Knowledge Graph API Client (Phase 7 C7.7–C7.9).
 */

import { apiFetch } from '@/services/api';
import {
  GraphNeighborhoodResponse,
  GraphNodeDetailResponse,
  GraphPathsResponse,
  GraphRelationshipDetailResponse,
  KnowledgeGraphOverviewResponse,
  MindMapNodeItem,
  MindMapTreeResponse,
  PaginatedGraphNodesResponse,
  PaginatedGraphRelationshipsResponse,
  PaginatedGraphSnapshotsResponse,
  PaginatedNodeMentionsResponse,
  PaginatedRelationshipEvidenceResponse,
} from '../types/knowledgeGraph';

export interface SearchNodesParams {
  snapshotId?: string;
  search?: string;
  nodeKind?: string;
  nodeType?: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortOrder?: string;
}

export interface GetNeighborhoodParams {
  nodeId: string;
  snapshotId?: string;
  depth?: number;
  direction?: 'outgoing' | 'incoming' | 'both';
  relationshipTypes?: string[];
  nodeTypes?: string[];
  maxNodes?: number;
  maxEdges?: number;
}

export interface GetRelationshipsParams {
  snapshotId?: string;
  sourceNodeId?: string;
  targetNodeId?: string;
  predicate?: string;
  polarity?: string;
  page?: number;
  pageSize?: number;
}

export interface FindPathsParams {
  sourceNodeId: string;
  targetNodeId: string;
  snapshotId?: string;
  maxHops?: number;
  maxPaths?: number;
  allowedPredicates?: string[];
}

export const knowledgeGraphApi = {
  /**
   * Fetches metadata, counts, and capabilities for workspace graph.
   */
  async getOverview(
    workspaceId: string,
    snapshotId?: string
  ): Promise<KnowledgeGraphOverviewResponse> {
    const query = new URLSearchParams();
    if (snapshotId) query.set('snapshot_id', snapshotId);
    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph${qs ? `?${qs}` : ''}`;
    return apiFetch<KnowledgeGraphOverviewResponse>(endpoint);
  },

  /**
   * Searches canonical nodes across the selected graph snapshot.
   */
  async searchNodes(
    workspaceId: string,
    params: SearchNodesParams = {}
  ): Promise<PaginatedGraphNodesResponse> {
    const query = new URLSearchParams();
    if (params.snapshotId) query.set('snapshot_id', params.snapshotId);
    if (params.search && params.search.trim()) query.set('search', params.search.trim());
    if (params.nodeKind) query.set('node_kind', params.nodeKind);
    if (params.nodeType) query.set('node_type', params.nodeType);
    if (params.page !== undefined) query.set('page', String(params.page));
    if (params.pageSize !== undefined) query.set('page_size', String(params.pageSize));
    if (params.sortBy) query.set('sort_by', params.sortBy);
    if (params.sortOrder) query.set('sort_order', params.sortOrder);

    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/nodes${qs ? `?${qs}` : ''}`;
    return apiFetch<PaginatedGraphNodesResponse>(endpoint);
  },

  /**
   * Retrieves full details and provenance for a single node.
   */
  async getNodeDetails(
    workspaceId: string,
    nodeId: string,
    snapshotId?: string
  ): Promise<GraphNodeDetailResponse> {
    const query = new URLSearchParams();
    if (snapshotId) query.set('snapshot_id', snapshotId);
    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/nodes/${encodeURIComponent(nodeId)}${qs ? `?${qs}` : ''}`;
    return apiFetch<GraphNodeDetailResponse>(endpoint);
  },

  /**
   * Retrieves bounded neighborhood subgraph around a focal node.
   */
  async getNeighborhood(
    workspaceId: string,
    params: GetNeighborhoodParams
  ): Promise<GraphNeighborhoodResponse> {
    const query = new URLSearchParams();
    query.set('node_id', params.nodeId);
    if (params.snapshotId) query.set('snapshot_id', params.snapshotId);
    if (params.depth !== undefined) query.set('depth', String(params.depth));
    if (params.direction) query.set('direction', params.direction);
    if (params.maxNodes !== undefined) query.set('max_nodes', String(params.maxNodes));
    if (params.maxEdges !== undefined) query.set('max_edges', String(params.maxEdges));
    if (params.relationshipTypes) {
      params.relationshipTypes.forEach((rt) => query.append('relationship_types', rt));
    }
    if (params.nodeTypes) {
      params.nodeTypes.forEach((nt) => query.append('node_types', nt));
    }

    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/neighborhood${qs ? `?${qs}` : ''}`;
    return apiFetch<GraphNeighborhoodResponse>(endpoint);
  },

  /**
   * Lists filtered relationships in the snapshot.
   */
  async getRelationships(
    workspaceId: string,
    params: GetRelationshipsParams = {}
  ): Promise<PaginatedGraphRelationshipsResponse> {
    const query = new URLSearchParams();
    if (params.snapshotId) query.set('snapshot_id', params.snapshotId);
    if (params.sourceNodeId) query.set('source_node_id', params.sourceNodeId);
    if (params.targetNodeId) query.set('target_node_id', params.targetNodeId);
    if (params.predicate) query.set('predicate', params.predicate);
    if (params.polarity) query.set('polarity', params.polarity);
    if (params.page !== undefined) query.set('page', String(params.page));
    if (params.pageSize !== undefined) query.set('page_size', String(params.pageSize));

    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/relationships${qs ? `?${qs}` : ''}`;
    return apiFetch<PaginatedGraphRelationshipsResponse>(endpoint);
  },

  /**
   * Retrieves single relationship details.
   */
  async getRelationshipDetails(
    workspaceId: string,
    relationshipId: string,
    snapshotId?: string
  ): Promise<GraphRelationshipDetailResponse> {
    const query = new URLSearchParams();
    if (snapshotId) query.set('snapshot_id', snapshotId);
    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/relationships/${encodeURIComponent(relationshipId)}${qs ? `?${qs}` : ''}`;
    return apiFetch<GraphRelationshipDetailResponse>(endpoint);
  },

  /**
   * Retrieves verified source evidence records for a relationship.
   */
  async getRelationshipEvidence(
    workspaceId: string,
    relationshipId: string,
    page: number = 1,
    pageSize: number = 10
  ): Promise<PaginatedRelationshipEvidenceResponse> {
    const query = new URLSearchParams();
    query.set('page', String(page));
    query.set('page_size', String(pageSize));
    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/relationships/${encodeURIComponent(relationshipId)}/evidence?${qs}`;
    return apiFetch<PaginatedRelationshipEvidenceResponse>(endpoint);
  },

  /**
   * Retrieves surface mentions and document excerpts for a node.
   */
  async getNodeEvidence(
    workspaceId: string,
    nodeId: string,
    page: number = 1,
    pageSize: number = 10
  ): Promise<PaginatedNodeMentionsResponse> {
    const query = new URLSearchParams();
    query.set('page', String(page));
    query.set('page_size', String(pageSize));
    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/nodes/${encodeURIComponent(nodeId)}/evidence?${qs}`;
    return apiFetch<PaginatedNodeMentionsResponse>(endpoint);
  },

  /**
   * Discovers connection paths between two canonical nodes.
   */
  async findPaths(
    workspaceId: string,
    params: FindPathsParams
  ): Promise<GraphPathsResponse> {
    const query = new URLSearchParams();
    query.set('source_node_id', params.sourceNodeId);
    query.set('target_node_id', params.targetNodeId);
    if (params.snapshotId) query.set('snapshot_id', params.snapshotId);
    if (params.maxHops !== undefined) query.set('max_hops', String(params.maxHops));
    if (params.maxPaths !== undefined) query.set('max_paths', String(params.maxPaths));
    if (params.allowedPredicates) {
      params.allowedPredicates.forEach((p) => query.append('allowed_predicates', p));
    }

    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/paths?${qs}`;
    return apiFetch<GraphPathsResponse>(endpoint);
  },

  /**
   * Lists historical graph snapshots for the workspace.
   */
  async listSnapshots(
    workspaceId: string,
    page: number = 1,
    pageSize: number = 20
  ): Promise<PaginatedGraphSnapshotsResponse> {
    const query = new URLSearchParams();
    query.set('page', String(page));
    query.set('page_size', String(pageSize));
    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/snapshots?${qs}`;
    return apiFetch<PaginatedGraphSnapshotsResponse>(endpoint);
  },

  /**
   * Builds or regenerates the active knowledge graph roadmap from workspace documents.
   */
  async buildGraph(workspaceId: string): Promise<KnowledgeGraphOverviewResponse> {
    return apiFetch<KnowledgeGraphOverviewResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/build`,
      {
        method: 'POST',
      }
    );
  },

  /**
   * Updates the persistent learning status for a concept node.
   */
  async updateNodeLearningStatus(
    workspaceId: string,
    nodeId: string,
    status: 'not_started' | 'in_progress' | 'learned' | 'needs_revision'
  ): Promise<GraphNodeDetailResponse> {
    return apiFetch<GraphNodeDetailResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/nodes/${encodeURIComponent(nodeId)}/status`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status }),
      }
    );
  },

  /**
   * Retrieves Knovera hierarchical mind map for the workspace.
   */
  async getMindMap(
    workspaceId: string,
    forceRebuild: boolean = false
  ): Promise<MindMapTreeResponse> {
    const qs = forceRebuild ? '?force_rebuild=true' : '';
    return apiFetch<MindMapTreeResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/mind-map${qs}`
    );
  },

  /**
   * Rebuilds Knovera hierarchical mind map from documents.
   */
  async buildMindMap(workspaceId: string): Promise<MindMapTreeResponse> {
    return apiFetch<MindMapTreeResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/mind-map/build`,
      {
        method: 'POST',
      }
    );
  },

  /**
   * Updates learning status for a node in the mind map.
   */
  async updateMindMapNodeStatus(
    workspaceId: string,
    nodeId: string,
    status: string
  ): Promise<MindMapNodeItem> {
    return apiFetch<MindMapNodeItem>(
      `workspaces/${encodeURIComponent(workspaceId)}/knowledge-graph/mind-map/nodes/${encodeURIComponent(nodeId)}/status`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status }),
      }
    );
  },
};
