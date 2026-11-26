import React from 'react';
import {
  Layers,
  FileText,
  Files,
  Cpu,
  History,
  CheckCircle2,
  ChevronDown,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TopicRunSummary } from '../types/topic';

interface TopicSummaryHeaderProps {
  totalTopics: number;
  totalChunks: number;
  totalDocuments: number;
  activeRun?: TopicRunSummary | null;
  runs: TopicRunSummary[];
  selectedRunId?: string;
  onSelectRun: (runId?: string) => void;
}

export const TopicSummaryHeader: React.FC<TopicSummaryHeaderProps> = ({
  totalTopics,
  totalChunks,
  totalDocuments,
  activeRun,
  runs,
  selectedRunId,
  onSelectRun,
}) => {
  const currentRun = runs.find((r) => r.id === selectedRunId) || activeRun;

  return (
    <div className="space-y-4 mb-6">
      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        <Card className="p-4 rounded-xl border border-border bg-surface flex flex-col justify-between">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs font-medium">Discovered Topics</span>
            <Layers className="w-4 h-4 text-primary" />
          </div>
          <div className="text-2xl font-bold text-text-primary tracking-tight">
            {totalTopics}
          </div>
          <p className="text-[11px] text-text-muted mt-1">Semantic clusters</p>
        </Card>

        <Card className="p-4 rounded-xl border border-border bg-surface flex flex-col justify-between">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs font-medium">Clustered Chunks</span>
            <FileText className="w-4 h-4 text-accent" />
          </div>
          <div className="text-2xl font-bold text-text-primary tracking-tight">
            {totalChunks}
          </div>
          <p className="text-[11px] text-text-muted mt-1">Across corpus</p>
        </Card>

        <Card className="p-4 rounded-xl border border-border bg-surface flex flex-col justify-between">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs font-medium">Documents Covered</span>
            <Files className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-text-primary tracking-tight">
            {totalDocuments}
          </div>
          <p className="text-[11px] text-text-muted mt-1">Active files</p>
        </Card>

        <Card className="p-4 rounded-xl border border-border bg-surface flex flex-col justify-between">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs font-medium">Model & Clusters</span>
            <Cpu className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-text-primary tracking-tight">
            K = {currentRun?.k || totalTopics || '—'}
          </div>
          <p className="text-[11px] text-text-muted mt-1 truncate">
            {(currentRun as any)?.algorithm || currentRun?.model_version || 'K-Means'}
          </p>
        </Card>
      </div>

      {/* Run Selection & Status Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg border border-border/70 bg-surface-muted/40 text-xs">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-text-muted font-medium flex items-center gap-1.5">
            <History className="w-3.5 h-3.5" />
            Clustering Run:
          </span>
          {currentRun?.is_active && (
            <Badge
              variant="outline"
              className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-[10px] py-0"
            >
              <CheckCircle2 className="w-2.5 h-2.5 mr-1" />
              Active
            </Badge>
          )}
          <span className="font-mono text-text-secondary">
            {currentRun ? `run_${currentRun.id.slice(0, 8)}` : 'No run loaded'}
          </span>
          {currentRun?.completed_at && (
            <span className="text-text-muted">
              • completed {new Date(currentRun.completed_at).toLocaleDateString()}
            </span>
          )}
        </div>

        {/* Run Selector if historical runs exist */}
        {runs.length > 1 && (
          <div className="flex items-center gap-2 self-start sm:self-auto">
            <label htmlFor="run-selector" className="text-text-muted text-[11px]">
              Switch Run:
            </label>
            <div className="relative">
              <select
                id="run-selector"
                value={selectedRunId || activeRun?.id || ''}
                onChange={(e) => onSelectRun(e.target.value ? e.target.value : undefined)}
                className="appearance-none bg-surface border border-border rounded-md px-2.5 py-1 pr-6 text-xs text-text-primary focus:outline-none focus:border-primary cursor-pointer"
              >
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.is_active ? '★ ' : ''}K={r.k} ({r.id.slice(0, 8)}) — {new Date(r.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3 h-3 absolute right-1.5 top-2 pointer-events-none text-text-muted" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
