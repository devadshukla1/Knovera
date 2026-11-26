/**
 * Workspace data types reflecting the Knovera database schema
 * defined in docs/schema.md and trd.md.
 */

export interface Workspace {
  id: string;
  name: string;
  description: string | null;
  document_count?: number;
  created_at: string;
  updated_at: string;
}

export interface CreateWorkspacePayload {
  name: string;
  description?: string | null;
}

export interface UpdateWorkspacePayload {
  name?: string;
  description?: string | null;
}

export interface WorkspaceListResponse {
  workspaces: Workspace[];
  total: number;
}
