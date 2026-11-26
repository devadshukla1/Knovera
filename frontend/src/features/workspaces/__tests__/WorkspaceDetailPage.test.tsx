import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { WorkspaceDetailPage } from '../pages/WorkspaceDetailPage';
import { workspaceApi } from '../api/workspaceApi';
import { renderWithProviders } from '@/test/test-utils';
import { Workspace } from '../types/workspace';

vi.mock('../api/workspaceApi', () => ({
  workspaceApi: {
    list: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockWorkspace: Workspace = {
  id: 'ws-test-456',
  name: 'Robotics Kinematics',
  description: 'Forward and inverse kinematics derivations.',
  document_count: 4,
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-05T08:30:00Z',
};

describe('WorkspaceDetailPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders workspace details and planned capability cards', async () => {
    vi.mocked(workspaceApi.getById).mockResolvedValue(mockWorkspace);

    renderWithProviders(
      <Routes>
        <Route
          path="/app/workspaces/:workspaceId"
          element={<WorkspaceDetailPage />}
        />
      </Routes>,
      {
        initialEntries: ['/app/workspaces/ws-test-456'],
      }
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
        'Robotics Kinematics'
      );
    });

    expect(
      screen.getByText(/Forward and inverse kinematics derivations/i)
    ).toBeInTheDocument();

    // Check breadcrumb
    expect(screen.getByText('Workspaces')).toBeInTheDocument();

    // Check unlocked module capability cards
    expect(screen.getByText('Documents & Library')).toBeInTheDocument();
    expect(screen.getByText('Open Document Library')).toBeInTheDocument();
    expect(screen.getByText('Research Chat')).toBeInTheDocument();
    expect(screen.getByText('Open Research Chat')).toBeInTheDocument();
    expect(screen.getByText('Knowledge Explorer')).toBeInTheDocument();
    expect(screen.getByText('Study Studio')).toBeInTheDocument();
    expect(screen.getByText('Open Study Studio')).toBeInTheDocument();
    expect(screen.getByText('Learning Analytics')).toBeInTheDocument();
    expect(screen.getByText('Open Learning Analytics')).toBeInTheDocument();
    expect(screen.getByText('Research Intelligence')).toBeInTheDocument();
    expect(screen.getByText('Open Research Intelligence')).toBeInTheDocument();
  });

  it('renders not-found error state when workspace does not exist', async () => {
    vi.mocked(workspaceApi.getById).mockRejectedValue(
      new Error('Workspace not found')
    );

    renderWithProviders(
      <Routes>
        <Route
          path="/app/workspaces/:workspaceId"
          element={<WorkspaceDetailPage />}
        />
      </Routes>,
      {
        initialEntries: ['/app/workspaces/invalid-id'],
      }
    );

    await waitFor(() => {
      expect(screen.getByText('Workspace Not Found')).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Back to Workspaces/i)
    ).toBeInTheDocument();
  });
});
