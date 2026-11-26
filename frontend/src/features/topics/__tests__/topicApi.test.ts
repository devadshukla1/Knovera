import { describe, it, expect, vi, beforeEach } from 'vitest';
import { topicApi } from '../api/topicApi';
import * as apiModule from '@/services/api';
import {
  PaginatedTopicChunksResponse,
  PaginatedTopicRunsResponse,
  PaginatedTopicsResponse,
  TopicDetail,
  TopicRunDetail,
  TopicSummaryItem,
} from '../types/topic';

vi.mock('@/services/api', async () => {
  const actual = await vi.importActual<typeof apiModule>('@/services/api');
  return {
    ...actual,
    apiFetch: vi.fn(),
  };
});

const mockTopic: TopicSummaryItem = {
  id: 'topic-1',
  workspace_id: 'ws-123',
  clustering_run_id: 'run-999',
  cluster_key: 'cluster_0',
  label: 'Lexical BM25 Ranking',
  description: 'Inverted index retrieval algorithms.',
  label_source: 'keyword_based',
  label_status: 'approved',
  keywords: [
    { term: 'bm25', score: 0.88 },
    { term: 'tf-idf', score: 0.75 },
  ],
  chunk_count: 5,
  document_count: 2,
  representative_chunk_ids: ['chunk-1'],
  created_at: '2026-11-07T00:00:00Z',
  updated_at: '2026-11-07T00:00:00Z',
};

const mockTopicsResponse: PaginatedTopicsResponse = {
  workspace_id: 'ws-123',
  run: {
    id: 'run-999',
    workspace_id: 'ws-123',
    snapshot_id: 'snap-1',
    status: 'completed',
    k: 3,
    model_version: 'kmeans_v1_k3',
    is_active: true,
    created_at: '2026-11-07T00:00:00Z',
  },
  items: [mockTopic],
  total: 1,
  page: 1,
  page_size: 20,
  total_pages: 1,
};

describe('topicApi Client (C6.7 & C6.8)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getTopics', () => {
    it('fetches topics with default paginated query params', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue(mockTopicsResponse);

      const res = await topicApi.getTopics('ws-123');
      expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-123/topics?paginate=true');
      expect(res).toEqual(mockTopicsResponse);
    });

    it('passes search, sort, and pagination parameters correctly', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue(mockTopicsResponse);

      await topicApi.getTopics('ws-123', {
        search: 'ranking',
        sort_by: 'chunk_count',
        sort_order: 'desc',
        page: 2,
        page_size: 10,
        run_id: 'run-historical',
      });

      const expectedUrl =
        'workspaces/ws-123/topics?paginate=true&run_id=run-historical&search=ranking&sort_by=chunk_count&sort_order=desc&page=2&page_size=10';
      expect(apiModule.apiFetch).toHaveBeenCalledWith(expectedUrl);
    });

    it('normalizes raw array into PaginatedTopicsResponse', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue([mockTopic]);

      const res = await topicApi.getTopics('ws-123');
      expect(res.items).toEqual([mockTopic]);
      expect(res.total).toBe(1);
      expect(res.total_pages).toBe(1);
    });
  });

  describe('getTopicRuns', () => {
    it('fetches historical clustering runs with pagination', async () => {
      const mockRunsResponse: PaginatedTopicRunsResponse = {
        items: [
          {
            id: 'run-999',
            workspace_id: 'ws-123',
            snapshot_id: 'snap-1',
            status: 'completed',
            k: 3,
            model_version: 'kmeans_v1_k3',
            is_active: true,
            created_at: '2026-11-07T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 10,
        total_pages: 1,
      };

      vi.mocked(apiModule.apiFetch).mockResolvedValue(mockRunsResponse);

      const res = await topicApi.getTopicRuns('ws-123', 1, 10);
      expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-123/topic-runs?page=1&page_size=10');
      expect(res.items.length).toBe(1);
    });
  });

  describe('getTopicRunDetail', () => {
    it('fetches detail for a single clustering run', async () => {
      const mockRunDetail: TopicRunDetail = {
        id: 'run-999',
        workspace_id: 'ws-123',
        snapshot_id: 'snap-1',
        status: 'completed',
        algorithm: 'kmeans',
        model_version: 'kmeans_v1_k3',
        embedding_model_id: 'all-MiniLM-L6-v2',
        embedding_dimension: 384,
        k: 3,
        configuration: { n_init: 20 },
        evaluation_metrics: { silhouette: 0.65 },
        selection_metadata: { status: 'conclusive' },
        corpus_snapshot_hash: 'hash-abc',
        created_at: '2026-11-07T00:00:00Z',
        is_active: true,
        topic_count: 3,
        total_assignments: 15,
      };

      vi.mocked(apiModule.apiFetch).mockResolvedValue(mockRunDetail);

      const res = await topicApi.getTopicRunDetail('ws-123', 'run-999');
      expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-123/topic-runs/run-999');
      expect(res.id).toBe('run-999');
      expect(res.algorithm).toBe('kmeans');
    });
  });

  describe('getTopicDetail', () => {
    it('fetches topic detail by topic ID', async () => {
      const mockDetail: TopicDetail = {
        ...mockTopic,
        cluster_statistics: { size: 5, mean_distance: 0.22 },
        run_summary: mockTopicsResponse.run,
      };

      vi.mocked(apiModule.apiFetch).mockResolvedValue(mockDetail);

      const res = await topicApi.getTopicDetail('ws-123', 'topic-1');
      expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-123/topics/topic-1');
      expect(res.label).toBe('Lexical BM25 Ranking');
    });
  });

  describe('getTopicChunks', () => {
    it('fetches paginated chunks assigned to topic', async () => {
      const mockChunksRes: PaginatedTopicChunksResponse = {
        topic_id: 'topic-1',
        topic_label: 'Lexical BM25 Ranking',
        items: [
          {
            assignment_id: 'assign-1',
            chunk_id: 'chunk-1',
            document_id: 'doc-1',
            document_title: 'Information_Retrieval.pdf',
            chunk_index: 0,
            distance_to_centroid: 0.12,
            is_representative: true,
            page_start: 1,
            page_end: 2,
            content_preview: 'BM25 scoring snippet...',
            source_type: 'application/pdf',
          },
        ],
        total: 1,
        page: 1,
        page_size: 10,
        total_pages: 1,
      };

      vi.mocked(apiModule.apiFetch).mockResolvedValue(mockChunksRes);

      const res = await topicApi.getTopicChunks('ws-123', 'topic-1', {
        page: 1,
        page_size: 10,
        representative_only: true,
      });

      expect(apiModule.apiFetch).toHaveBeenCalledWith(
        'workspaces/ws-123/topics/topic-1/chunks?page=1&page_size=10&representative_only=true'
      );
      expect(res.items.length).toBe(1);
      expect(res.items[0].is_representative).toBe(true);
    });
  });
});
