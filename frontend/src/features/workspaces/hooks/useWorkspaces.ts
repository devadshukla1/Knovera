import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { workspaceApi } from '../api/workspaceApi';
import {
  Workspace,
  CreateWorkspacePayload,
  UpdateWorkspacePayload,
} from '../types/workspace';

export const WORKSPACE_KEYS = {
  all: ['workspaces'] as const,
  lists: () => [...WORKSPACE_KEYS.all, 'list'] as const,
  details: () => [...WORKSPACE_KEYS.all, 'detail'] as const,
  detail: (id: string) => [...WORKSPACE_KEYS.details(), id] as const,
};

/**
 * Hook to retrieve all personal workspaces.
 */
export function useWorkspaces(options?: { retry?: number | boolean }) {
  return useQuery<Workspace[], Error>({
    queryKey: WORKSPACE_KEYS.lists(),
    queryFn: () => workspaceApi.list(),
    staleTime: 1000 * 30, // 30 seconds
    ...(options?.retry !== undefined ? { retry: options.retry } : {}),
  });
}

/**
 * Hook to retrieve a single workspace by ID.
 */
export function useWorkspace(workspaceId: string, options?: { retry?: number | boolean }) {
  return useQuery<Workspace, Error>({
    queryKey: WORKSPACE_KEYS.detail(workspaceId),
    queryFn: () => workspaceApi.getById(workspaceId),
    enabled: Boolean(workspaceId && workspaceId.trim().length > 0),
    staleTime: 1000 * 30,
    ...(options?.retry !== undefined ? { retry: options.retry } : {}),
  });
}

/**
 * Hook to create a new workspace.
 */
export function useCreateWorkspace() {
  const queryClient = useQueryClient();

  return useMutation<Workspace, Error, CreateWorkspacePayload>({
    mutationFn: (payload) => workspaceApi.create(payload),
    onSuccess: (newWorkspace) => {
      // Invalidate the workspace list query to refetch
      queryClient.invalidateQueries({ queryKey: WORKSPACE_KEYS.lists() });
      // Prepopulate the cache for the newly created workspace
      queryClient.setQueryData(
        WORKSPACE_KEYS.detail(newWorkspace.id),
        newWorkspace
      );
    },
  });
}

/**
 * Hook to update/rename a workspace.
 */
export function useUpdateWorkspace() {
  const queryClient = useQueryClient();

  return useMutation<
    Workspace,
    Error,
    { id: string; payload: UpdateWorkspacePayload }
  >({
    mutationFn: ({ id, payload }) => workspaceApi.update(id, payload),
    onSuccess: (updatedWorkspace) => {
      queryClient.invalidateQueries({ queryKey: WORKSPACE_KEYS.lists() });
      queryClient.setQueryData(
        WORKSPACE_KEYS.detail(updatedWorkspace.id),
        updatedWorkspace
      );
    },
  });
}

/**
 * Hook to delete a workspace.
 */
export function useDeleteWorkspace() {
  const queryClient = useQueryClient();

  return useMutation<{ success: boolean; id: string }, Error, string>({
    mutationFn: (id) => workspaceApi.delete(id),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: WORKSPACE_KEYS.lists() });
      queryClient.removeQueries({ queryKey: WORKSPACE_KEYS.detail(deletedId) });
    },
  });
}
