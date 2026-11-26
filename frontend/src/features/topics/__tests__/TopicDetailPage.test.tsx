import { screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { TopicDetailPage } from '../pages/TopicDetailPage';
import { topicApi } from '../api/topicApi';
import { workspaceApi } from '@/features/workspaces/api/workspaceApi';
import { renderWithProviders } from '@/test/test-utils';
import { TopicDetail, PaginatedTopicChunksResponse } from '../types/topic';
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

const mockTopicDetail: TopicDetail = {
  id: 'topic-1',
  workspace_id: 'ws-123',
  clustering_run_id: 'run-alpha',
  cluster_key: 'cluster_0',
  label: 'Lexical BM25 Ranking',
  description: 'Inverted index retrieval algorithms and probabilistic scoring.',
  label_source: 'keyword_based',
  label_status: 'approved',
  keywords: [
    { term: 'bm25', score: 0.88 },
    { term: 'tf-idf', score: 0.75 },
    { term: 'probabilistic', score: 0.62 },
  ],
  chunk_count: 5,
  document_count: 2,
  representative_chunk_ids: ['chunk-1'],
  cluster_statistics: { size: 5, mean_distance: 0.18 },
  created_at: '2026-11-07T00:00:00Z',
  updated_at: '2026-11-07T00:00:00Z',
  run_summary: {
    id: 'run-alpha',
    workspace_id: 'ws-123',
    snapshot_id: 'snap-1',
    status: 'completed',
    k: 3,
    model_version: 'kmeans_v1_k3',
    is_active: true,
    created_at: '2026-11-07T00:00:00Z',
  },
};

const mockChunksResponse: PaginatedTopicChunksResponse = {
  topic_id: 'topic-1',
  topic_label: 'Lexical BM25 Ranking',
  items: [
    {
      assignment_id: 'assign-1',
      chunk_id: 'chunk-1',
      document_id: 'doc-1',
      document_title: 'An Introduction to Information Retrieval.pdf',
      chunk_index: 0,
      distance_to_centroid: 0.12,
      is_representative: true,
      page_start: 3,
      page_end: 4,
      content_preview: 'BM25 is a ranking function used by search engines to rank matching documents...',
      source_type: 'application/pdf',
    },
    {
      assignment_id: 'assign-2',
      chunk_id: 'chunk-2',
      document_id: 'doc-2',
      document_title: 'Lucene Practical Guide.pdf',
      chunk_index: 1,
      distance_to_centroid: 0.28,
      is_representative: false,
      page_start: 12,
      page_end: 12,
      content_preview: 'Configuring BM25 parameters k1 and b in the similarity module...',
      source_type: 'application/pdf',
    },
  ],
  total: 2,
  page: 1,
  page_size: 15,
  total_pages: 1,
};

describe('TopicDetailPage Component (C6.8)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(topicApi.getTopicDetail).mockResolvedValue(mockTopicDetail);
    vi.mocked(topicApi.getTopicChunks).mockResolvedValue(mockChunksResponse);
  });

  it('renders topic header, keyword cloud, and assigned chunks list', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/app/workspaces/:workspaceId/topics/:topicId" element={<TopicDetailPage />} />
      </Routes>,
      { initialEntries: ['/app/workspaces/ws-123/topics/topic-1'] }
    );

    // Verify Title
    expect(await screen.findByRole('heading', { level: 1, name: 'Lexical BM25 Ranking' })).toBeInTheDocument();

    // Verify Badges
    expect(screen.getByText('Cluster #0')).toBeInTheDocument();
    expect(screen.getByText('Approved')).toBeInTheDocument();

    // Verify Keywords
    expect(screen.getByText('bm25')).toBeInTheDocument();
    expect(screen.getByText('tf-idf')).toBeInTheDocument();
    expect(screen.getByText('probabilistic')).toBeInTheDocument();

    // Verify Assigned Chunks
    expect(await screen.findByText(/assigned chunks \(2\)/i)).toBeInTheDocument();
    expect(screen.getByText('An Introduction to Information Retrieval.pdf')).toBeInTheDocument();
    expect(screen.getByText('Lucene Practical Guide.pdf')).toBeInTheDocument();
    expect(screen.getByText(/page 3–4/i)).toBeInTheDocument();
    expect(screen.getByText('Representative')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /centroid representatives only/i })).toBeInTheDocument();
  });

  it('renders not found error state when topic does not exist', async () => {
    vi.mocked(topicApi.getTopicDetail).mockRejectedValue(new Error('Topic not found in workspace'));

    renderWithProviders(
      <Routes>
        <Route path="/app/workspaces/:workspaceId/topics/:topicId" element={<TopicDetailPage />} />
      </Routes>,
      { initialEntries: ['/app/workspaces/ws-123/topics/topic-missing'] }
    );

    expect(await screen.findByRole('heading', { name: 'Topic not found' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to topics/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry request/i })).toBeInTheDocument();
  });
});
