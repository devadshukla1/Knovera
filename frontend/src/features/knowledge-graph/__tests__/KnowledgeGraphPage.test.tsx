/**
 * Automated component tests for KnowledgeGraphPage (Phase 7 C7.8, C7.9).
 */

import { screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { KnowledgeGraphPage } from '../pages/KnowledgeGraphPage';
import { knowledgeGraphApi } from '../api/knowledgeGraphApi';
import { workspaceApi } from '@/features/workspaces/api/workspaceApi';
import { renderWithProviders } from '@/test/test-utils';
import {
  KnowledgeGraphOverviewResponse,
  PaginatedGraphNodesResponse,
  PaginatedGraphRelationshipsResponse,
  PaginatedGraphSnapshotsResponse,
} from '../types/knowledgeGraph';
import { Workspace } from '@/features/workspaces/types/workspace';

// Mock Cytoscape to run deterministically in JSDOM
vi.mock('cytoscape', () => {
  return {
    default: vi.fn(() => ({
      on: vi.fn(),
      batch: vi.fn((cb: () => void) => cb && cb()),
      add: vi.fn(),
      elements: vi.fn(() => ({
        removeClass: vi.fn().mockReturnThis(),
        addClass: vi.fn().mockReturnThis(),
        remove: vi.fn(),
      })),
      getElementById: vi.fn(() => ({
        length: 1,
        select: vi.fn(),
        unselect: vi.fn(),
      })),
      collection: vi.fn(() => ({
        merge: vi.fn(),
        removeClass: vi.fn().mockReturnThis(),
        addClass: vi.fn().mockReturnThis(),
        length: 2,
      })),
      layout: vi.fn(() => ({
        run: vi.fn(),
        stop: vi.fn(),
      })),
      animate: vi.fn(),
      zoom: vi.fn(() => 1.0),
      fit: vi.fn(),
      reset: vi.fn(),
      destroy: vi.fn(),
      nodes: vi.fn(() => []),
      edges: vi.fn(() => []),
    })),
  };
});

vi.mock('../api/knowledgeGraphApi', () => ({
  knowledgeGraphApi: {
    getOverview: vi.fn(),
    searchNodes: vi.fn(),
    getNodeDetails: vi.fn(),
    getNeighborhood: vi.fn(),
    getRelationships: vi.fn(),
    getRelationshipDetails: vi.fn(),
    getRelationshipEvidence: vi.fn(),
    getNodeEvidence: vi.fn(),
    findPaths: vi.fn(),
    listSnapshots: vi.fn(),
  },
}));

vi.mock('@/features/workspaces/api/workspaceApi', () => ({
  workspaceApi: {
    list: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockWorkspace: Workspace = {
  id: 'ws-123',
  name: 'Information Retrieval Workspace',
  description: 'Research lab for search and knowledge graphs',
  document_count: 5,
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
};

const mockOverview: KnowledgeGraphOverviewResponse = {
  workspace_id: 'ws-123',
  has_graph: true,
  snapshot: {
    id: 'snap-1',
    status: 'completed',
    is_active: true,
    created_at: '2026-11-07T00:00:00Z',
    node_count: 15,
    edge_count: 22,
    concept_count: 10,
    entity_count: 5,
    component_count: 1,
    isolated_node_count: 0,
    ontology_version: '1.0.0',
  },
  statistics: {
    isolated_node_count: 0,
    connected_component_count: 1,
    density: 0.12,
    self_loops_count: 0,
    parallel_edges_count: 2,
    predicate_distribution: { uses: 12, proposes: 10 },
    node_type_distribution: { algorithm: 8, model: 7 },
    node_kind_distribution: { concept: 10, entity: 5 },
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

const mockNodesResponse: PaginatedGraphNodesResponse = {
  items: [
    {
      id: 'node-1',
      label: 'Transformer',
      normalized_name: 'transformer',
      node_kind: 'concept',
      node_type: 'model',
      description: 'Self-attention based neural network architecture.',
      aliases: ['Transformer model'],
      in_degree: 4,
      out_degree: 6,
      degree: 10,
      connected_relationship_count: 10,
    },
    {
      id: 'node-2',
      label: 'Self-Attention',
      normalized_name: 'self-attention',
      node_kind: 'concept',
      node_type: 'algorithm',
      description: 'Attention mechanism relating different positions of a single sequence.',
      aliases: ['intra-attention'],
      in_degree: 3,
      out_degree: 2,
      degree: 5,
      connected_relationship_count: 5,
    },
  ],
  total: 2,
  page: 1,
  page_size: 100,
  total_pages: 1,
};

const mockRelationshipsResponse: PaginatedGraphRelationshipsResponse = {
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
      confidence: 0.95,
      validation_status: 'valid',
      evidence_count: 3,
      source_label: 'Transformer',
      target_label: 'Self-Attention',
    },
  ],
  total: 1,
  page: 1,
  page_size: 150,
  total_pages: 1,
};

const mockSnapshotsResponse: PaginatedGraphSnapshotsResponse = {
  items: [mockOverview.snapshot!],
  total: 1,
  page: 1,
  page_size: 20,
  total_pages: 1,
};

describe('KnowledgeGraphPage (C7.8 & C7.9)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(knowledgeGraphApi.getOverview).mockResolvedValue(mockOverview);
    vi.mocked(knowledgeGraphApi.searchNodes).mockResolvedValue(mockNodesResponse);
    vi.mocked(knowledgeGraphApi.getRelationships).mockResolvedValue(mockRelationshipsResponse);
    vi.mocked(knowledgeGraphApi.listSnapshots).mockResolvedValue(mockSnapshotsResponse);
  });

  it('renders page header, breadcrumbs, and stats panel correctly', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/workspaces/:workspaceId/knowledge-graph" element={<KnowledgeGraphPage />} />
      </Routes>,
      { initialEntries: ['/workspaces/ws-123/knowledge-graph'] }
    );

    // Header Title
    expect(await screen.findByRole('heading', { name: 'Knowledge Graph', level: 1 })).toBeInTheDocument();

    // Breadcrumbs
    expect(screen.getByText('Information Retrieval Workspace')).toBeInTheDocument();

    // Stats ribbon metrics
    expect(screen.getByText('Total Nodes')).toBeInTheDocument();
    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getByText('Relationships')).toBeInTheDocument();
    expect(screen.getByText('22')).toBeInTheDocument();
  });

  it('renders filters, search input, and toolbar', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/workspaces/:workspaceId/knowledge-graph" element={<KnowledgeGraphPage />} />
      </Routes>,
      { initialEntries: ['/workspaces/ws-123/knowledge-graph'] }
    );

    await screen.findByRole('heading', { name: 'Knowledge Graph', level: 1 });

    // Search input
    expect(screen.getByPlaceholderText('Search concepts or entities...')).toBeInTheDocument();

    // Kind filter toggles
    expect(screen.getByTitle('Toggle Concepts visibility')).toBeInTheDocument();
    expect(screen.getByTitle('Toggle Entities visibility')).toBeInTheDocument();

    // Toolbar buttons
    expect(screen.getByTitle('Zoom In')).toBeInTheDocument();
    expect(screen.getByTitle('Zoom Out')).toBeInTheDocument();
    expect(screen.getByTitle('Fit to Screen')).toBeInTheDocument();
  });

  it('displays empty state when workspace has no active graph', async () => {
    const emptyOverview: KnowledgeGraphOverviewResponse = {
      workspace_id: 'ws-123',
      has_graph: false,
      snapshot: null,
      statistics: null,
      capabilities: mockOverview.capabilities,
    };
    vi.mocked(knowledgeGraphApi.getOverview).mockResolvedValueOnce(emptyOverview);

    renderWithProviders(
      <Routes>
        <Route path="/workspaces/:workspaceId/knowledge-graph" element={<KnowledgeGraphPage />} />
      </Routes>,
      { initialEntries: ['/workspaces/ws-123/knowledge-graph'] }
    );

    expect(await screen.findByText('No Knowledge Graph Found')).toBeInTheDocument();
    expect(screen.getByText('Upload Documents')).toBeInTheDocument();
  });

  it('opens path finder modal when button is clicked', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/workspaces/:workspaceId/knowledge-graph" element={<KnowledgeGraphPage />} />
      </Routes>,
      { initialEntries: ['/workspaces/ws-123/knowledge-graph'] }
    );

    await screen.findByRole('heading', { name: 'Knowledge Graph', level: 1 });

    const pathFinderBtns = screen.getAllByRole('button', { name: /path finder/i });
    fireEvent.click(pathFinderBtns[0]);

    expect(await screen.findByText('Knowledge Path Explorer')).toBeInTheDocument();
    expect(screen.getByText('Source Concept / Entity')).toBeInTheDocument();
    expect(screen.getByText('Target Concept / Entity')).toBeInTheDocument();
  });
});
