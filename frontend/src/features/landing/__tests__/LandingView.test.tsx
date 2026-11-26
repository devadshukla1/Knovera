import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { LandingView } from '../LandingView';
import * as apiService from '@/services/api';

vi.mock('@/services/api', async () => {
  const actual = await vi.importActual<typeof apiService>('@/services/api');
  return {
    ...actual,
    checkAggregateHealth: vi.fn(),
  };
});

describe('LandingView Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders brand identity, title, and tagline', async () => {
    vi.mocked(apiService.checkAggregateHealth).mockImplementation(
      () => new Promise(() => {}) // never resolves to stay in loading
    );

    render(<LandingView />);

    expect(screen.getByText('Knovera')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      /Turn Information into Intelligence/i
    );
    expect(
      screen.getByText(/Knovera is a focused research workspace for students and researchers/i)
    ).toBeInTheDocument();
  });

  it('renders loading state initially while probing connectivity', () => {
    vi.mocked(apiService.checkAggregateHealth).mockImplementation(
      () => new Promise(() => {})
    );

    render(<LandingView />);

    expect(screen.getByTestId('status-loading')).toBeInTheDocument();
    expect(screen.getByText(/Checking backend connectivity.../i)).toBeInTheDocument();
  });

  it('renders success state when backend is reachable and healthy', async () => {
    vi.mocked(apiService.checkAggregateHealth).mockResolvedValue({
      liveness: {
        status: 'ok',
        app: 'Knovera',
        version: '1.0.0',
        environment: 'development',
      },
      readiness: {
        status: 'ready',
        services: {
          database: { status: 'connected', latency_ms: 1.2 },
          vector_store: { status: 'connected', latency_ms: 2.3 },
        },
      },
      latencyMs: 15,
    });

    render(<LandingView />);

    await waitFor(() => {
      expect(screen.getByTestId('status-success')).toBeInTheDocument();
    });

    expect(screen.getByText(/Backend Reachable & Healthy/i)).toBeInTheDocument();
    expect(screen.getByText(/Knovera Core API v1.0.0/i)).toBeInTheDocument();
    expect(screen.getByText(/15 ms/i)).toBeInTheDocument();
    expect(screen.getByText('PostgreSQL 16')).toBeInTheDocument();
    expect(screen.getByText('ChromaDB')).toBeInTheDocument();
  });

  it('renders error state with troubleshooting guide when backend request fails', async () => {
    vi.mocked(apiService.checkAggregateHealth).mockRejectedValue(
      new apiService.ApiClientError(
        'Unable to connect to Knovera backend. Please ensure the backend server is running.',
        0,
        'NETWORK_ERROR'
      )
    );

    render(<LandingView />);

    await waitFor(() => {
      expect(screen.getByTestId('status-error')).toBeInTheDocument();
    });

    expect(screen.getByText(/Backend Unreachable/i)).toBeInTheDocument();
    expect(screen.getByText(/Troubleshooting Steps:/i)).toBeInTheDocument();
    expect(screen.getByText(/Retry Connection/i)).toBeInTheDocument();
  });

  it('handles manual retry button click', async () => {
    vi.mocked(apiService.checkAggregateHealth)
      .mockRejectedValueOnce(new Error('Connection failure'))
      .mockResolvedValueOnce({
        liveness: {
          status: 'ok',
          app: 'Knovera',
          version: '1.0.0',
          environment: 'development',
        },
        readiness: {
          status: 'ready',
          services: {
            database: { status: 'connected' },
            vector_store: { status: 'connected' },
          },
        },
        latencyMs: 8,
      });

    render(<LandingView />);

    await waitFor(() => {
      expect(screen.getByTestId('status-error')).toBeInTheDocument();
    });

    const retryBtn = screen.getByText(/Retry Connection/i);
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByTestId('status-success')).toBeInTheDocument();
    });

    expect(apiService.checkAggregateHealth).toHaveBeenCalledTimes(2);
  });
});
