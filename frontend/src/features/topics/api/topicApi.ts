/**
 * Knovera Topic Discovery API Client (Phase 6 C6.7 & C6.8).
 */

import { apiFetch } from '@/services/api';
import {
  PaginatedTopicChunksResponse,
  PaginatedTopicRunsResponse,
  PaginatedTopicsResponse,
  TopicDetail,
  TopicRunDetail,
  TopicSummaryItem,
} from '../types/topic';

export interface GetTopicsParams {
  run_id?: string;
  search?: string;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  page_size?: number;
}

export interface GetTopicChunksParams {
  page?: number;
  page_size?: number;
  representative_only?: boolean;
}

export const topicApi = {
  /**
   * Fetches topics for a workspace with optional search, sorting, and pagination.
   */
  async getTopics(
    workspaceId: string,
    params: GetTopicsParams = {}
  ): Promise<PaginatedTopicsResponse> {
    const query = new URLSearchParams();
    query.set('paginate', 'true');
    if (params.run_id) query.set('run_id', params.run_id);
    if (params.search && params.search.trim()) query.set('search', params.search.trim());
    if (params.sort_by) query.set('sort_by', params.sort_by);
    if (params.sort_order) query.set('sort_order', params.sort_order);
    if (params.page !== undefined) query.set('page', String(params.page));
    if (params.page_size !== undefined) query.set('page_size', String(params.page_size));

    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/topics${qs ? `?${qs}` : ''}`;
    const data = await apiFetch<PaginatedTopicsResponse | TopicSummaryItem[]>(endpoint);

    // Normalize envelope if backend returned an unpaginated array
    if (Array.isArray(data)) {
      return {
        workspace_id: workspaceId,
        run: null,
        items: data,
        total: data.length,
        page: 1,
        page_size: data.length || 20,
        total_pages: data.length > 0 ? 1 : 0,
      };
    }

    return data;
  },

  /**
   * Fetches historical clustering runs for a workspace.
   */
  async getTopicRuns(
    workspaceId: string,
    page = 1,
    pageSize = 20
  ): Promise<PaginatedTopicRunsResponse> {
    const query = new URLSearchParams();
    query.set('page', String(page));
    query.set('page_size', String(pageSize));

    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/topic-runs?${query.toString()}`;
    return apiFetch<PaginatedTopicRunsResponse>(endpoint);
  },

  /**
   * Fetches full metadata and metrics for an individual clustering run.
   */
  async getTopicRunDetail(
    workspaceId: string,
    runId: string
  ): Promise<TopicRunDetail> {
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/topic-runs/${encodeURIComponent(runId)}`;
    return apiFetch<TopicRunDetail>(endpoint);
  },

  /**
   * Fetches detailed topic metadata, statistics, and keywords.
   */
  async getTopicDetail(
    workspaceId: string,
    topicId: string
  ): Promise<TopicDetail> {
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/topics/${encodeURIComponent(topicId)}`;
    return apiFetch<TopicDetail>(endpoint);
  },

  /**
   * Fetches paginated document chunks assigned to a topic.
   */
  async getTopicChunks(
    workspaceId: string,
    topicId: string,
    params: GetTopicChunksParams = {}
  ): Promise<PaginatedTopicChunksResponse> {
    const query = new URLSearchParams();
    if (params.page !== undefined) query.set('page', String(params.page));
    if (params.page_size !== undefined) query.set('page_size', String(params.page_size));
    if (params.representative_only) query.set('representative_only', 'true');

    const qs = query.toString();
    const endpoint = `workspaces/${encodeURIComponent(workspaceId)}/topics/${encodeURIComponent(topicId)}/chunks${
      qs ? `?${qs}` : ''
    }`;
    return apiFetch<PaginatedTopicChunksResponse>(endpoint);
  },
};
