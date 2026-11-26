import { describe, it, expect, vi, beforeEach } from 'vitest';
import { workspaceApi } from '../api/workspaceApi';
import * as apiModule from '@/services/api';

vi.mock('@/services/api', async () => {
  const actual = await vi.importActual<typeof apiModule>('@/services/api');
  return {
    ...actual,
    apiFetch: vi.fn(),
  };
});

describe('workspaceApi Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls list endpoint and returns array', async () => {
    const mockData = [
      {
        id: 'ws-1',
        name: 'Workspace 1',
        description: null,
        created_at: '2026-11-05T00:00:00Z',
        updated_at: '2026-11-05T00:00:00Z',
      },
    ];
    vi.mocked(apiModule.apiFetch).mockResolvedValue(mockData);

    const result = await workspaceApi.list();
    expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces');
    expect(result).toEqual(mockData);
  });

  it('calls getById endpoint with encoded ID', async () => {
    const mockData = {
      id: 'ws-1',
      name: 'Workspace 1',
      description: 'Test',
      created_at: '2026-11-05T00:00:00Z',
      updated_at: '2026-11-05T00:00:00Z',
    };
    vi.mocked(apiModule.apiFetch).mockResolvedValue(mockData);

    const result = await workspaceApi.getById('ws-1');
    expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-1');
    expect(result).toEqual(mockData);
  });

  it('calls create endpoint with POST and JSON payload', async () => {
    const payload = { name: 'New WS', description: 'Desc' };
    const mockCreated = {
      id: 'ws-new',
      name: 'New WS',
      description: 'Desc',
      created_at: '2026-11-05T00:00:00Z',
      updated_at: '2026-11-05T00:00:00Z',
    };
    vi.mocked(apiModule.apiFetch).mockResolvedValue(mockCreated);

    const result = await workspaceApi.create(payload);
    expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    expect(result).toEqual(mockCreated);
  });

  it('calls update endpoint with PATCH and JSON payload', async () => {
    const payload = { name: 'Renamed WS' };
    const mockUpdated = {
      id: 'ws-1',
      name: 'Renamed WS',
      description: 'Desc',
      created_at: '2026-11-05T00:00:00Z',
      updated_at: '2026-11-05T01:00:00Z',
    };
    vi.mocked(apiModule.apiFetch).mockResolvedValue(mockUpdated);

    const result = await workspaceApi.update('ws-1', payload);
    expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-1', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    expect(result).toEqual(mockUpdated);
  });

  it('calls delete endpoint with DELETE', async () => {
    vi.mocked(apiModule.apiFetch).mockResolvedValue({ success: true, id: 'ws-1' });

    const result = await workspaceApi.delete('ws-1');
    expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-1', {
      method: 'DELETE',
    });
    expect(result).toEqual({ success: true, id: 'ws-1' });
  });
});
