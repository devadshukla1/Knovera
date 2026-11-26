/**
 * Knovera Document API Client
 *
 * Implements REST calls to backend document endpoints under
 * /api/v1/workspaces/{workspaceId}/documents.
 */

import { apiFetch, getApiBaseUrl, ApiClientError } from '@/services/api';
import { WorkspaceDocument } from '../types/document';

export const documentApi = {
  /**
   * Fetches all documents belonging to a specific workspace.
   */
  async list(workspaceId: string): Promise<WorkspaceDocument[]> {
    const data = await apiFetch<
      WorkspaceDocument[] | { documents: WorkspaceDocument[] }
    >(`workspaces/${encodeURIComponent(workspaceId)}/documents`);

    if (Array.isArray(data)) {
      return data;
    }
    if (data && Array.isArray(data.documents)) {
      return data.documents;
    }
    return [];
  },

  /**
   * Fetches a single document's metadata by ID.
   */
  async getById(
    workspaceId: string,
    documentId: string
  ): Promise<WorkspaceDocument> {
    return apiFetch<WorkspaceDocument>(
      `workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(documentId)}`
    );
  },

  /**
   * Uploads a document to the workspace using multipart/form-data.
   */
  async upload(
    workspaceId: string,
    file: File
  ): Promise<WorkspaceDocument> {
    const baseUrl = getApiBaseUrl();
    const endpoint = `${baseUrl}/workspaces/${encodeURIComponent(workspaceId)}/documents`;

    const formData = new FormData();
    formData.append('file', file);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60000); // 60s timeout for uploads

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
        },
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timer);

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        let detail = `HTTP ${response.status}: Failed to upload document.`;
        if (errorData) {
          if (typeof errorData.detail === 'string') {
            detail = errorData.detail;
          } else if (errorData.detail && typeof errorData.detail === 'object') {
            detail = errorData.detail.message || errorData.detail.error || JSON.stringify(errorData.detail);
          } else if (typeof errorData.message === 'string') {
            detail = errorData.message;
          }
        }
        const errorCode =
          errorData?.detail?.error_code ||
          errorData?.detail?.code ||
          (response.status === 409 ? 'DUPLICATE_DOCUMENT' : 'UPLOAD_FAILED');
        throw new ApiClientError(detail, response.status, errorCode, errorData);
      }

      return (await response.json()) as WorkspaceDocument;
    } catch (err: unknown) {
      clearTimeout(timer);
      if (err instanceof ApiClientError) throw err;
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new ApiClientError('Upload request timed out.', 408, 'TIMEOUT');
      }
      const message =
        err instanceof Error ? err.message : 'Network error during upload.';
      throw new ApiClientError(message, 0, 'NETWORK_ERROR');
    }
  },

  /**
   * Triggers retry of a failed document extraction/chunking job.
   */
  async retry(
    workspaceId: string,
    documentId: string
  ): Promise<{ success: boolean }> {
    return apiFetch<{ success: boolean }>(
      `workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(documentId)}/retry`,
      {
        method: 'POST',
      }
    );
  },

  /**
   * Deletes a document and its extracted chunks from the workspace.
   */
  async delete(
    workspaceId: string,
    documentId: string
  ): Promise<{ success: boolean; id: string }> {
    return apiFetch<{ success: boolean; id: string }>(
      `workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(documentId)}`,
      {
        method: 'DELETE',
      }
    );
  },
};
