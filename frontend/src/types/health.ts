/**
 * Knovera Health Check Type Definitions
 * Matches backend schemas in backend/app/api/v1/endpoints/health.py
 */

export interface LivenessResponse {
  status: string;
  app: string;
  version: string;
  environment: string;
}

export interface ServiceDependencyStatus {
  status: 'connected' | 'disconnected' | string;
  latency_ms?: number;
  error?: string;
}

export interface ReadinessResponse {
  status: 'ready' | 'not_ready' | string;
  services: {
    database?: ServiceDependencyStatus;
    vector_store?: ServiceDependencyStatus;
    [key: string]: ServiceDependencyStatus | undefined;
  };
}

export interface ApiErrorResponse {
  message: string;
  code?: string;
  status?: number;
  details?: unknown;
  timestamp?: string;
}

export type ConnectivityState = 'idle' | 'loading' | 'success' | 'error';

export interface BackendConnectivity {
  state: ConnectivityState;
  latencyMs?: number;
  liveness?: LivenessResponse;
  readiness?: ReadinessResponse;
  error?: string;
  lastChecked?: Date;
  endpointUrl: string;
}
