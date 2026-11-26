import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/shared/PageHeader';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { BlurFade } from '@/components/magicui/BlurFade';

import { useTheme } from '@/context/ThemeContext';
import {
  Sun,
  Moon,
  Monitor,
  Sliders,
  ShieldCheck,
  Bot,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Cpu,
  Server,
  Zap,
} from 'lucide-react';
import { apiFetch, getApiBaseUrl } from '@/services/api';

interface LLMSettings {
  provider: string;
  model: string;
  is_configured: boolean;
  connection_status?:
    | 'active_ready'
    | 'configured'
    | 'authentication_failed'
    | 'model_unavailable'
    | 'provider_unreachable'
    | 'inference_failed'
    | 'not_configured';
  status_detail?: string | null;
  credential_configured?: boolean;
  provider_authenticated?: boolean;
  model_available?: boolean;
  inference_ok?: boolean;
  masked_api_key?: string | null;
}

interface TestConnectionResult {
  status: string;
  latency_ms?: number;
  model: string;
  message: string;
}

function getStatusBadgeProps(config?: LLMSettings) {
  const s = config?.connection_status;
  if (s === 'active_ready') {
    return {
      label: 'Active & Ready',
      className: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
      isOk: true,
    };
  }
  if (s === 'authentication_failed') {
    return {
      label: 'Authentication Failed',
      className: 'bg-destructive/15 text-destructive border-destructive/30',
      isOk: false,
    };
  }
  if (s === 'model_unavailable') {
    return {
      label: 'Model Unavailable',
      className: 'text-warning bg-warning/10 border-warning/30',
      isOk: false,
    };
  }
  if (s === 'provider_unreachable') {
    return {
      label: 'Provider Unreachable',
      className: 'bg-destructive/15 text-destructive border-destructive/30',
      isOk: false,
    };
  }
  if (s === 'inference_failed') {
    return {
      label: 'Inference Failed',
      className: 'bg-destructive/15 text-destructive border-destructive/30',
      isOk: false,
    };
  }
  if (s === 'configured' || config?.is_configured) {
    return {
      label: 'Configured',
      className: 'bg-primary/15 text-primary border-primary/30',
      isOk: false,
    };
  }
  return {
    label: 'Server Configuration Required',
    className: 'text-warning bg-warning/10 border-warning/30',
    isOk: false,
  };
}

