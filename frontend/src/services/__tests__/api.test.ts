import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getApiBaseUrl,
  resolveEndpointUrl,
  checkLiveness,
  checkReadiness,
  checkAggregateHealth,
  ApiClientError,
  DEFAULT_API_BASE_URL,
} from '../api';

describe('API Service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('URL Resolution', () => {
    it('returns default base URL if env is unset', () => {
      const url = getApiBaseUrl();
      expect(url).toBe(DEFAULT_API_BASE_URL);
      expect(url.length).toBeGreaterThan(0);
    });

    it('normalizes endpoint URLs with slashes', () => {
      expect(resolveEndpointUrl('health', 'http://localhost:8000/api/v1')).toBe(
        'http://localhost:8000/api/v1/health'
      );
      expect(resolveEndpointUrl('/health/', 'http://localhost:8000/api/v1/')).toBe(
        'http://localhost:8000/api/v1/health/'
      );
      expect(resolveEndpointUrl('health/ready', 'http://localhost:8000')).toBe(
        'http://localhost:8000/health/ready'
      );
    });
  });

  describe('checkLiveness', () => {
    it('returns liveness data on HTTP 200', async () => {
      const mockLiveness = {
        status: 'ok',
        app: 'Knovera',
        version: '1.0.0',
        environment: 'development',
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockLiveness,
      });

      const res = await checkLiveness();
      expect(res).toEqual(mockLiveness);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/health'),
        expect.objectContaining({ method: 'GET' })
      );
    });

    it('throws ApiClientError on HTTP error status', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'Fatal server error' }),
      });

      await expect(checkLiveness()).rejects.toThrow(ApiClientError);
      await expect(checkLiveness()).rejects.toThrow('Fatal server error');
    });

    it('handles network disconnection gracefully', async () => {
      global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

      await expect(checkLiveness()).rejects.toThrow(ApiClientError);
      await expect(checkLiveness()).rejects.toThrow(/Unable to connect to Knovera backend/);
    });
  });

  describe('checkReadiness', () => {
    it('returns readiness data on HTTP 200 ready state', async () => {
      const mockReadiness = {
        status: 'ready',
        services: {
          database: { status: 'connected', latency_ms: 1.2 },
          vector_store: { status: 'connected', latency_ms: 2.1 },
        },
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockReadiness,
      });

      const res = await checkReadiness();
      expect(res.status).toBe('ready');
      expect(res.services.database?.status).toBe('connected');
      expect(res.services.vector_store?.status).toBe('connected');
    });

    it('parses degraded readiness response on HTTP 503', async () => {
      const mockDegraded = {
        status: 'not_ready',
        services: {
          database: { status: 'connected', latency_ms: 1.5 },
          vector_store: { status: 'disconnected', error: 'Vector store unreachable' },
        },
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockDegraded,
      });

      const res = await checkReadiness();
      expect(res.status).toBe('not_ready');
      expect(res.services.vector_store?.status).toBe('disconnected');
    });
  });

  describe('checkAggregateHealth', () => {
    it('returns aggregated liveness, readiness, and latency', async () => {
      const mockLiveness = {
        status: 'ok',
        app: 'Knovera',
        version: '1.0.0',
        environment: 'development',
      };
      const mockReadiness = {
        status: 'ready',
        services: {
          database: { status: 'connected' },
          vector_store: { status: 'connected' },
        },
      };

      global.fetch = vi.fn().mockImplementation((url: string) => {
        if (url.includes('health/ready')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => mockReadiness,
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockLiveness,
        });
      });

      const result = await checkAggregateHealth();
      expect(result.liveness.status).toBe('ok');
      expect(result.readiness.status).toBe('ready');
      expect(typeof result.latencyMs).toBe('number');
    });
  });
});
