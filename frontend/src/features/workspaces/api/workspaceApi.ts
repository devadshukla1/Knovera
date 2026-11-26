/**
 * Knovera Workspace API Client
 *
 * Implements REST calls to the backend /api/v1/workspaces endpoints
 * according to the documented schema and architecture.
 */

import { apiFetch } from '@/services/api';
import {
  Workspace,
  CreateWorkspacePayload,
  UpdateWorkspacePayload,
} from '../types/workspace';

export const workspaceApi = {
  /**
   * Fetches all personal workspaces owned by the user.
   */
  async list(): Promise<Workspace[]> {
    const data = await apiFetch<Workspace[] | { workspaces: Workspace[] }>('workspaces');
    if (Array.isArray(data)) {
      return data;
    }
    if (data && Array.isArray(data.workspaces)) {
      return data.workspaces;
    }
    return [];
  },

  /**
   * Fetches a single workspace by ID.
   */
  async getById(workspaceId: string): Promise<Workspace> {
    return apiFetch<Workspace>(`workspaces/${encodeURIComponent(workspaceId)}`);
  },

  /**
   * Creates a new personal workspace.
   */
  async create(payload: CreateWorkspacePayload): Promise<Workspace> {
    return apiFetch<Workspace>('workspaces', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  },

  /**
   * Renames or updates a workspace's details.
   */
  async update(workspaceId: string, payload: UpdateWorkspacePayload): Promise<Workspace> {
    return apiFetch<Workspace>(`workspaces/${encodeURIComponent(workspaceId)}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  },

  /**
   * Deletes a workspace and all its associated artifacts.
   */
  async delete(workspaceId: string): Promise<{ success: boolean; id: string }> {
    await apiFetch<unknown>(
      `workspaces/${encodeURIComponent(workspaceId)}`,
      {
        method: 'DELETE',
      }
    );
    return { success: true, id: workspaceId };
  },
};
