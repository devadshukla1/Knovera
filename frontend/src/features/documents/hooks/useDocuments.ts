import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentApi } from '../api/documentApi';
import { WorkspaceDocument } from '../types/document';
import { WORKSPACE_KEYS } from '@/features/workspaces/hooks/useWorkspaces';

export const DOCUMENT_KEYS = {
  all: ['documents'] as const,
  workspaceDocuments: (workspaceId: string) =>
    ['workspaces', workspaceId, 'documents'] as const,
  documentDetail: (workspaceId: string, documentId: string) =>
    ['workspaces', workspaceId, 'documents', documentId] as const,
};

/**
 * Hook to fetch all documents in a workspace.
 */
export function useDocuments(workspaceId: string, options?: { retry?: number | boolean }) {
  return useQuery<WorkspaceDocument[], Error>({
    queryKey: DOCUMENT_KEYS.workspaceDocuments(workspaceId),
    queryFn: () => documentApi.list(workspaceId),
    enabled: Boolean(workspaceId && workspaceId.trim().length > 0),
    staleTime: 1000 * 20, // 20s
    ...(options?.retry !== undefined ? { retry: options.retry } : {}),
  });
}

/**
 * Hook to fetch a single document's metadata.
 */
export function useDocument(
  workspaceId: string,
  documentId: string,
  options?: { retry?: number | boolean }
) {
  return useQuery<WorkspaceDocument, Error>({
    queryKey: DOCUMENT_KEYS.documentDetail(workspaceId, documentId),
    queryFn: () => documentApi.getById(workspaceId, documentId),
    enabled: Boolean(
      workspaceId &&
        workspaceId.trim().length > 0 &&
        documentId &&
        documentId.trim().length > 0
    ),
    staleTime: 1000 * 20,
    ...(options?.retry !== undefined ? { retry: options.retry } : {}),
  });
}

/**
 * Hook to upload a document.
 */
export function useUploadDocument(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<WorkspaceDocument, Error, File>({
    mutationFn: (file: File) => documentApi.upload(workspaceId, file),
    onSuccess: (newDoc) => {
      // Invalidate the documents list query for this workspace
      queryClient.invalidateQueries({
        queryKey: DOCUMENT_KEYS.workspaceDocuments(workspaceId),
      });
      // Invalidate workspace details to refresh document_count
      queryClient.invalidateQueries({
        queryKey: WORKSPACE_KEYS.detail(workspaceId),
      });
      // Pre-set document detail in cache
      queryClient.setQueryData(
        DOCUMENT_KEYS.documentDetail(workspaceId, newDoc.id),
        newDoc
      );
    },
  });
}

/**
 * Hook to retry a failed processing job.
 */
export function useRetryDocument(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<{ success: boolean }, Error, string>({
    mutationFn: (documentId: string) =>
      documentApi.retry(workspaceId, documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: DOCUMENT_KEYS.workspaceDocuments(workspaceId),
      });
    },
  });
}

/**
 * Hook to delete a document.
 */
export function useDeleteDocument(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<{ success: boolean; id: string }, Error, string>({
    mutationFn: (documentId: string) =>
      documentApi.delete(workspaceId, documentId),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({
        queryKey: DOCUMENT_KEYS.workspaceDocuments(workspaceId),
      });
      queryClient.invalidateQueries({
        queryKey: WORKSPACE_KEYS.detail(workspaceId),
      });
      queryClient.removeQueries({
        queryKey: DOCUMENT_KEYS.documentDetail(workspaceId, deletedId),
      });
    },
  });
}
