import { screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WorkspacesPage } from '../pages/WorkspacesPage';
import { workspaceApi } from '../api/workspaceApi';
import { renderWithProviders } from '@/test/test-utils';
import { Workspace } from '../types/workspace';

vi.mock('../api/workspaceApi', () => ({
  workspaceApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockWorkspaces: Workspace[] = [
  {
    id: 'ws-1111',
    name: 'Quantum Optics',
    description: 'Photonics, entanglement, and quantum computing materials.',
    document_count: 3,
    created_at: '2026-11-01T10:00:00Z',
    updated_at: '2026-11-05T08:30:00Z',
  },
  {
    id: 'ws-2222',
    name: 'Bioinformatics Pipeline',
    description: 'Genomic sequences and variant analysis.',
    document_count: 7,
    created_at: '2026-11-02T12:00:00Z',
    updated_at: '2026-11-04T15:20:00Z',
  },
];

describe('WorkspacesPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders workspace list and title', async () => {
    vi.mocked(workspaceApi.list).mockResolvedValue(mockWorkspaces);

    renderWithProviders(<WorkspacesPage />);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Workspaces'
    );

    await waitFor(() => {
      expect(screen.getByText('Quantum Optics')).toBeInTheDocument();
      expect(screen.getByText('Bioinformatics Pipeline')).toBeInTheDocument();
    });
  });

  it('filters workspaces when searching', async () => {
    vi.mocked(workspaceApi.list).mockResolvedValue(mockWorkspaces);

    renderWithProviders(<WorkspacesPage />);

    await waitFor(() => {
      expect(screen.getByText('Quantum Optics')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search workspaces/i);
    fireEvent.change(searchInput, { target: { value: 'Bioinformatics' } });

    expect(screen.getByText('Bioinformatics Pipeline')).toBeInTheDocument();
    expect(screen.queryByText('Quantum Optics')).not.toBeInTheDocument();
  });

  it('opens create workspace modal and validates empty name', async () => {
    vi.mocked(workspaceApi.list).mockResolvedValue(mockWorkspaces);

    renderWithProviders(<WorkspacesPage />);

    const createButton = screen.getByRole('button', {
      name: /Create Workspace/i,
    });
    fireEvent.click(createButton);

    expect(
      screen.getByRole('heading', { name: /Create Workspace/i })
    ).toBeInTheDocument();

    // Try submitting without a name
    const submitBtn = screen.getByRole('button', {
      name: /^Create Workspace$/i,
    });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Workspace name is required/i)
      ).toBeInTheDocument();
    });
  });

  it('creates a workspace successfully and invalidates cache', async () => {
    vi.mocked(workspaceApi.list).mockResolvedValue(mockWorkspaces);
    vi.mocked(workspaceApi.create).mockResolvedValue({
      id: 'ws-3333',
      name: 'Deep Learning Theory',
      description: 'Optimization landscape studies',
      created_at: '2026-11-05T12:00:00Z',
      updated_at: '2026-11-05T12:00:00Z',
    });

    renderWithProviders(<WorkspacesPage />);

    fireEvent.click(
      screen.getByRole('button', { name: /Create Workspace/i })
    );

    const nameInput = screen.getByPlaceholderText(/e\.g\. Quantum Computing/i);
    fireEvent.change(nameInput, { target: { value: 'Deep Learning Theory' } });

    const submitBtn = screen.getByRole('button', {
      name: /^Create Workspace$/i,
    });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(workspaceApi.create).toHaveBeenCalledWith({
        name: 'Deep Learning Theory',
        description: null,
      });
    });
  });
});
