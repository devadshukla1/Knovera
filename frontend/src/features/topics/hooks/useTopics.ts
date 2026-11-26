import { useQuery } from '@tanstack/react-query';
import {
  GetTopicChunksParams,
  GetTopicsParams,
  topicApi,
} from '../api/topicApi';
import {
  PaginatedTopicChunksResponse,
  PaginatedTopicRunsResponse,
  PaginatedTopicsResponse,
  TopicDetail,
  TopicRunDetail,
} from '../types/topic';

export const TOPIC_KEYS = {
  all: ['topics'] as const,
  workspaceTopics: (workspaceId: string, params?: GetTopicsParams) =>
    ['workspaces', workspaceId, 'topics', params] as const,
  workspaceTopicRuns: (workspaceId: string, page?: number, pageSize?: number) =>
    ['workspaces', workspaceId, 'topic-runs', page, pageSize] as const,
  topicRunDetail: (workspaceId: string, runId: string) =>
    ['workspaces', workspaceId, 'topic-runs', runId] as const,
  topicDetail: (workspaceId: string, topicId: string) =>
    ['workspaces', workspaceId, 'topics', topicId] as const,
  topicChunks: (workspaceId: string, topicId: string, params?: GetTopicChunksParams) =>
    ['workspaces', workspaceId, 'topics', topicId, 'chunks', params] as const,
};

/**
 * Hook to fetch paginated topics for a workspace with filter & sorting parameters.
 */
export function useWorkspaceTopics(
  workspaceId: string,
  params?: GetTopicsParams,
  options?: { enabled?: boolean }
) {
  return useQuery<PaginatedTopicsResponse, Error>({
    queryKey: TOPIC_KEYS.workspaceTopics(workspaceId, params),
    queryFn: () => topicApi.getTopics(workspaceId, params),
    enabled: options?.enabled !== false && Boolean(workspaceId && workspaceId.trim().length > 0),
    staleTime: 1000 * 30, // 30s
  });
}

/**
 * Hook to fetch historical topic runs for a workspace.
 */
export function useTopicRuns(
  workspaceId: string,
  page = 1,
  pageSize = 20
) {
  return useQuery<PaginatedTopicRunsResponse, Error>({
    queryKey: TOPIC_KEYS.workspaceTopicRuns(workspaceId, page, pageSize),
    queryFn: () => topicApi.getTopicRuns(workspaceId, page, pageSize),
    enabled: Boolean(workspaceId && workspaceId.trim().length > 0),
    staleTime: 1000 * 60,
  });
}

/**
 * Hook to fetch metadata for a single clustering run.
 */
export function useTopicRunDetail(
  workspaceId: string,
  runId: string
) {
  return useQuery<TopicRunDetail, Error>({
    queryKey: TOPIC_KEYS.topicRunDetail(workspaceId, runId),
    queryFn: () => topicApi.getTopicRunDetail(workspaceId, runId),
    enabled: Boolean(workspaceId && runId),
    staleTime: 1000 * 60,
  });
}

/**
 * Hook to fetch an individual topic's detail.
 */
export function useTopicDetail(
  workspaceId: string,
  topicId: string
) {
  return useQuery<TopicDetail, Error>({
    queryKey: TOPIC_KEYS.topicDetail(workspaceId, topicId),
    queryFn: () => topicApi.getTopicDetail(workspaceId, topicId),
    enabled: Boolean(workspaceId && topicId),
    staleTime: 1000 * 30,
  });
}

/**
 * Hook to fetch paginated chunks assigned to a topic.
 */
export function useTopicChunks(
  workspaceId: string,
  topicId: string,
  params?: GetTopicChunksParams
) {
  return useQuery<PaginatedTopicChunksResponse, Error>({
    queryKey: TOPIC_KEYS.topicChunks(workspaceId, topicId, params),
    queryFn: () => topicApi.getTopicChunks(workspaceId, topicId, params),
    enabled: Boolean(workspaceId && topicId),
    staleTime: 1000 * 30,
  });
}
