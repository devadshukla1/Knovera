/**
 * Automated tests for Knowledge Graph API client (Phase 7 C7.7–C7.9).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { knowledgeGraphApi } from '../api/knowledgeGraphApi';
import * as apiModule from '@/services/api';
import {
  KnowledgeGraphOverviewResponse,
  PaginatedGraphNodesResponse,
  GraphNodeDetailResponse,
  GraphNeighborhoodResponse,
  PaginatedGraphRelationshipsResponse,
  PaginatedRelationshipEvidenceResponse,
  PaginatedNodeMentionsResponse,
  GraphPathsResponse,
  PaginatedGraphSnapshotsResponse,
} from '../types/knowledgeGraph';

vi.mock('@/services/api', async () => {
  const actual = await vi.importActual<typeof apiModule>('@/services/api');
  return {
    ...actual,
    apiFetch: vi.fn(),
  };
});

const mockOverview: KnowledgeGraphOverviewResponse = {
  workspace_id: 'ws-test',
  has_graph: true,
  snapshot: {
    id: 'snap-1',
    status: 'completed',
    is_active: true,
    created_at: '2026-11-07T00:00:00Z',
    node_count: 42,
    edge_count: 68,
    concept_count: 26,
    entity_count: 16,
    component_count: 1,
    isolated_node_count: 2,
    ontology_version: '1.0.0',
  },
  statistics: {
    isolated_node_count: 2,
    connected_component_count: 1,
    density: 0.078,
    self_loops_count: 0,
    parallel_edges_count: 3,
    predicate_distribution: { uses: 24, evaluates_on: 15 },
    node_type_distribution: { algorithm: 14, model: 12 },
    node_kind_distribution: { concept: 26, entity: 16 },
  },
  capabilities: {
    node_search: true,
    neighborhood_expansion: true,
    relationship_details: true,
    source_evidence: true,
    path_exploration: true,
    snapshot_history: true,
  },
};

describe('knowledgeGraphApi Client (C7.7–C7.9)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls getOverview with correct URL', async () => {
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockOverview);

    const result = await knowledgeGraphApi.getOverview('ws-test', 'snap-1');
    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-test/knowledge-graph?snapshot_id=snap-1'
    );
    expect(result.workspace_id).toBe('ws-test');
    expect(result.snapshot?.node_count).toBe(42);
  });

  it('calls searchNodes with query params', async () => {
    const mockNodesResponse: PaginatedGraphNodesResponse = {
      items: [
        {
          id: 'node-1',
          label: 'Dense Embeddings',
          normalized_name: 'dense embeddings',
          node_kind: 'concept',
          node_type: 'technique',
          description: 'Vector representations',
          aliases: ['embeddings'],
          in_degree: 3,
          out_degree: 5,
          degree: 8,
          connected_relationship_count: 8,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
    };

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockNodesResponse);

    const result = await knowledgeGraphApi.searchNodes('ws-test', {
      search: 'dense',
      nodeKind: 'concept',
      pageSize: 20,
    });

    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-test/knowledge-graph/nodes?search=dense&node_kind=concept&page_size=20'
    );
    expect(result.items.length).toBe(1);
    expect(result.items[0].label).toBe('Dense Embeddings');
  });

  it('calls getNodeDetails with URL encoding', async () => {
    const mockDetail: GraphNodeDetailResponse = {
      id: 'node-1',
      workspace_id: 'ws-test',
      label: 'BM25',
      normalized_name: 'bm25',
      node_kind: 'concept',
      node_type: 'algorithm',
      description: 'Lexical ranking algorithm',
      aliases: ['Okapi BM25'],
      ontology_version: '1.0.0',
      in_degree: 2,
      out_degree: 4,
      degree: 6,
      connected_relationship_count: 6,
      mention_count: 12,
      supporting_document_count: 3,
    };

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockDetail);

    const result = await knowledgeGraphApi.getNodeDetails('ws-test', 'node-1');
    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-test/knowledge-graph/nodes/node-1'
    );
    expect(result.label).toBe('BM25');
    expect(result.mention_count).toBe(12);
  });

  it('calls getNeighborhood with bounded traversal parameters', async () => {
    const mockNeighborhood: GraphNeighborhoodResponse = {
      root_node_id: 'node-1',
      depth: 1,
      direction: 'both',
      nodes: [],
      edges: [],
      total_nodes: 5,
      total_edges: 7,
      is_truncated: false,
      available_neighbor_count: 4,
    };

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockNeighborhood);

    const result = await knowledgeGraphApi.getNeighborhood('ws-test', {
      nodeId: 'node-1',
      depth: 1,
      direction: 'both',
      maxNodes: 50,
      maxEdges: 100,
    });

    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-test/knowledge-graph/neighborhood?node_id=node-1&depth=1&direction=both&max_nodes=50&max_edges=100'
    );
    expect(result.root_node_id).toBe('node-1');
  });

  it('calls getRelationships with filters', async () => {
    const mockRels: PaginatedGraphRelationshipsResponse = {
      items: [
        {
          id: 'rel-1',
          source: 'node-1',
          target: 'node-2',
          predicate: 'uses',
          polarity: 'positive',
          is_negated: false,
          modality: 'asserted',
          qualifiers: {},
          confidence: 0.92,
          validation_status: 'valid',
          evidence_count: 2,
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
      total_pages: 1,
    };

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockRels);

    const result = await knowledgeGraphApi.getRelationships('ws-test', {
      predicate: 'uses',
      page: 1,
      pageSize: 50,
    });

    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-test/knowledge-graph/relationships?predicate=uses&page=1&page_size=50'
    );
    expect(result.items.length).toBe(1);
    expect(result.items[0].predicate).toBe('uses');
  });

  it('calls getRelationshipEvidence with pagination', async () => {
    const mockEvidence: PaginatedRelationshipEvidenceResponse = {
      relationship_id: 'rel-1',
      items: [
        {
          id: 'ev-1',
          relationship_id: 'rel-1',
          document_id: 'doc-1',
          document_title: 'Attention is All You Need',
          source_type: 'paper',
          evidence_text: 'The Transformer uses multi-head self-attention.',
          start_offset: 120,
          end_offset: 168,
          confidence: 0.95,
          page_start: 3,
          page_end: 3,
          slide_number: null,
          section_title: 'Model Architecture',
          validation_status: 'verified',
          is_source_available: true,
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
      total_pages: 1,
    };

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockEvidence);

    const result = await knowledgeGraphApi.getRelationshipEvidence('ws-test', 'rel-1', 1, 10);
    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-test/knowledge-graph/relationships/rel-1/evidence?page=1&page_size=10'
    );
    expect(result.items[0].document_title).toBe('Attention is All You Need');
    expect(result.items[0].page_start).toBe(3);
  });

  it('calls getNodeEvidence with pagination', async () => {
    const mockMentions: PaginatedNodeMentionsResponse = {
      node_id: 'node-1',
      items: [
        {
          id: 'men-1',
          node_id: 'node-1',
          surface_form: 'Transformer',
          document_id: 'doc-1',
          document_title: 'Attention is All You Need',
          source_type: 'paper',
          excerpt: 'We propose the Transformer, a model architecture...',
          start_offset: 45,
          end_offset: 56,
          confidence: 0.98,
          extraction_method: 'llm_extracted',
          page_start: 1,
          page_end: 1,
          slide_number: null,
          section_title: 'Abstract',
          is_source_available: true,
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
      total_pages: 1,
    };

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockMentions);

    const result = await knowledgeGraphApi.getNodeEvidence('ws-test', 'node-1', 1, 10);
    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-test/knowledge-graph/nodes/node-1/evidence?page=1&page_size=10'
    );
    expect(result.items[0].surface_form).toBe('Transformer');
    expect(result.items[0].page_start).toBe(1);
  });

  it('calls findPaths with source and target parameters', async () => {
    const mockPaths: GraphPathsResponse = {
      source_node_id: 'node-a',
      target_node_id: 'node-c',
      max_hops: 3,
      path_count: 1,
      paths: [
        {
          path_index: 0,
          hop_count: 2,
          nodes: [],
          edges: [],
          steps: [],
        },
      ],
      no_path_found: false,
    };

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockPaths);

    const result = await knowledgeGraphApi.findPaths('ws-test', {
      sourceNodeId: 'node-a',
      targetNodeId: 'node-c',
      maxHops: 3,
    });

    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-test/knowledge-graph/paths?source_node_id=node-a&target_node_id=node-c&max_hops=3'
    );
    expect(result.paths.length).toBe(1);
    expect(result.no_path_found).toBe(false);
  });

  it('calls listSnapshots with pagination', async () => {
    const mockSnapshots: PaginatedGraphSnapshotsResponse = {
      items: [mockOverview.snapshot!],
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
    };

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockSnapshots);

    const result = await knowledgeGraphApi.listSnapshots('ws-test', 1, 20);
    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-test/knowledge-graph/snapshots?page=1&page_size=20'
    );
    expect(result.items.length).toBe(1);
    expect(result.items[0].is_active).toBe(true);
  });
});
