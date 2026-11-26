import React, { useState, useEffect, useCallback } from 'react';
import { ThemeToggle } from '@/components/shared/ThemeToggle';
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Database,
  Layers,
  Cpu,
  ShieldCheck,
  ExternalLink,
  BookOpen,
  GitBranch,
} from 'lucide-react';
import {
  checkAggregateHealth,
  getApiBaseUrl,
  ApiClientError,
} from '@/services/api';
import {
  ConnectivityState,
  LivenessResponse,
  ReadinessResponse,
} from '@/types/health';

export const LandingView: React.FC = () => {
  const [state, setState] = useState<ConnectivityState>('loading');
  const [liveness, setLiveness] = useState<LivenessResponse | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const activeApiUrl = getApiBaseUrl();

  const probeConnectivity = useCallback(async () => {
    setIsRefreshing(true);
    setErrorMsg(null);

    try {
      const result = await checkAggregateHealth(7000);
      setLiveness(result.liveness);
      setReadiness(result.readiness);
      setLatencyMs(result.latencyMs);

      if (result.readiness.status === 'ready') {
        setState('success');
      } else {
        // Degraded state (e.g. DB or Chroma offline)
        setState('error');
        setErrorMsg('Backend process is online, but one or more dependency services are degraded or unavailable.');
      }
    } catch (err: unknown) {
      setState('error');
      if (err instanceof ApiClientError) {
        setErrorMsg(err.message);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg('An unexpected error occurred while communicating with the backend service.');
      }
      setLiveness(null);
      setReadiness(null);
      setLatencyMs(null);
    } finally {
      setLastChecked(new Date());
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    probeConnectivity();
  }, [probeConnectivity]);

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col justify-between selection:bg-primary-soft selection:text-text-primary font-sans">
      {/* Top Navigation Bar */}
      <header className="border-b border-border bg-surface/70 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            {/* Connected Node Logo Mark */}
            <div className="w-9 h-9 rounded-lg bg-surface-elevated border border-border flex items-center justify-center p-1.5 shadow-sm">
              <svg viewBox="0 0 32 32" fill="none" className="w-full h-full">
                <circle cx="8" cy="16" r="3.5" fill="#8B7CFF" />
                <circle cx="24" cy="9" r="3" fill="#58D6C7" />
                <circle cx="22" cy="23" r="3" fill="#42C98A" />
                <path
                  d="M10.8 14.5L21.5 10.2M10.8 17.5L19.5 21.8M22.5 11.5L21.2 20.2"
                  stroke="#2A3348"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </div>
            <div>
              <span className="text-lg font-semibold tracking-tight text-text-primary">
                Knovera
              </span>
              <span className="ml-2 text-xs font-medium px-2 py-0.5 rounded bg-surface-muted text-accent border border-border">
                Research workspace
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <span className="text-xs text-text-muted hidden md:inline-block">
              Your sources. Connected.
            </span>
            <ThemeToggle />
            <a
              href="/app"
              className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary-hover shadow-sm transition-colors"
            >
              <span>Dashboard</span>
            </a>
            <a
              href={`${activeApiUrl.replace(/\/api\/v1$/, '')}/docs`}
              target="_blank"
              rel="noreferrer"
              className="hidden sm:inline-flex items-center space-x-1.5 text-xs text-text-secondary hover:text-primary transition-colors px-2.5 py-1.5 rounded-md hover:bg-surface-muted"
            >
              <span>API Docs</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 flex-1 w-full flex flex-col justify-center">
        {/* Hero Section */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-surface-muted border border-border text-xs text-text-secondary mb-6">
            <span className="w-2 h-2 rounded-full bg-primary" />
            <span>AI-Powered Knowledge Intelligence Platform</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight text-text-primary mb-4 leading-tight">
            Turn Information into{' '}
            <span className="text-primary">Intelligence.</span>
          </h1>

          <p className="text-base sm:text-lg text-text-secondary max-w-2xl mx-auto leading-relaxed">
            Knovera is a focused research workspace for students and researchers.
            Synthesize papers, connect disparate concepts into knowledge graphs, and
            interact with evidence-first citations.
          </p>
        </div>

        {/* Real-Time Connectivity Monitor Card */}
        <div className="max-w-2xl mx-auto w-full mb-14">
          <div className="rounded-xl border border-border bg-surface shadow-lg overflow-hidden transition-all duration-200">
            {/* Monitor Header */}
            <div className="px-6 py-4 border-b border-border bg-surface-elevated/50 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Activity className="w-5 h-5 text-primary" />
                <h2 className="text-sm font-semibold text-text-primary">
                  Backend Connectivity Monitor
                </h2>
              </div>
              <button
                onClick={probeConnectivity}
                disabled={isRefreshing}
                className="inline-flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-md bg-surface-muted hover:bg-surface-elevated text-text-secondary hover:text-text-primary border border-border transition-colors disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                title="Trigger immediate health check"
                aria-label="Refresh backend status"
              >
                <RefreshCw
                  className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-primary' : ''}`}
                />
                <span>{isRefreshing ? 'Checking...' : 'Refresh Status'}</span>
              </button>
            </div>

            {/* Monitor Body States */}
            <div className="p-6">
              {state === 'loading' && (
                <div
                  data-testid="status-loading"
                  className="flex flex-col items-center justify-center py-8 text-center space-y-4"
                >
                  <div className="relative">
                    <div className="w-12 h-12 rounded-full border-2 border-border border-t-primary animate-spin" />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Cpu className="w-5 h-5 text-text-muted" />
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-text-primary">
                      Checking backend connectivity...
                    </p>
                    <p className="text-xs text-text-muted mt-1">
                      Querying probe at <code className="text-accent">{activeApiUrl}/health</code>
                    </p>
                  </div>
                </div>
              )}

              {state === 'success' && liveness && (
                <div data-testid="status-success" className="space-y-6">
                  {/* Status Banner */}
                  <div className="flex items-center justify-between p-4 rounded-lg bg-surface-muted border border-border">
                    <div className="flex items-center space-x-3">
                      <div className="w-9 h-9 rounded-full bg-success/15 flex items-center justify-center text-success">
                        <CheckCircle2 className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-sm font-semibold text-text-primary">
                            Backend Reachable & Healthy
                          </span>
                          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-success/20 text-success border border-success/30">
                            HTTP 200 OK
                          </span>
                        </div>
                        <p className="text-xs text-text-muted mt-0.5">
                          Knovera Core API v{liveness.version} ({liveness.environment})
                        </p>
                      </div>
                    </div>

                    {latencyMs !== null && (
                      <div className="text-right pl-4">
                        <span className="text-xs text-text-muted block">Round-trip</span>
                        <span className="text-sm font-semibold text-accent font-mono">
                          {latencyMs} ms
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Service Dependencies Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    {/* Relational DB */}
                    <div className="p-3.5 rounded-lg bg-surface-elevated border border-border flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <Database className="w-4 h-4 text-primary" />
                        <div>
                          <p className="text-xs font-medium text-text-primary">
                            PostgreSQL 16
                          </p>
                          <p className="text-[11px] text-text-muted">
                            Relational Metadata
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-1.5">
                        <span className="w-2 h-2 rounded-full bg-success" />
                        <span className="text-xs font-medium text-success capitalize">
                          {readiness?.services?.database?.status || 'connected'}
                        </span>
                        {readiness?.services?.database?.latency_ms !== undefined && (
                          <span className="text-[10px] text-text-muted font-mono ml-1">
                            ({readiness.services.database.latency_ms.toFixed(1)}ms)
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Vector DB */}
                    <div className="p-3.5 rounded-lg bg-surface-elevated border border-border flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <Layers className="w-4 h-4 text-accent" />
                        <div>
                          <p className="text-xs font-medium text-text-primary">
                            ChromaDB
                          </p>
                          <p className="text-[11px] text-text-muted">
                            Vector Store
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-1.5">
                        <span
                          className={`w-2 h-2 rounded-full ${
                            readiness?.services?.vector_store?.status === 'connected'
                              ? 'bg-success'
                              : 'bg-warning'
                          }`}
                        />
                        <span
                          className={`text-xs font-medium capitalize ${
                            readiness?.services?.vector_store?.status === 'connected'
                              ? 'text-success'
                              : 'text-warning'
                          }`}
                        >
                          {readiness?.services?.vector_store?.status || 'connected'}
                        </span>
                        {readiness?.services?.vector_store?.latency_ms !== undefined && (
                          <span className="text-[10px] text-text-muted font-mono ml-1">
                            ({readiness.services.vector_store.latency_ms.toFixed(1)}ms)
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {state === 'error' && (
                <div data-testid="status-error" className="space-y-4">
                  {/* Error Banner */}
                  <div className="p-4 rounded-lg bg-danger/10 border border-danger/30 flex items-start space-x-3.5">
                    <div className="w-8 h-8 rounded-full bg-danger/20 flex items-center justify-center text-danger shrink-0 mt-0.5">
                      {liveness ? (
                        <AlertTriangle className="w-4 h-4" />
                      ) : (
                        <XCircle className="w-4 h-4" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-semibold text-text-primary">
                          {liveness ? 'Backend Service Degraded' : 'Backend Unreachable'}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-danger/20 text-danger border border-danger/30">
                          {liveness ? 'Degraded (503)' : 'Connection Failed'}
                        </span>
                      </div>
                      <p className="text-xs text-text-secondary mt-1.5 leading-relaxed">
                        {errorMsg || 'Unable to establish HTTP connectivity to the Knovera backend server.'}
                      </p>
                    </div>
                  </div>

                  {/* Troubleshooting Guidance */}
                  <div className="p-4 rounded-lg bg-surface-muted border border-border text-xs text-text-secondary space-y-2">
                    <p className="font-semibold text-text-primary">Troubleshooting Steps:</p>
                    <ol className="list-decimal list-inside space-y-1 text-text-muted">
                      <li>
                        Ensure the FastAPI server is running:{' '}
                        <code className="text-text-primary font-mono bg-surface px-1.5 py-0.5 rounded border border-border">
                          .venv\Scripts\uvicorn backend.app.main:app --reload
                        </code>
                      </li>
                      <li>
                        Confirm Docker containers are up:{' '}
                        <code className="text-text-primary font-mono bg-surface px-1.5 py-0.5 rounded border border-border">
                          docker compose up -d
                        </code>
                      </li>
                      <li>
                        Check backend URL configuration in <code className="text-text-primary">frontend/.env</code>:{' '}
                        <code className="text-accent font-mono">{activeApiUrl}</code>
                      </li>
                    </ol>
                  </div>

                  {/* Retry Action */}
                  <div className="flex justify-end pt-1">
                    <button
                      onClick={probeConnectivity}
                      disabled={isRefreshing}
                      className="inline-flex items-center space-x-2 text-xs font-semibold px-4 py-2 rounded-md bg-primary hover:bg-primary-hover text-primary-foreground transition-colors disabled:opacity-50 cursor-pointer"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
                      <span>Retry Connection</span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Monitor Footer Info */}
            <div className="px-6 py-3 bg-surface-muted/40 border-t border-border flex items-center justify-between text-[11px] text-text-muted">
              <span className="truncate max-w-[320px]">
                Target: <code className="text-text-secondary">{activeApiUrl}</code>
              </span>
              <span>
                {lastChecked ? (
                  <>Last verified: {lastChecked.toLocaleTimeString()}</>
                ) : (
                  'Pending first check'
                )}
              </span>
            </div>
          </div>
        </div>

        {/* Feature Pillar Highlights */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto w-full">
          <div className="p-5 rounded-lg border border-border bg-surface/50 hover:bg-surface transition-colors">
            <div className="w-9 h-9 rounded-md bg-primary-soft flex items-center justify-center text-primary mb-3">
              <BookOpen className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-text-primary mb-1">
              Calm Research Workspace
            </h3>
            <p className="text-xs text-text-secondary leading-relaxed">
              Synthesize academic literature without distraction. Distraction-free, dark-first UI optimized for sustained reading.
            </p>
          </div>

          <div className="p-5 rounded-lg border border-border bg-surface/50 hover:bg-surface transition-colors">
            <div className="w-9 h-9 rounded-md bg-surface-muted flex items-center justify-center text-accent mb-3 border border-border">
              <GitBranch className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-text-primary mb-1">
              Connected Knowledge Graphs
            </h3>
            <p className="text-xs text-text-secondary leading-relaxed">
              Discover non-obvious cross-paper relationships and concept bridges mapped into interactive graph visualizations.
            </p>
          </div>

          <div className="p-5 rounded-lg border border-border bg-surface/50 hover:bg-surface transition-colors">
            <div className="w-9 h-9 rounded-md bg-surface-muted flex items-center justify-center text-success mb-3 border border-border">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-text-primary mb-1">
              Evidence-First Rigor
            </h3>
            <p className="text-xs text-text-secondary leading-relaxed">
              Every synthesized claim links directly to verbatim source passages with confidence scores and zero hallucinated citations.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-surface/40 py-6 text-center text-xs text-text-muted">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>&copy; {new Date().getFullYear()} Knovera. All rights reserved.</span>
          <div className="flex items-center space-x-4">
            <span>Research workspace Foundation</span>
            <span>&bull;</span>
            <span className="text-text-secondary">Vite + React + Tailwind + FastAPI</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
