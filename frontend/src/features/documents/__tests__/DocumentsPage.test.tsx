import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { DocumentsPage } from '../pages/DocumentsPage';
import { documentApi } from '../api/documentApi';
import { workspaceApi } from '@/features/workspaces/api/workspaceApi';
import { renderWithProviders } from '@/test/test-utils';
import { WorkspaceDocument } from '../types/document';
import { Workspace } from '@/features/workspaces/types/workspace';

vi.mock('../api/documentApi', () => ({
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
  id: 'ws-alpha',
  name: 'Machine Learning Lab',
  description: 'ML research documents',
  document_count: 2,
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
};

const mockDocs: WorkspaceDocument[] = [
  {
    id: 'doc-1',
    workspace_id: 'ws-alpha',
    original_filename: 'transformer.pdf',
    media_type: 'application/pdf',
    file_size_bytes: 1048576,
    page_count: 12,
    processing_status: 'ready',
    error_message: null,
    created_at: '2026-11-01T01:00:00Z',
    updated_at: '2026-11-01T01:05:00Z',
  },
  {
    id: 'doc-2',
    workspace_id: 'ws-alpha',
    original_filename: 'dataset_notes.docx',
    media_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    file_size_bytes: 512000,
    page_count: 4,
    processing_status: 'failed',
    error_message: 'Corrupted binary stream',
    created_at: '2026-11-02T01:00:00Z',
    updated_at: '2026-11-02T01:02:00Z',
  },
];

describe('DocumentsPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders document list with workspace title and status badges', async () => {
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(documentApi.list).mockResolvedValue(mockDocs);

    renderWithProviders(
      <Routes>
        <Route
          path="/app/workspaces/:workspaceId/documents"
          element={<DocumentsPage />}
        />
      </Routes>,
      {
        initialEntries: ['/app/workspaces/ws-alpha/documents'],
      }
    );

    await waitFor(() => {
      expect(screen.getAllByText('transformer.pdf').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getAllByText('dataset_notes.docx').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Machine Learning Lab')).toBeInTheDocument();
  });

  it('filters documents when user types into search input', async () => {
    const user = userEvent.setup();
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(documentApi.list).mockResolvedValue(mockDocs);

    renderWithProviders(
      <Routes>
        <Route
          path="/app/workspaces/:workspaceId/documents"
          element={<DocumentsPage />}
        />
      </Routes>,
      {
        initialEntries: ['/app/workspaces/ws-alpha/documents'],
      }
    );

    await waitFor(() => {
      expect(screen.getAllByText('transformer.pdf').length).toBeGreaterThanOrEqual(1);
    });

    const searchInput = screen.getByPlaceholderText(/Search documents by filename/i);
    await user.type(searchInput, 'dataset');

    expect(screen.queryByText('transformer.pdf')).not.toBeInTheDocument();
    expect(screen.getAllByText('dataset_notes.docx').length).toBeGreaterThanOrEqual(1);
  });

  it('opens upload modal when clicking Upload Document button', async () => {
    const user = userEvent.setup();
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(documentApi.list).mockResolvedValue(mockDocs);

    renderWithProviders(
      <Routes>
        <Route
          path="/app/workspaces/:workspaceId/documents"
          element={<DocumentsPage />}
        />
      </Routes>,
      {
        initialEntries: ['/app/workspaces/ws-alpha/documents'],
      }
    );

    await waitFor(() => {
      expect(screen.getAllByText('transformer.pdf').length).toBeGreaterThanOrEqual(1);
    });

    const uploadButtons = screen.getAllByRole('button', { name: /Add Documents/i });
    await user.click(uploadButtons[0]);

    expect(screen.getByText('Add Documents to Workspace')).toBeInTheDocument();
  });

  it('renders empty state when workspace has no documents', async () => {
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(documentApi.list).mockResolvedValue([]);

    renderWithProviders(
      <Routes>
        <Route
          path="/app/workspaces/:workspaceId/documents"
          element={<DocumentsPage />}
        />
      </Routes>,
      {
        initialEntries: ['/app/workspaces/ws-alpha/documents'],
      }
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Your workspace is ready for its first document/i)
      ).toBeInTheDocument();
    });
  });
});
