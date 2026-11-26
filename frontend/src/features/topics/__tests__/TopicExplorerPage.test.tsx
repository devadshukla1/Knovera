import { screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { TopicExplorerPage } from '../pages/TopicExplorerPage';
import { topicApi } from '../api/topicApi';
import { workspaceApi } from '@/features/workspaces/api/workspaceApi';
import { renderWithProviders } from '@/test/test-utils';
import { PaginatedTopicsResponse, TopicSummaryItem } from '../types/topic';
import { Workspace } from '@/features/workspaces/types/workspace';

vi.mock('../api/topicApi', () => ({
  topicApi: {
    getTopics: vi.fn(),
    getTopicRuns: vi.fn(),
    getTopicRunDetail: vi.fn(),
    getTopicDetail: vi.fn(),
    getTopicChunks: vi.fn(),
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
  name: 'Information Retrieval Lab',
  description: 'Researching IR pipelines',
  document_count: 5,
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
};

const mockTopics: TopicSummaryItem[] = [
  {
    id: 'topic-1',
    workspace_id: 'ws-123',
    clustering_run_id: 'run-alpha',
    cluster_key: 'cluster_0',
    label: 'Lexical BM25 Ranking',
    description: 'Inverted index retrieval algorithms.',
    label_source: 'keyword_based',
    label_status: 'approved',
    keywords: [
      { term: 'bm25', score: 0.88 },
      { term: 'tf-idf', score: 0.75 },
    ],
    chunk_count: 14,
    document_count: 3,
    representative_chunk_ids: ['chunk-1'],
    created_at: '2026-11-07T00:00:00Z',
    updated_at: '2026-11-07T00:00:00Z',
  },
  {
    id: 'topic-2',
    workspace_id: 'ws-123',
    clustering_run_id: 'run-alpha',
    cluster_key: 'cluster_1',
    label: 'Dense Vector Embeddings',
    description: 'Bi-encoder representation learning.',
    label_source: 'llm_assisted',
    label_status: 'suggested',
    keywords: [
      { term: 'embeddings', score: 0.92 },
      { term: 'chromadb', score: 0.81 },
    ],
    chunk_count: 8,
    document_count: 2,
    representative_chunk_ids: ['chunk-2'],
    created_at: '2026-11-07T00:00:00Z',
    updated_at: '2026-11-07T00:00:00Z',
  },
];

const mockTopicsResponse: PaginatedTopicsResponse = {
  workspace_id: 'ws-123',
  run: {
    id: 'run-alpha',
    workspace_id: 'ws-123',
    snapshot_id: 'snap-1',
    status: 'completed',
    k: 2,
    model_version: 'kmeans_v1_k2',
    is_active: true,
    created_at: '2026-11-07T00:00:00Z',
    completed_at: '2026-11-07T00:01:00Z',
  },
  items: mockTopics,
  total: 2,
  page: 1,
  page_size: 18,
  total_pages: 1,
};

describe('TopicExplorerPage Component (C6.8)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(topicApi.getTopicRuns).mockResolvedValue({
      items: [mockTopicsResponse.run!],
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
  });

  it('renders topic list with summary statistics and topic cards', async () => {
    vi.mocked(topicApi.getTopics).mockResolvedValue(mockTopicsResponse);

    renderWithProviders(
      <Routes>
        <Route path="/app/workspaces/:workspaceId/topics" element={<TopicExplorerPage />} />
      </Routes>,
      { initialEntries: ['/app/workspaces/ws-123/topics'] }
    );

    // Verify Page Header
    expect(await screen.findByRole('heading', { level: 1, name: 'Topic Explorer' })).toBeInTheDocument();

    // Verify Metrics Cards
    expect(await screen.findByText('Discovered Topics')).toBeInTheDocument();
    expect(screen.getByText('Clustered Chunks')).toBeInTheDocument();
    expect(screen.getByText('Documents Covered')).toBeInTheDocument();

    // Verify Topic Cards
    expect(await screen.findByText('Lexical BM25 Ranking')).toBeInTheDocument();
    expect(screen.getByText('Dense Vector Embeddings')).toBeInTheDocument();
    expect(screen.getByText('14')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getAllByText(/chunks/i).length).toBeGreaterThan(0);
    expect(screen.getByText('bm25')).toBeInTheDocument();
    expect(screen.getByText('embeddings')).toBeInTheDocument();
  });

  it('filters topics when user types in search input', async () => {
    vi.mocked(topicApi.getTopics).mockResolvedValue(mockTopicsResponse);

    renderWithProviders(
      <Routes>
        <Route path="/app/workspaces/:workspaceId/topics" element={<TopicExplorerPage />} />
      </Routes>,
      { initialEntries: ['/app/workspaces/ws-123/topics'] }
    );

    expect(await screen.findByText('Lexical BM25 Ranking')).toBeInTheDocument();

    const searchInput = screen.getByPlaceholderText(/search topics/i);
    fireEvent.change(searchInput, { target: { value: 'BM25' } });

    await waitFor(() => {
      expect(topicApi.getTopics).toHaveBeenCalledWith(
        'ws-123',
        expect.objectContaining({ search: 'BM25' })
      );
    });
  });

  it('renders empty state when workspace has no discovered topics', async () => {
    vi.mocked(topicApi.getTopics).mockResolvedValue({
      workspace_id: 'ws-123',
      run: null,
      items: [],
      total: 0,
      page: 1,
      page_size: 18,
      total_pages: 0,
    });

    renderWithProviders(
      <Routes>
        <Route path="/app/workspaces/:workspaceId/topics" element={<TopicExplorerPage />} />
      </Routes>,
      { initialEntries: ['/app/workspaces/ws-123/topics'] }
    );

    expect(await screen.findByText(/no topics discovered yet/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /go to documents/i })).toBeInTheDocument();
  });

  it('renders error state when backend topics fetch fails', async () => {
    vi.mocked(topicApi.getTopics).mockRejectedValue(new Error('Network error loading topics'));

    renderWithProviders(
      <Routes>
        <Route path="/app/workspaces/:workspaceId/topics" element={<TopicExplorerPage />} />
      </Routes>,
      { initialEntries: ['/app/workspaces/ws-123/topics'] }
    );

    expect(await screen.findByText(/failed to load topics/i)).toBeInTheDocument();
    expect(screen.getByText(/network error loading topics/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry request/i })).toBeInTheDocument();
  });
});
