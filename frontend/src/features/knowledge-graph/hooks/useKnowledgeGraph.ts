/**
 * TanStack Query hooks for Knowledge Graph (Phase 7 C7.7–C7.9).
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  knowledgeGraphApi,
  SearchNodesParams,
  GetNeighborhoodParams,
  GetRelationshipsParams,
  FindPathsParams,
} from '../api/knowledgeGraphApi';

export const knowledgeGraphKeys = {
  all: ['knowledge-graph'] as const,
  overview: (workspaceId: string, snapshotId?: string) =>
    [...knowledgeGraphKeys.all, 'overview', workspaceId, snapshotId || 'active'] as const,
  snapshots: (workspaceId: string, page: number, pageSize: number) =>
    [...knowledgeGraphKeys.all, 'snapshots', workspaceId, page, pageSize] as const,
  search: (workspaceId: string, params: SearchNodesParams) =>
    [...knowledgeGraphKeys.all, 'search', workspaceId, params] as const,
  neighborhood: (workspaceId: string, params: GetNeighborhoodParams) =>
    [...knowledgeGraphKeys.all, 'neighborhood', workspaceId, params] as const,
  relationships: (workspaceId: string, params: GetRelationshipsParams) =>
    [...knowledgeGraphKeys.all, 'relationships', workspaceId, params] as const,
  nodeDetails: (workspaceId: string, nodeId: string, snapshotId?: string) =>
    [...knowledgeGraphKeys.all, 'node', workspaceId, nodeId, snapshotId || 'active'] as const,
  relDetails: (workspaceId: string, relId: string, snapshotId?: string) =>
    [...knowledgeGraphKeys.all, 'relationship', workspaceId, relId, snapshotId || 'active'] as const,
  relEvidence: (workspaceId: string, relId: string, page: number) =>
    [...knowledgeGraphKeys.all, 'rel-evidence', workspaceId, relId, page] as const,
  nodeEvidence: (workspaceId: string, nodeId: string, page: number) =>
    [...knowledgeGraphKeys.all, 'node-evidence', workspaceId, nodeId, page] as const,
  paths: (workspaceId: string, params: FindPathsParams) =>
    [...knowledgeGraphKeys.all, 'paths', workspaceId, params] as const,
  mindMap: (workspaceId: string) =>
    [...knowledgeGraphKeys.all, 'mind-map', workspaceId] as const,
};

export function useKnowledgeGraphOverview(workspaceId: string, snapshotId?: string) {
  return useQuery({
    queryKey: knowledgeGraphKeys.overview(workspaceId, snapshotId),
    queryFn: () => knowledgeGraphApi.getOverview(workspaceId, snapshotId),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });
}

export function useKnowledgeGraphSnapshots(workspaceId: string, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: knowledgeGraphKeys.snapshots(workspaceId, page, pageSize),
    queryFn: () => knowledgeGraphApi.listSnapshots(workspaceId, page, pageSize),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });
}

export function useKnowledgeGraphSearch(workspaceId: string, params: SearchNodesParams, enabled = true) {
  return useQuery({
    queryKey: knowledgeGraphKeys.search(workspaceId, params),
    queryFn: () => knowledgeGraphApi.searchNodes(workspaceId, params),
    enabled: Boolean(workspaceId) && enabled,
    staleTime: 30_000,
  });
}

export function useKnowledgeGraphNeighborhood(
  workspaceId: string,
  params: GetNeighborhoodParams,
  enabled = true
) {
  return useQuery({
    queryKey: knowledgeGraphKeys.neighborhood(workspaceId, params),
    queryFn: () => knowledgeGraphApi.getNeighborhood(workspaceId, params),
    enabled: Boolean(workspaceId) && Boolean(params.nodeId) && enabled,
    staleTime: 120_000,
  });
}

export function useKnowledgeGraphRelationships(
  workspaceId: string,
  params: GetRelationshipsParams = {},
  enabled = true
) {
  return useQuery({
    queryKey: knowledgeGraphKeys.relationships(workspaceId, params),
    queryFn: () => knowledgeGraphApi.getRelationships(workspaceId, params),
    enabled: Boolean(workspaceId) && enabled,
    staleTime: 60_000,
  });
}

export function useKnowledgeGraphNodeDetails(workspaceId: string, nodeId?: string, snapshotId?: string) {
  return useQuery({
    queryKey: knowledgeGraphKeys.nodeDetails(workspaceId, nodeId || '', snapshotId),
    queryFn: () => knowledgeGraphApi.getNodeDetails(workspaceId, nodeId!, snapshotId),
    enabled: Boolean(workspaceId) && Boolean(nodeId),
    staleTime: 60_000,
  });
}

export function useKnowledgeGraphRelationshipDetails(
  workspaceId: string,
  relationshipId?: string,
  snapshotId?: string
) {
  return useQuery({
    queryKey: knowledgeGraphKeys.relDetails(workspaceId, relationshipId || '', snapshotId),
    queryFn: () => knowledgeGraphApi.getRelationshipDetails(workspaceId, relationshipId!, snapshotId),
    enabled: Boolean(workspaceId) && Boolean(relationshipId),
    staleTime: 60_000,
  });
}

export function useKnowledgeGraphRelationshipEvidence(
  workspaceId: string,
  relationshipId?: string,
  page = 1,
  pageSize = 10
) {
  return useQuery({
    queryKey: knowledgeGraphKeys.relEvidence(workspaceId, relationshipId || '', page),
    queryFn: () => knowledgeGraphApi.getRelationshipEvidence(workspaceId, relationshipId!, page, pageSize),
    enabled: Boolean(workspaceId) && Boolean(relationshipId),
    staleTime: 60_000,
  });
}

export function useKnowledgeGraphNodeEvidence(
  workspaceId: string,
  nodeId?: string,
  page = 1,
  pageSize = 10
) {
  return useQuery({
    queryKey: knowledgeGraphKeys.nodeEvidence(workspaceId, nodeId || '', page),
    queryFn: () => knowledgeGraphApi.getNodeEvidence(workspaceId, nodeId!, page, pageSize),
    enabled: Boolean(workspaceId) && Boolean(nodeId),
    staleTime: 60_000,
  });
}

export function useKnowledgeGraphPaths(workspaceId: string, params: FindPathsParams, enabled = false) {
  return useQuery({
    queryKey: knowledgeGraphKeys.paths(workspaceId, params),
    queryFn: () => knowledgeGraphApi.findPaths(workspaceId, params),
    enabled: Boolean(workspaceId) && Boolean(params.sourceNodeId) && Boolean(params.targetNodeId) && enabled,
    staleTime: 120_000,
  });
}

export function useBuildKnowledgeGraph(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => knowledgeGraphApi.buildGraph(workspaceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: knowledgeGraphKeys.all });
    },
  });
}

export function useUpdateNodeStatus(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      nodeId,
      status,
    }: {
      nodeId: string;
      status: 'not_started' | 'in_progress' | 'learned' | 'needs_revision';
    }) => knowledgeGraphApi.updateNodeLearningStatus(workspaceId, nodeId, status),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: knowledgeGraphKeys.nodeDetails(workspaceId, variables.nodeId),
      });
      queryClient.invalidateQueries({
        queryKey: [...knowledgeGraphKeys.all, 'search', workspaceId],
      });
    },
  });
}

export function useMindMap(workspaceId: string, forceRebuild = false) {
  return useQuery({
    queryKey: knowledgeGraphKeys.mindMap(workspaceId),
    queryFn: () => knowledgeGraphApi.getMindMap(workspaceId, forceRebuild),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });
}

export function useBuildMindMap(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => knowledgeGraphApi.buildMindMap(workspaceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: knowledgeGraphKeys.mindMap(workspaceId) });
      queryClient.invalidateQueries({ queryKey: knowledgeGraphKeys.all });
    },
  });
}

export function useUpdateMindMapNodeStatus(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      nodeId,
      status,
    }: {
      nodeId: string;
      status: string;
    }) => knowledgeGraphApi.updateMindMapNodeStatus(workspaceId, nodeId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: knowledgeGraphKeys.mindMap(workspaceId) });
    },
  });
}
