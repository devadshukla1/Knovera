/**
 * Knovera Research Chat API Client
 *
 * Implements REST calls to the backend chat endpoints under
 * /api/v1/workspaces/{workspaceId}/chat and /conversations.
 */

import { apiFetch } from '@/services/api';
import { ChatMessage, Conversation, SendMessagePayload } from '../types/chat';

export const chatApi = {
  /**
   * Fetches conversation threads for a specific workspace.
   */
  async listConversations(workspaceId: string): Promise<Conversation[]> {
    const data = await apiFetch<any>(
      `workspaces/${encodeURIComponent(workspaceId)}/conversations`
    );

    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.items)) return data.items;
    if (data && Array.isArray(data.conversations)) return data.conversations;
    return [];
  },

  /**
   * Fetches a conversation thread and its messages with normalized citations.
   */
  async getConversation(
    workspaceId: string,
    conversationId: string
  ): Promise<{ conversation: Conversation; messages: ChatMessage[] }> {
    const raw = await apiFetch<any>(
      `workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(conversationId)}`
    );
    const conversation: Conversation = raw.conversation || raw;
    const rawMessages: any[] = Array.isArray(raw.messages) ? raw.messages : [];
    const messages: ChatMessage[] = rawMessages.map((m) => {
      const msg: ChatMessage = {
        id: String(m.id),
        role: m.role,
        content: m.content || '',
        status: m.status,
        failure_code: m.failure_code ?? null,
        created_at: m.created_at || new Date().toISOString(),
      };
      if (m.evidence_status) {
        msg.evidence_status = m.evidence_status;
      }
      if (Array.isArray(m.citations)) {
        msg.citations = m.citations.map((c: any) => ({
          id: String(c.citation_id || c.id || Math.random().toString(36)),
          citation_number: c.display_number || c.citation_number || 1,
          document_id: String(c.document_id || ''),
          document_title: c.document_name || c.document_title || 'Document',
          page_number: c.page_start ?? c.page_number ?? null,
          snippet: c.quote_text || c.snippet || c.location_label || '',
          ...(c.relevance_score !== undefined || c.confidence_score !== undefined
            ? { confidence_score: c.relevance_score ?? c.confidence_score }
            : {}),
        }));
      }
      return msg;
    });
    return { conversation, messages };
  },

  /**
   * Sends a user query to the RAG chat engine.
   */
  async sendMessage(
    workspaceId: string,
    payload: SendMessagePayload
  ): Promise<ChatMessage & { conversation_id?: string }> {
    return apiFetch<ChatMessage & { conversation_id?: string }>(
      `workspaces/${encodeURIComponent(workspaceId)}/chat`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      }
    );
  },

  /**
   * Renames an existing conversation.
   */
  async renameConversation(
    workspaceId: string,
    conversationId: string,
    title: string
  ): Promise<Conversation> {
    return apiFetch<Conversation>(
      `workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(conversationId)}`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title }),
      }
    );
  },

  /**
   * Deletes an entire conversation thread and its message history.
   */
  async deleteConversation(
    workspaceId: string,
    conversationId: string
  ): Promise<void> {
    await apiFetch(
      `workspaces/${encodeURIComponent(workspaceId)}/conversations/${encodeURIComponent(conversationId)}`,
      {
        method: 'DELETE',
      }
    );
  },
};