export const SettingsPage: React.FC = () => {
  const { theme, setTheme, resolvedTheme } = useTheme();

  const [statusMessage, setStatusMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  // Fetch current LLM config (developer-managed centrally)
  const {
    data: llmConfig,
    refetch: refetchLlm,
  } = useQuery<LLMSettings>({
    queryKey: ['settings', 'llm'],
    queryFn: () => apiFetch<LLMSettings>('settings/llm'),
  });

  // Developer connection verification mutation
  const testConnectionMutation = useMutation<TestConnectionResult, Error>({
    mutationFn: () =>
      apiFetch<TestConnectionResult>('settings/llm/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      }),
    onSuccess: (result) => {
      setStatusMessage({
        type: 'success',
        text: `${result.message} (Active Model: ${result.model})`,
      });
      refetchLlm();
    },
    onError: (err) => {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Connection test failed. Verify server environment configuration.',
      });
    },
  });

  const handleTestConnection = () => {
    setStatusMessage(null);
    testConnectionMutation.mutate();
  };

  return (
    <PageContainer maxWidth="5xl">
      <BlurFade delay={0.05}>
        <PageHeader
          title="Settings & System Diagnostics"
          description="Manage your Knovera interface preferences, AI inference engine, and system runtime."
        />
      </BlurFade>

      <div className="settings-content space-y-6">
        {/* Centralized Developer-Managed AI Inference Engine */}
        <BlurFade delay={0.1}>
          <Card className="relative overflow-hidden border-border/80 bg-surface shadow-md">

            <CardHeader>
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20 shadow-glow-sm">
                    <Bot className="h-5 w-5" />
                  </div>
                  <div>
                    <CardTitle className="text-base font-semibold">
                      AI & LLM Intelligence Engine
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Centralized server-managed Groq Cloud hardware-accelerated inference.
                    </CardDescription>
                  </div>
                </div>
                <div>
                  {(() => {
                    const badge = getStatusBadgeProps(llmConfig);
                    return (
                      <Badge variant="outline" className={`text-[11px] gap-1.5 px-2.5 py-1 ${badge.className}`}>
                        {badge.isOk ? (
                          <CheckCircle2 className="h-3 w-3" />
                        ) : (
                          <AlertCircle className="h-3 w-3" />
                        )}
                        <span>{badge.label}</span>
                      </Badge>
                    );
                  })()}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-xl bg-surface-muted/50 p-4 border border-border/80 text-xs space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-text-muted flex items-center gap-1.5">
                    <Zap className="h-3.5 w-3.5 text-primary" /> Primary Inference Provider:
                  </span>
                  <span className="font-semibold text-text-primary capitalize flex items-center gap-1">
                    {llmConfig?.provider || 'Groq'} (LPU Hardware Fast-Inference)
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-text-muted flex items-center gap-1.5">
                    <Cpu className="h-3.5 w-3.5 text-accent" /> Active Model:
                  </span>
                  <span className="font-mono text-primary font-medium bg-primary/10 px-2 py-0.5 rounded-md border border-primary/20">
                    {llmConfig?.model || 'Not configured'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-text-muted flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> Credential Management:
                  </span>
                  <span className="text-text-secondary">
                    Centrally configured by Server Administrator (.env)
                  </span>
                </div>
              </div>

              <div className="rounded-xl bg-primary/5 p-4 border border-primary/15 text-xs text-text-secondary space-y-1">
                <div className="flex items-center gap-2 font-medium text-text-primary">
                  <ShieldCheck className="h-4 w-4 text-primary" />
                  <span>Zero User Credential Management</span>
                </div>
                <p className="text-[11px] text-text-muted leading-relaxed">
                  All AI inference operations are executed through the centralized developer-managed Groq key.
                  Standard users are never asked for API keys or vendor selections.
                </p>
              </div>

              {statusMessage && (
                <div
                  className={`p-3.5 rounded-xl text-xs flex items-center gap-2.5 ${
                    statusMessage.type === 'success'
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-destructive/10 text-destructive border border-destructive/20'
                  }`}
                >
                  {statusMessage.type === 'success' ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                  ) : (
                    <AlertCircle className="h-4 w-4 shrink-0" />
                  )}
                  <span>{statusMessage.text}</span>
                </div>
              )}

              <div className="flex items-center gap-3 pt-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleTestConnection}
                  disabled={testConnectionMutation.isPending}
                  className="gap-2 rounded-xl border-border/80"
                >
                  <RefreshCw
                    className={`h-3.5 w-3.5 ${
                      testConnectionMutation.isPending ? 'animate-spin' : ''
                    }`}
                  />
                  <span>
                    {testConnectionMutation.isPending ? 'Testing Inference...' : 'Verify Engine Connection'}
                  </span>
                </Button>
              </div>
            </CardContent>
          </Card>
        </BlurFade>

        {/* Appearance Section */}
        <BlurFade delay={0.15}>
          <Card className="border-border/80 bg-surface rounded-2xl">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
                  <Sliders className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle className="text-base font-semibold">Appearance & Theme</CardTitle>
                  <CardDescription className="text-xs">
                    Customise how Knovera looks on your device.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-xs font-medium text-text-primary mb-2.5">Interface Theme</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <Button
                    variant={theme === 'dark' ? 'default' : 'outline'}
                    size="default"
                    onClick={() => setTheme('dark')}
                    className={`justify-start gap-2.5 rounded-xl ${
                      theme === 'dark' ? 'shadow-glow-sm' : 'border-border/80'
                    }`}
                  >
                    <Moon className="h-4 w-4" />
                    <span>Dark (Default)</span>
                  </Button>
                  <Button
                    variant={theme === 'light' ? 'default' : 'outline'}
                    size="default"
                    onClick={() => setTheme('light')}
                    className={`justify-start gap-2.5 rounded-xl ${
                      theme === 'light' ? 'shadow-glow-sm' : 'border-border/80'
                    }`}
                  >
                    <Sun className="h-4 w-4 text-warning" />
                    <span>Light</span>
                  </Button>
                  <Button
                    variant={theme === 'system' ? 'default' : 'outline'}
                    size="default"
                    onClick={() => setTheme('system')}
                    className={`justify-start gap-2.5 rounded-xl ${
                      theme === 'system' ? 'shadow-glow-sm' : 'border-border/80'
                    }`}
                  >
                    <Monitor className="h-4 w-4" />
                    <span>System Preference</span>
                  </Button>
                </div>
                <p className="text-[11px] text-text-muted mt-2.5">
                  Active theme: <strong className="text-text-primary capitalize">{resolvedTheme}</strong>. Your choice is automatically persisted in local storage.
                </p>
              </div>
            </CardContent>
          </Card>
        </BlurFade>

        {/* System & Architecture Information */}
        <BlurFade delay={0.2}>
          <Card className="border-border/80 bg-surface rounded-2xl">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10 text-accent border border-accent/20">
                  <Server className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle className="text-base font-semibold">System Diagnostics</CardTitle>
                  <CardDescription className="text-xs">
                    Underlying platform runtime and native Windows configuration.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <div className="flex items-center justify-between py-2.5 border-b border-border/80">
                <span className="text-text-secondary">Platform Version</span>
                <span className="font-mono text-text-primary">Knovera v1.0.0</span>
              </div>
              <div className="flex items-center justify-between py-2.5 border-b border-border/80">
                <span className="text-text-secondary">Target Backend API</span>
                <span className="font-mono text-primary bg-primary/10 px-2 py-0.5 rounded-md border border-primary/20">
                  {getApiBaseUrl()}
                </span>
              </div>
              <div className="flex items-center justify-between py-2.5 border-b border-border/80">
                <span className="text-text-secondary">Architecture Pattern</span>
                <span className="font-medium text-text-primary">Native Windows Modular Architecture</span>
              </div>
              <div className="flex items-center justify-between py-2.5 border-b border-border/80">
                <span className="text-text-secondary">Vector Database Engine</span>
                <span className="font-mono text-emerald-400">ChromaDB v0.5.20 (Persistent Disk)</span>
              </div>
              <div className="flex items-center justify-between py-2.5">
                <span className="text-text-secondary">Session Mode</span>
                <span className="font-medium text-text-primary">Single-User Research Workspace</span>
              </div>
            </CardContent>
          </Card>
        </BlurFade>
      </div>
    </PageContainer>
  );
};
