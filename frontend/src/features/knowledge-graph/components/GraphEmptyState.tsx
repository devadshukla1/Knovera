/**
 * Knowledge Graph empty & onboarding state component with pipeline generation progress.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import {
  Network,
  Upload,
  Sparkles,
  FileText,
  Layers,
  Loader2,
  CheckCircle2,
  BrainCircuit,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface GraphEmptyStateProps {
  workspaceId: string;
  readyDocumentsCount?: number;
  topicsCount?: number;
  onBuildGraph?: () => void;
  isBuilding?: boolean;
  buildStepIndex?: number;
}

const BUILD_STEPS = [
  'Analyzing uploaded workspace documents...',
  'Extracting core concepts and canonical entities...',
  'Identifying relationships and prerequisite dependencies...',
  'Organizing pedagogical learning sequence...',
  'Finalizing interactive knowledge roadmap...',
];

export const GraphEmptyState: React.FC<GraphEmptyStateProps> = ({
  workspaceId,
  readyDocumentsCount = 0,
  topicsCount = 0,
  onBuildGraph,
  isBuilding = false,
  buildStepIndex = 0,
}) => {
  // Case A: Building / Pipeline running
  if (isBuilding) {
    const currentStepText = BUILD_STEPS[Math.min(buildStepIndex, BUILD_STEPS.length - 1)];

    return (
      <div className="flex flex-col items-center justify-center p-8 sm:p-12 text-center max-w-xl mx-auto bg-surface-elevated/90 border border-primary/30 rounded-3xl shadow-xl my-12 backdrop-blur-xl animate-in fade-in duration-300">
        <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/30 to-accent-purple/20 border border-primary/40 flex items-center justify-center text-primary mb-6 shadow-glow-sm">
          <BrainCircuit className="h-8 w-8 animate-pulse motion-reduce:animate-none" />
          <span className="absolute -inset-1 rounded-2xl bg-primary/20 blur-sm animate-ping motion-reduce:animate-none opacity-40 pointer-events-none" />
        </div>

        <h3 className="text-xl font-bold text-text-primary tracking-tight">
          Constructing Knowledge Roadmap
        </h3>
        <p className="mt-1.5 text-xs text-text-secondary leading-relaxed max-w-md">
          Please wait while Knovera synthesizes concept prerequisites and multi-hop relationships.
        </p>

        {/* Current Stage Indicator */}
        <div className="w-full mt-6 p-4 rounded-2xl border border-primary/20 bg-surface/80 flex items-center gap-3 text-left">
          <Loader2 className="h-5 w-5 animate-spin text-primary shrink-0" />
          <div className="min-w-0 flex-1">
            <span className="text-[10px] font-semibold text-primary uppercase tracking-wider block">
              Step {buildStepIndex + 1} of {BUILD_STEPS.length}
            </span>
            <p className="text-xs font-medium text-text-primary truncate">
              {currentStepText}
            </p>
          </div>
        </div>

        {/* Multi-Step Timeline */}
        <div className="w-full mt-4 space-y-2 text-left">
          {BUILD_STEPS.map((step, idx) => {
            const isDone = idx < buildStepIndex;
            const isCurrent = idx === buildStepIndex;

            return (
              <div
                key={step}
                className={cn(
                  'flex items-center gap-2.5 text-xs px-3 py-1.5 rounded-lg transition-colors',
                  isDone
                    ? 'text-emerald-400 font-medium'
                    : isCurrent
                    ? 'text-primary font-semibold bg-primary/10 border border-primary/20'
                    : 'text-text-muted opacity-50'
                )}
              >
                {isDone ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                ) : isCurrent ? (
                  <span className="h-2 w-2 rounded-full bg-primary animate-ping shrink-0" />
                ) : (
                  <span className="h-2 w-2 rounded-full bg-border shrink-0" />
                )}
                <span className="truncate">{step}</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Case B: Ready documents exist -> prompt to create roadmap
  if (readyDocumentsCount > 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 sm:p-12 text-center max-w-xl mx-auto bg-surface-elevated/90 border border-border/80 rounded-3xl shadow-xl my-10 backdrop-blur-xl">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-accent-purple/10 border border-primary/30 flex items-center justify-center text-primary mb-5 shadow-glow-sm">
          <Network className="h-8 w-8" />
        </div>

        <h3 className="text-xl font-bold text-text-primary tracking-tight">
          Create Your Knowledge Roadmap
        </h3>

        <p className="mt-2 text-xs sm:text-sm text-text-secondary leading-relaxed max-w-md">
          Transform your indexed source documents into an interactive semantic network with prerequisite dependencies and mastery tracking.
        </p>

        {/* Document & Topic Readiness Summary */}
        <div className="grid grid-cols-2 gap-3 w-full max-w-sm mt-5">
          <div className="p-3 rounded-xl border border-border bg-surface-muted/40 text-left">
            <div className="flex items-center gap-2 text-primary text-xs font-semibold">
              <FileText className="h-4 w-4" />
              <span>{readyDocumentsCount} Ready Document{readyDocumentsCount > 1 ? 's' : ''}</span>
            </div>
            <p className="text-[11px] text-text-muted mt-0.5">Available for concept extraction</p>
          </div>
          <div className="p-3 rounded-xl border border-border bg-surface-muted/40 text-left">
            <div className="flex items-center gap-2 text-accent-purple text-xs font-semibold">
              <Layers className="h-4 w-4" />
              <span>{topicsCount} Discovered Topic{topicsCount > 1 ? 's' : ''}</span>
            </div>
            <p className="text-[11px] text-text-muted mt-0.5">Identified thematic clusters</p>
          </div>
        </div>

        {/* Trigger Action */}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <Button
            onClick={onBuildGraph}
            size="sm"
            className="gap-2 text-xs h-9 px-5 rounded-xl bg-primary hover:bg-primary-hover text-white shadow-sm"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Create Knowledge Graph</span>
          </Button>
          <Link to={`/app/workspaces/${encodeURIComponent(workspaceId)}/documents`}>
            <Button variant="outline" size="sm" className="gap-2 text-xs h-9 px-4 rounded-xl border-border hover:bg-surface-muted">
              <Upload className="h-3.5 w-3.5" />
              <span>Manage Documents</span>
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  // Case C: No documents exist in workspace
  return (
    <div className="flex flex-col items-center justify-center p-8 sm:p-12 text-center max-w-lg mx-auto bg-surface-elevated/70 border border-border/80 rounded-3xl shadow-sm my-10 backdrop-blur-xl">
      <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary mb-5 shadow-inner">
        <Network className="h-8 w-8" />
      </div>

      <h3 className="text-lg font-bold text-text-primary tracking-tight">
        No Documents in this Workspace
      </h3>

      <p className="mt-2 text-xs text-text-muted leading-relaxed">
        Upload research papers, lecture notes, or technical documents to extract concepts, normalize entities, and construct an interactive knowledge roadmap.
      </p>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <Link to={`/app/workspaces/${encodeURIComponent(workspaceId)}/documents`}>
          <Button size="sm" className="gap-2 text-xs h-9 px-4 rounded-xl">
            <Upload className="h-3.5 w-3.5" />
            <span>Upload Documents</span>
          </Button>
        </Link>
      </div>
    </div>
  );
};
