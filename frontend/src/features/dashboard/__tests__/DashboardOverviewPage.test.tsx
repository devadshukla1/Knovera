import { screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DashboardOverviewPage } from '../pages/DashboardOverviewPage';
import { workspaceApi } from '@/features/workspaces/api/workspaceApi';
import { renderWithProviders } from '@/test/test-utils';
import { Workspace } from '@/features/workspaces/types/workspace';

vi.mock('@/features/workspaces/api/workspaceApi', () => ({
  workspaceApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockWorkspaces: Workspace[] = [
  {
    id: 'ws-1111-2222',
    name: 'Neural Network Architectures',
    description: 'Literature review on transformer backbones and self-attention.',
    document_count: 5,
    created_at: '2026-11-01T10:00:00Z',
    updated_at: '2026-11-05T08:30:00Z',
  },
  {
    id: 'ws-3333-4444',
    name: 'Cognitive Science Notes',
    description: 'Bayesian knowledge tracing and active recall models.',
    document_count: 2,
    created_at: '2026-11-02T12:00:00Z',
    updated_at: '2026-11-04T15:20:00Z',
  },
];

describe('DashboardOverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders welcome heading and product description', async () => {
    vi.mocked(workspaceApi.list).mockResolvedValue(mockWorkspaces);

    renderWithProviders(<DashboardOverviewPage />);

    expect(screen.getByText(/Your knowledge, connected/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /Organise your research, explore ideas, and turn your documents into actionable knowledge/i
      )
    ).toBeInTheDocument();
  });

  it('renders empty state when user has zero workspaces', async () => {
    vi.mocked(workspaceApi.list).mockResolvedValue([]);

    renderWithProviders(<DashboardOverviewPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/Your knowledge journey starts here/i)
      ).toBeInTheDocument();
    });

    expect(
      screen.getByRole('button', { name: /Create Your First Workspace/i })
    ).toBeInTheDocument();
  });

  it('renders workspace cards when workspaces exist', async () => {
    vi.mocked(workspaceApi.list).mockResolvedValue(mockWorkspaces);

    renderWithProviders(<DashboardOverviewPage />);

    await waitFor(() => {
      expect(
        screen.getByText('Neural Network Architectures')
      ).toBeInTheDocument();
    });

    expect(screen.getByText('Cognitive Science Notes')).toBeInTheDocument();
    expect(
      screen.getByText(/Literature review on transformer backbones/i)
    ).toBeInTheDocument();
  });

  it('renders error state with retry button when workspace API fails', async () => {
    vi.mocked(workspaceApi.list).mockRejectedValue(
      new Error('Failed to fetch workspaces from server')
    );

    renderWithProviders(<DashboardOverviewPage />);

    await waitFor(() => {
      expect(screen.getByText(/Unable to load workspaces/i)).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Failed to fetch workspaces from server/i)
    ).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Retry Request/i });
    expect(retryBtn).toBeInTheDocument();

    // Trigger retry
    vi.mocked(workspaceApi.list).mockResolvedValue(mockWorkspaces);
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(
        screen.getByText('Neural Network Architectures')
      ).toBeInTheDocument();
    });
  });
});
