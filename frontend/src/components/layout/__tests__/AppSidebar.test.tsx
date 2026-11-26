import { screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { AppSidebar } from '../AppSidebar';
import { renderWithProviders } from '@/test/test-utils';
import * as workspaceHooks from '@/features/workspaces/hooks/useWorkspaces';

vi.mock('@/features/workspaces/context/WorkspaceContext', () => ({
  useWorkspaceContext: () => ({
    activeWorkspaceId: 'ws-test-123',
    activeWorkspace: { id: 'ws-test-123', name: 'Test Workspace' },
    workspaces: [{ id: 'ws-test-123', name: 'Test Workspace' }],
    isLoading: false,
    setActiveWorkspaceId: vi.fn(),
  }),
}));

vi.mock('@/features/workspaces/hooks/useWorkspaces', () => ({
  useWorkspaces: vi.fn(),
  useWorkspace: vi.fn(),
  useCreateWorkspace: () => ({ mutateAsync: vi.fn(), isPending: false }),
  WORKSPACE_KEYS: {
    all: ['workspaces'],
    lists: () => ['workspaces', 'list'],
    details: () => ['workspaces', 'detail'],
    detail: (id: string) => ['workspaces', 'detail', id],
  },
}));

describe('AppSidebar Component (C1.4 Navigation)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(workspaceHooks.useWorkspaces).mockReturnValue({
      data: [
        {
          id: 'ws-active-1',
          name: 'Quantum Optics',
          description: null,
          created_at: '2026-11-01T00:00:00Z',
          updated_at: '2026-11-01T00:00:00Z',
        },
      ],
      isLoading: false,
    } as any);

    vi.mocked(workspaceHooks.useWorkspace).mockReturnValue({
      data: {
        id: 'ws-active-1',
        name: 'Quantum Optics',
        description: null,
        created_at: '2026-11-01T00:00:00Z',
        updated_at: '2026-11-01T00:00:00Z',
      },
      isLoading: false,
    } as any);
  });

  it('renders Knovera brand and primary navigation links', () => {
    renderWithProviders(<AppSidebar isOpen={true} />);

    expect(screen.getByText('Knovera')).toBeInTheDocument();
    expect(screen.getByText('Your research space')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('All Workspaces')).toBeInTheDocument();
    expect(screen.getByText('Document Library')).toBeInTheDocument();
    expect(screen.getByText('Research Chat')).toBeInTheDocument();
    expect(screen.getByText('Knowledge Graph')).toBeInTheDocument();
    expect(screen.getByText('Study Studio')).toBeInTheDocument();
    expect(screen.getByText('Learning Analytics')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders all feature navigation items as active links', () => {
    renderWithProviders(<AppSidebar isOpen={true} />);

    // Verify all module navigation links are present and active
    const docLink = screen.getByRole('link', { name: /Document Library/i });
    expect(docLink).toHaveAttribute('href', '/app/workspaces/ws-test-123/documents');

    const chatLink = screen.getByRole('link', { name: /Research Chat/i });
    expect(chatLink).toHaveAttribute('href', '/app/workspaces/ws-test-123/chat');

    const topicsLink = screen.getByRole('link', { name: /Knowledge Graph/i });
    expect(topicsLink).toHaveAttribute('href', '/app/workspaces/ws-test-123/knowledge-graph');

    const studyLink = screen.getByRole('link', { name: /Study Studio/i });
    expect(studyLink).toHaveAttribute('href', '/app/workspaces/ws-test-123/study-studio');

    const analyticsLink = screen.getByRole('link', { name: /Learning Analytics/i });
    expect(analyticsLink).toHaveAttribute('href', '/app/workspaces/ws-test-123/learning-analytics');

  });

  it('renders footer version and platform tagline', () => {
    renderWithProviders(<AppSidebar isOpen={true} />);

    expect(screen.getByText('Knovera v1.0.0')).toBeInTheDocument();
    expect(screen.getByText('Documents. Ideas. Understanding.')).toBeInTheDocument();
  });

  it('triggers onClose when close button is clicked on mobile', () => {
    const handleClose = vi.fn();
    renderWithProviders(<AppSidebar isOpen={true} onClose={handleClose} />);

    const closeBtn = screen.getByRole('button', { name: /Close navigation/i });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
