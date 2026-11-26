import { describe, it, expect, vi, beforeEach } from 'vitest';
import { chatApi } from '../api/chatApi';
import * as apiModule from '@/services/api';
import { Conversation, ChatMessage } from '../types/chat';

vi.mock('@/services/api', async () => {
  const actual = await vi.importActual<typeof apiModule>('@/services/api');
  return {
    ...actual,
    apiFetch: vi.fn(),
  };
});

const mockConversation: Conversation = {
  id: 'conv-1',
  workspace_id: 'ws-1',
  title: 'Transformers Architecture Discussion',
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T01:00:00Z',
};

const mockMessage: ChatMessage = {
  id: 'msg-1',
  role: 'assistant',
  content: 'Transformers use multi-head self-attention mechanisms [1].',
  citations: [
    {
      id: 'cite-1',
      citation_number: 1,
      document_id: 'doc-1',
      document_title: 'Attention Is All You Need',
      page_number: 3,
      snippet: 'An attention function can be described as mapping a query and a set of key-value pairs...',
      confidence_score: 0.94,
    },
  ],
  created_at: '2026-11-01T01:01:00Z',
};

describe('chatApi Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('listConversations', () => {
    it('returns array directly when API responds with array', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue([mockConversation]);

      const result = await chatApi.listConversations('ws-1');
      expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-1/conversations');
      expect(result).toEqual([mockConversation]);
    });

    it('returns conversations when API responds with { conversations: [...] } envelope', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue({ conversations: [mockConversation] });

      const result = await chatApi.listConversations('ws-1');
      expect(result).toEqual([mockConversation]);
    });

    it('returns empty array when API responds with null or unknown shape', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue(null);

      const result = await chatApi.listConversations('ws-1');
      expect(result).toEqual([]);
    });
  });

  describe('getConversation', () => {
    it('fetches conversation metadata and messages', async () => {
      const mockPayload = {
        conversation: mockConversation,
        messages: [mockMessage],
      };
      vi.mocked(apiModule.apiFetch).mockResolvedValue(mockPayload);

      const result = await chatApi.getConversation('ws-1', 'conv-1');
      expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-1/conversations/conv-1');
      expect(result).toEqual({ ...mockPayload, messages: [{ ...mockMessage, status: undefined, failure_code: null }] });
    });
  });

  describe('sendMessage', () => {
    it('sends POST to chat endpoint with JSON body and returns assistant message', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue(mockMessage);

      const payload = {
        message: 'How does self-attention work?',
        conversation_id: 'conv-1',
        selected_document_ids: ['doc-1'],
      };

      const result = await chatApi.sendMessage('ws-1', payload);
      expect(apiModule.apiFetch).toHaveBeenCalledWith(
        'workspaces/ws-1/chat',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        }
      );
      expect(result).toEqual(mockMessage);
    });
  });
});
