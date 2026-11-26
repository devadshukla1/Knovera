/**
 * Document Data Types reflecting the Knovera schema in docs/schema.md
 */

export type DocumentStatus =
  | 'queued'
  | 'extracting'
  | 'chunking'
  | 'indexing'
  | 'ready'
  | 'failed'
  | 'deleting';

export interface WorkspaceDocument {
  id: string;
  workspace_id: string;
  original_filename: string;
  media_type: string;
  file_size_bytes: number;
  processing_status: DocumentStatus;
  page_count: number | null;
  chunk_count?: number | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentUploadResponse {
  document: WorkspaceDocument;
  upload_status: string;
}
