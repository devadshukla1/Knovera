/**
 * Knovera Topic Discovery & Explorer TypeScript Definitions (Phase 6 C6.7 & C6.8).
 */

export interface TopicKeyword {
  term: string;
  score: number;
}

export type TopicLabelStatus = 'suggested' | 'reviewed' | 'approved' | 'needs_review';
export type TopicLabelSource = 'keyword_based' | 'llm_assisted' | 'human_reviewed';

export interface TopicSummaryItem {
  id: string;
  workspace_id: string;
  clustering_run_id: string;
  cluster_key: string;
  label: string;
  description?: string | null;
  label_source: TopicLabelSource | string;
  label_status: TopicLabelStatus | string;
  keywords: TopicKeyword[];
  chunk_count: number;
  document_count: number;
  representative_chunk_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface TopicRunSummary {
  id: string;
  workspace_id: string;
  snapshot_id: string;
  status: string;
  k: number;
  model_version: string;
  is_active: boolean;
  created_at: string;
  completed_at?: string | null;
  topic_count?: number;
  total_assignments?: number;
}

export interface TopicRunDetail {
  id: string;
  workspace_id: string;
  snapshot_id: string;
  status: string;
  algorithm: string;
  model_version: string;
  embedding_model_id: string;
  embedding_dimension: number;
  k: number;
  configuration: Record<string, unknown>;
  evaluation_metrics: Record<string, unknown>;
  selection_metadata: Record<string, unknown>;
  corpus_snapshot_hash: string;
  created_by_user_id?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  is_active: boolean;
  topic_count: number;
  total_assignments: number;
}

export interface TopicDetail {
  id: string;
  workspace_id: string;
  clustering_run_id: string;
  cluster_key: string;
  label: string;
  description?: string | null;
  label_source: TopicLabelSource | string;
  label_status: TopicLabelStatus | string;
  keywords: TopicKeyword[];
  chunk_count: number;
  document_count: number;
  representative_chunk_ids: string[];
  cluster_statistics: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  run_summary?: TopicRunSummary | null;
}

export interface TopicChunkItem {
  assignment_id: string;
  chunk_id: string;
  document_id: string;
  document_title: string;
  chunk_index: number;
  distance_to_centroid?: number | null;
  is_representative: boolean;
  page_start?: number | null;
  page_end?: number | null;
  slide_number?: number | null;
  section_title?: string | null;
  content_preview: string;
  source_type?: string | null;
}

export interface PaginatedTopicsResponse {
  workspace_id: string;
  run?: TopicRunSummary | null;
  items: TopicSummaryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PaginatedTopicRunsResponse {
  items: TopicRunSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PaginatedTopicChunksResponse {
  topic_id: string;
  topic_label: string;
  items: TopicChunkItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export type TopicSortOption =
  | 'chunk_count-desc'
  | 'chunk_count-asc'
  | 'document_count-desc'
  | 'label-asc'
  | 'cluster_key-asc';
