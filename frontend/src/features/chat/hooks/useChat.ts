import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { chatApi } from '../api/chatApi';
import { ChatMessage, Conversation, SendMessagePayload } from '../types/chat';

export const CHAT_KEYS = {
  all: ['chat'] as const,
  conversations: (workspaceId: string) =>
    ['workspaces', workspaceId, 'conversations'] as const,
  conversation: (workspaceId: string, conversationId: string) =>
    ['workspaces', workspaceId, 'conversations', conversationId] as const,
};

/**
 * Hook to retrieve conversation history for a workspace.
 */
export function useConversations(
  workspaceId: string,
  options?: { retry?: number | boolean }
) {
  return useQuery<Conversation[], Error>({
    queryKey: CHAT_KEYS.conversations(workspaceId),
    queryFn: async () => (await chatApi.listConversations(workspaceId)) ?? [],
    enabled: Boolean(workspaceId && workspaceId.trim().length > 0),
    staleTime: 1000 * 30,
    ...(options?.retry !== undefined ? { retry: options.retry } : {}),
  });
}

/**
 * Hook to retrieve a specific conversation thread and its messages.
 */
export function useConversation(
  workspaceId: string,
  conversationId?: string,
  options?: { retry?: number | boolean }
) {
  return useQuery<{ conversation: Conversation; messages: ChatMessage[] }, Error>({
    queryKey: CHAT_KEYS.conversation(workspaceId, conversationId || ''),
    queryFn: () => chatApi.getConversation(workspaceId, conversationId || ''),
    enabled: Boolean(
      workspaceId &&
        workspaceId.trim().length > 0 &&
        conversationId &&
        conversationId.trim().length > 0
    ),
    staleTime: 1000 * 30,
    ...(options?.retry !== undefined ? { retry: options.retry } : {}),
  });
}

/**
 * Hook to send a query to the chat engine.
 */
export function useSendMessage(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<ChatMessage & { conversation_id?: string }, Error, SendMessagePayload>({
    mutationFn: (payload: SendMessagePayload) =>
      chatApi.sendMessage(workspaceId, payload),
    onSuccess: (response, variables) => {
      const convId = response.conversation_id || variables.conversation_id;
      if (convId) {
        queryClient.invalidateQueries({
          queryKey: CHAT_KEYS.conversation(workspaceId, convId),
        });
      }
      queryClient.invalidateQueries({
        queryKey: CHAT_KEYS.conversations(workspaceId),
      });
    },
  });
}

/**
 * Hook to rename a conversation thread.
 */
export function useRenameConversation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<Conversation, Error, { conversationId: string; title: string }>({
    mutationFn: ({ conversationId, title }) =>
      chatApi.renameConversation(workspaceId, conversationId, title),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: CHAT_KEYS.conversation(workspaceId, variables.conversationId),
      });
      queryClient.invalidateQueries({
        queryKey: CHAT_KEYS.conversations(workspaceId),
      });
    },
  });
}

/**
 * Hook to delete a conversation thread.
 */
export function useDeleteConversation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { conversationId: string }>({
    mutationFn: ({ conversationId }) =>
      chatApi.deleteConversation(workspaceId, conversationId),
    onSuccess: (_, variables) => {
      queryClient.removeQueries({
        queryKey: CHAT_KEYS.conversation(workspaceId, variables.conversationId),
      });
      queryClient.invalidateQueries({
        queryKey: CHAT_KEYS.conversations(workspaceId),
      });
    },
  });
}
