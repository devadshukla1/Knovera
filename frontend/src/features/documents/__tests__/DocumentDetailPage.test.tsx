import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { DocumentDetailPage } from '../pages/DocumentDetailPage';
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
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
};

const mockDoc: WorkspaceDocument = {
  id: 'doc-deep-1',
  workspace_id: 'ws-alpha',
  original_filename: 'resnet.pdf',
  media_type: 'application/pdf',
  file_size_bytes: 4194304,
  page_count: 28,
  processing_status: 'ready',
  error_message: null,
  created_at: '2026-11-01T01:00:00Z',
  updated_at: '2026-11-01T01:10:00Z',
};

describe('DocumentDetailPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders document metadata, lifecycle stages, and properties', async () => {
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(documentApi.getById).mockResolvedValue(mockDoc);

    renderWithProviders(
      <Routes>
        <Route
          path="/app/workspaces/:workspaceId/documents/:documentId"
          element={<DocumentDetailPage />}
        />
      </Routes>,
      {
        initialEntries: ['/app/workspaces/ws-alpha/documents/doc-deep-1'],
      }
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
        'resnet.pdf'
      );
    });

    expect(screen.getByText('Source File Properties')).toBeInTheDocument();
    expect(screen.getByText('Ingestion Lifecycle Stages')).toBeInTheDocument();
    expect(screen.getByText(/28 pages/i)).toBeInTheDocument();
  });

  it('renders error state when document fails to load', async () => {
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);
    vi.mocked(documentApi.getById).mockRejectedValue(new Error('Document not found'));

    renderWithProviders(
      <Routes>
        <Route
          path="/app/workspaces/:workspaceId/documents/:documentId"
          element={<DocumentDetailPage />}
        />
      </Routes>,
      {
        initialEntries: ['/app/workspaces/ws-alpha/documents/non-existent-id'],
      }
    );

    await waitFor(() => {
      expect(screen.getByText('Document Not Found')).toBeInTheDocument();
    });
  });
});
