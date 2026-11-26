/**
 * Automated component tests for KnowledgeGraphPage (Phase 7 C7.8, C7.9).
 */

import { screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { KnowledgeGraphPage } from '../pages/KnowledgeGraphPage';
import { knowledgeGraphApi } from '../api/knowledgeGraphApi';
import { workspaceApi } from '@/features/workspaces/api/workspaceApi';
import { renderWithProviders } from '@/test/test-utils';
import {
  MindMapTreeResponse,
  PaginatedGraphNodesResponse,
  PaginatedGraphRelationshipsResponse,
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
    getMindMap: vi.fn(),
    buildMindMap: vi.fn(),
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

const mockMindMap: MindMapTreeResponse = {
  workspace_id: 'ws-123', workspace_name: mockWorkspace.name,
  root_node_id: 'root', nodes: [
    { id: 'root', label: 'Information Retrieval', level: 0, node_type: 'root', children_count: 0 },
  ], edges: [], total_nodes: 1, total_leaves: 0, depth: 0, source_document_count: 1,
};

vi.mock('@/features/documents/hooks/useDocuments', () => ({
  useDocuments: () => ({ data: [] }),
}));
vi.mock('@/features/topics/hooks/useTopics', () => ({
  useWorkspaceTopics: () => ({ data: { items: [], total: 0 } }),
}));

describe('KnowledgeGraphPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(knowledgeGraphApi.getMindMap).mockResolvedValue(mockMindMap);
    vi.mocked(knowledgeGraphApi.buildMindMap).mockResolvedValue(mockMindMap);
    vi.mocked(knowledgeGraphApi.searchNodes).mockResolvedValue(mockNodesResponse);
    vi.mocked(knowledgeGraphApi.getRelationships).mockResolvedValue(mockRelationshipsResponse);
  });

  const renderPage = () => renderWithProviders(
    <Routes><Route path="/workspaces/:workspaceId/knowledge-graph" element={<KnowledgeGraphPage />} /></Routes>,
    { initialEntries: ['/workspaces/ws-123/knowledge-graph'] }
  );

  it('renders the mind map header, workspace link, and hierarchy summary', async () => {
    renderPage();
    expect(screen.getByRole('heading', { name: 'Knovera Mind Map', level: 1 })).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: mockWorkspace.name })).toHaveAttribute('href', '/app/workspaces/ws-123');
    expect(await screen.findByText('Workspace Hierarchy:')).toBeInTheDocument();
    expect(knowledgeGraphApi.getMindMap).toHaveBeenCalledWith('ws-123', false);
  });

  it('updates concept search and switches to network mode', async () => {
    renderPage();
    await screen.findByText('Workspace Hierarchy:');
    const search = screen.getByPlaceholderText('Search concepts, formulas, definitions, algorithms...');
    fireEvent.change(search, { target: { value: 'retrieval' } });
    expect(search).toHaveValue('retrieval');
    fireEvent.click(screen.getByRole('button', { name: 'Network' }));
    expect(screen.queryByPlaceholderText('Search concepts, formulas, definitions, algorithms...')).not.toBeInTheDocument();
    await waitFor(() => expect(knowledgeGraphApi.searchNodes).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Mind Map' }));
    expect(screen.getByPlaceholderText('Search concepts, formulas, definitions, algorithms...')).toHaveValue('retrieval');
  });

  it('links to document upload when no documents or map exist', async () => {
    vi.mocked(knowledgeGraphApi.getMindMap).mockResolvedValue({ ...mockMindMap, nodes: [], total_nodes: 0 });
    renderPage();
    expect(await screen.findByText('No Documents in this Workspace')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Upload Documents/i })).toHaveAttribute('href', '/app/workspaces/ws-123/documents');
  });

  it('rebuilds the mind map and reports the source document count', async () => {
    renderPage();
    await screen.findByText('Workspace Hierarchy:');
    fireEvent.click(screen.getByRole('button', { name: /Rebuild Mind Map/i }));
    expect(await screen.findByText('Knowledge Graph successfully rebuilt from 1 workspace document.')).toBeInTheDocument();
    expect(knowledgeGraphApi.buildMindMap).toHaveBeenCalledWith('ws-123');
  });
});
