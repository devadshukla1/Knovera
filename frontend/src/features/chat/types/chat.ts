/**
 * Chat and Citation types reflecting the Knovera schema in docs/schema.md
 */

export interface Citation {
  id: string;
  citation_number: number;
  document_id: string;
  document_title: string;
  page_number: number | null;
  snippet: string;
  confidence_score?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  status?: 'pending' | 'complete' | 'failed';
  failure_code?: string | null;
  citations?: Citation[];
  evidence_status?: 'full' | 'partial' | 'insufficient';
  created_at: string;
}

export interface Conversation {
  id: string;
  workspace_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface SendMessagePayload {
  message: string;
  conversation_id?: string;
  selected_document_ids?: string[];
}
