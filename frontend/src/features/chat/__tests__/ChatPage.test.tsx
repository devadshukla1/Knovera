import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { ChatPage } from '../pages/ChatPage';
import { chatApi } from '../api/chatApi';
import { documentApi } from '@/features/documents/api/documentApi';
import { workspaceApi } from '@/features/workspaces/api/workspaceApi';
import { renderWithProviders } from '@/test/test-utils';
import { Workspace } from '@/features/workspaces/types/workspace';
import { WorkspaceDocument } from '@/features/documents/types/document';
import { ChatMessage } from '../types/chat';

vi.mock('../api/chatApi', () => ({
  chatApi: {
    listConversations: vi.fn(),
    getConversation: vi.fn(),
    sendMessage: vi.fn(),
  },
}));

vi.mock('@/features/documents/api/documentApi', () => ({
  documentApi: {
    list: vi.fn(),
    getById: vi.fn(),
    upload: vi.fn(),
    retry: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('@/features/workspaces/api/workspaceApi', () => ({
  workspaceApi: {
    list: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockWorkspace: Workspace = {
  id: 'ws-chat-1',
  name: 'Quantum Optics',
  description: 'Quantum optics research',
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
};

const mockReadyDoc: WorkspaceDocument = {
  id: 'doc-optics-1',
  workspace_id: 'ws-chat-1',
  original_filename: 'Photon Entanglement.pdf',
  media_type: 'application/pdf',
  file_size_bytes: 1048576,
  page_count: 8,
  processing_status: 'ready',
  error_message: null,
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
};

const mockAssistantResponse: ChatMessage = {
  id: 'msg-assist-1',
  role: 'assistant',
  content: 'Spontaneous parametric down-conversion generates entangled photons [1].',
  citations: [
    {
      id: 'cite-optics-1',
      citation_number: 1,
      document_id: 'doc-optics-1',
      document_title: 'Photon Entanglement.pdf',
      page_number: 2,
      snippet: 'Type-II SPDC yields orthogonally polarized pairs with high fidelity.',
      confidence_score: 0.96,
    },
  ],
  created_at: '2026-11-01T02:00:00Z',
};

describe('ChatPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders research chat header with breadcrumbs and workspace name', async () => {
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(documentApi.list).mockResolvedValue([mockReadyDoc]);

    renderWithProviders(
      <Routes>
        <Route path="/app/workspaces/:workspaceId/chat" element={<ChatPage />} />
      </Routes>,
      {
        initialEntries: ['/app/workspaces/ws-chat-1/chat'],
      }
    );

    await waitFor(() => {
      expect(screen.getByText('Quantum Optics')).toBeInTheDocument();
    });

    expect(screen.getByText('Research Chat')).toBeInTheDocument();
    expect(screen.getByText('Ask Questions Grounded in Your Sources')).toBeInTheDocument();
  });

  it('allows user to send message and inspect citations', async () => {
    const user = userEvent.setup();
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(documentApi.list).mockResolvedValue([mockReadyDoc]);
    vi.mocked(chatApi.sendMessage).mockResolvedValue(mockAssistantResponse);

    renderWithProviders(
      <Routes>
        <Route path="/app/workspaces/:workspaceId/chat" element={<ChatPage />} />
      </Routes>,
      {
        initialEntries: ['/app/workspaces/ws-chat-1/chat'],
      }
    );

    await waitFor(() => {
      expect(screen.getByText('Quantum Optics')).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Ask a question about your documents/i);
    await user.type(textarea, 'How is entanglement created?');

    const sendButton = screen.getByRole('button', { name: /Send Message/i });
    await user.click(sendButton);

    // Verify user message appears in list
    expect(screen.getByText('How is entanglement created?')).toBeInTheDocument();

    // Verify assistant response appears with citation
    await waitFor(() => {
      expect(
        screen.getByText(/Spontaneous parametric down-conversion generates entangled photons/i)
      ).toBeInTheDocument();
    });

    // Find and click citation chip [1]
    const citationChip = screen.getByRole('button', { name: '[1]' });
    await user.click(citationChip);

    // Verify Citation Inspector panel opens
    expect(screen.getByText('Source Grounding')).toBeInTheDocument();
    expect(
      screen.getByText(/Type-II SPDC yields orthogonally polarized pairs with high fidelity/i)
    ).toBeInTheDocument();
  });

  it('displays architectural notice when backend RAG service returns 404/not implemented', async () => {
    const user = userEvent.setup();
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(documentApi.list).mockResolvedValue([mockReadyDoc]);
    vi.mocked(chatApi.sendMessage).mockRejectedValue(
      new Error('RAG backend service scheduled for Phase 3')
    );

    renderWithProviders(
      <Routes>
        <Route path="/app/workspaces/:workspaceId/chat" element={<ChatPage />} />
      </Routes>,
      {
        initialEntries: ['/app/workspaces/ws-chat-1/chat'],
      }
    );

    await waitFor(() => {
      expect(screen.getByText('Quantum Optics')).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Ask a question about your documents/i);
    await user.type(textarea, 'What is the coherence time?');

    const sendButton = screen.getByRole('button', { name: /Send Message/i });
    await user.click(sendButton);

    await waitFor(() => {
      expect(
        screen.getByText(/RAG backend service scheduled for Phase 3/i)
      ).toBeInTheDocument();
    });
  });
});
