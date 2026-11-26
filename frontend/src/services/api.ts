/**
 * Knovera Reusable API Client
 *
 * Implements typed HTTP requests with timeout controllers, normalized errors,
 * and automated health / readiness connectivity probes.
 */

import {
  LivenessResponse,
  ReadinessResponse,
  ApiErrorResponse,
} from '@/types/health';

export const DEFAULT_API_BASE_URL = 'http://localhost:8000/api/v1';
export const DEFAULT_TIMEOUT_MS = 30000;

export class ApiClientError extends Error {
  status?: number;
  code?: string;
  details?: unknown;

  constructor(message: string, status?: number, code?: string, details?: unknown) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  toResponse(): ApiErrorResponse {
    return {
      message: this.message,
      status: this.status,
      code: this.code,
      details: this.details,
      timestamp: new Date().toISOString(),
    };
  }
}

/**
 * Resolves the active backend API base URL from Vite environment variables.
 * Automatically aligns hostname (localhost vs 127.0.0.1) with the current browser location
 * to eliminate cross-origin preflight overhead and Windows IPv6 resolver divergences.
 */
export function getApiBaseUrl(): string {
  const envUrl = import.meta.env?.VITE_API_BASE_URL;
  let base =
    typeof envUrl === 'string' && envUrl.trim().length > 0
      ? envUrl.trim().replace(/\/+$/, '')
      : DEFAULT_API_BASE_URL;

  if (typeof window !== 'undefined' && window.location) {
    const curHost = window.location.hostname;
    if (curHost === '127.0.0.1' && base.includes('//localhost')) {
      base = base.replace('//localhost', '//127.0.0.1');
    } else if (curHost === 'localhost' && base.includes('//127.0.0.1')) {
      base = base.replace('//127.0.0.1', '//localhost');
    }
  }

  return base;
}

/**
 * Builds normalized URL for health endpoints.
 * Handles both root base URLs (http://localhost:8000) and versioned base URLs (http://localhost:8000/api/v1).
 */
export function resolveEndpointUrl(subpath: string, baseUrl: string = getApiBaseUrl()): string {
  const cleanSubpath = subpath.replace(/^\/+/, '');
  const cleanBase = baseUrl.replace(/\/+$/, '');
  return `${cleanBase}/${cleanSubpath}`;
}

/**
 * Generic Fetch wrapper with AbortController timeout support.
 */
export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);

  // If a parent signal was provided, link it to our controller
  if (options.signal) {
    options.signal.addEventListener('abort', () => controller.abort());
  }

  const url = endpoint.startsWith('http') ? endpoint : resolveEndpointUrl(endpoint);

  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    throw new ApiClientError(
      `Invalid API URL configuration: "${url}". Please verify VITE_API_BASE_URL.`,
      0,
      'INVALID_URL'
    );
  }

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Accept': 'application/json',
        ...options.headers,
      },
    });

    clearTimeout(id);

    if (response.status === 204) {
      return { success: true } as unknown as T;
    }

    let data: unknown;
    const contentType = response.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');

    if (typeof response.text === 'function') {
      const text = await response.text();
      if (!text || text.trim() === '') {
        data = { success: true };
      } else if (isJson) {
        try {
          data = JSON.parse(text);
        } catch {
          data = text;
        }
      } else {
        data = text;
      }
    } else if (typeof response.json === 'function' && isJson) {
      try {
        data = await response.json();
      } catch {
        data = { success: true };
      }
    } else {
      data = { success: true };
    }

    if (!response.ok) {
      // 503 from /health/ready returns valid ReadinessResponse in data with degraded info
      if (response.status === 503 && typeof data === 'object' && data !== null && 'status' in data) {
        return data as T;
      }

      let errorMessage =
        typeof data === 'object' && data !== null && 'detail' in data && typeof (data as { detail: unknown }).detail === 'string'
          ? (data as { detail: string }).detail
          : `HTTP ${response.status}: ${response.statusText || 'Request failed'}`;

      let code = 'HTTP_ERROR';
      if (response.status === 404) {
        code = 'NOT_FOUND';
      } else if (response.status === 400) {
        code = 'BAD_REQUEST';
      } else if (response.status === 401 || response.status === 403) {
        code = 'AUTH_ERROR';
      } else if (response.status === 502 || response.status === 503) {
        code = 'SERVICE_UNAVAILABLE';
      } else if (response.status === 500) {
        const lower = errorMessage.toLowerCase();
        if (
          lower.includes('database') ||
          lower.includes('psycopg') ||
          lower.includes('operationalerror') ||
          lower.includes('connection timeout') ||
          lower.includes('could not connect')
        ) {
          code = 'DATABASE_ERROR';
          errorMessage = 'Database connection failure. PostgreSQL appears to be unavailable or timed out.';
        } else {
          code = 'SERVER_ERROR';
        }
      }

      throw new ApiClientError(errorMessage, response.status, code, data);
    }

    return data as T;
  } catch (err: unknown) {
    clearTimeout(id);

    if (err instanceof ApiClientError) {
      throw err;
    }

    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiClientError(
        `Request timed out after ${timeoutMs}ms. Backend service is unresponsive.`,
        408,
        'TIMEOUT'
      );
    }

    if (err instanceof TypeError && err.message.toLowerCase().includes('fetch')) {
      throw new ApiClientError(
        `Unable to connect to Knovera backend at ${url}. Please ensure the backend server is running and CORS is configured.`,
        0,
        'NETWORK_ERROR'
      );
    }

    const message = err instanceof Error ? err.message : 'Unknown network error';
    throw new ApiClientError(message, 0, 'UNKNOWN_ERROR');
  }
}

/**
 * Liveness Check: verifies FastAPI application process is up and running.
 */
export async function checkLiveness(
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
  signal?: AbortSignal
): Promise<LivenessResponse> {
  return apiFetch<LivenessResponse>('health', { method: 'GET', signal }, timeoutMs);
}

/**
 * Readiness Check: verifies PostgreSQL and ChromaDB dependency connectivity.
 */
export async function checkReadiness(
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
  signal?: AbortSignal
): Promise<ReadinessResponse> {
  return apiFetch<ReadinessResponse>('health/ready', { method: 'GET', signal }, timeoutMs);
}

/**
 * Aggregate Health Check: checks both liveness and readiness, measuring round-trip latency.
 */
export async function checkAggregateHealth(
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<{
  liveness: LivenessResponse;
  readiness: ReadinessResponse;
  latencyMs: number;
}> {
  const startTime = performance.now();
  const [liveness, readiness] = await Promise.all([
    checkLiveness(timeoutMs),
    checkReadiness(timeoutMs),
  ]);
  const latencyMs = Math.round(performance.now() - startTime);

  return {
    liveness,
    readiness,
    latencyMs,
  };
}
