import { describe, it, expect, vi, beforeEach } from 'vitest';
import { documentApi } from '../api/documentApi';
import * as apiModule from '@/services/api';
import { WorkspaceDocument } from '../types/document';

vi.mock('@/services/api', async () => {
  const actual = await vi.importActual<typeof apiModule>('@/services/api');
  return {
    ...actual,
    apiFetch: vi.fn(),
    getApiBaseUrl: vi.fn(() => 'http://localhost:8000/api/v1'),
  };
});

const mockDocument: WorkspaceDocument = {
  id: 'doc-123',
  workspace_id: 'ws-1',
  original_filename: 'Attention Is All You Need.pdf',
  media_type: 'application/pdf',
  file_size_bytes: 2048000,
  page_count: 15,
  processing_status: 'ready',
  error_message: null,
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:05:00Z',
};

describe('documentApi Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('list', () => {
    it('returns document array directly when backend returns an array', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue([mockDocument]);

      const result = await documentApi.list('ws-1');
      expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-1/documents');
      expect(result).toEqual([mockDocument]);
    });

    it('returns documents when backend returns { documents: [...] } envelope', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue({ documents: [mockDocument] });

      const result = await documentApi.list('ws-1');
      expect(result).toEqual([mockDocument]);
    });

    it('returns empty array when backend returns unexpected structure', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue(null);

      const result = await documentApi.list('ws-1');
      expect(result).toEqual([]);
    });
  });

  describe('getById', () => {
    it('fetches single document by workspaceId and documentId', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue(mockDocument);

      const result = await documentApi.getById('ws-1', 'doc-123');
      expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-1/documents/doc-123');
      expect(result).toEqual(mockDocument);
    });
  });

  describe('retry', () => {
    it('sends POST request to retry endpoint', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue({ success: true });

      const result = await documentApi.retry('ws-1', 'doc-123');
      expect(apiModule.apiFetch).toHaveBeenCalledWith(
        'workspaces/ws-1/documents/doc-123/retry',
        { method: 'POST' }
      );
      expect(result).toEqual({ success: true });
    });
  });

  describe('delete', () => {
    it('sends DELETE request to document endpoint', async () => {
      vi.mocked(apiModule.apiFetch).mockResolvedValue({ success: true, id: 'doc-123' });

      const result = await documentApi.delete('ws-1', 'doc-123');
      expect(apiModule.apiFetch).toHaveBeenCalledWith(
        'workspaces/ws-1/documents/doc-123',
        { method: 'DELETE' }
      );
      expect(result).toEqual({ success: true, id: 'doc-123' });
    });
  });

  describe('upload', () => {
    it('uploads file via multipart POST and returns parsed document', async () => {
      const mockFile = new File(['content'], 'paper.pdf', { type: 'application/pdf' });
      const globalFetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockDocument,
      });
      vi.stubGlobal('fetch', globalFetchMock);

      const result = await documentApi.upload('ws-1', mockFile);
      expect(globalFetchMock).toHaveBeenCalled();
      const callArgs = globalFetchMock.mock.calls[0];
      expect(callArgs[0]).toBe('http://localhost:8000/api/v1/workspaces/ws-1/documents');
      expect(callArgs[1].method).toBe('POST');
      expect(result).toEqual(mockDocument);

      vi.unstubAllGlobals();
    });

    it('throws ApiClientError when server returns non-ok response', async () => {
      const mockFile = new File(['content'], 'paper.pdf', { type: 'application/pdf' });
      const globalFetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'File too large or invalid format' }),
      });
      vi.stubGlobal('fetch', globalFetchMock);

      await expect(documentApi.upload('ws-1', mockFile)).rejects.toThrow(
        'File too large or invalid format'
      );

      vi.unstubAllGlobals();
    });
  });
});
