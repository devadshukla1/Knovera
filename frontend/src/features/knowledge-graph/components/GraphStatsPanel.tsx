/**
 * Knowledge Graph summary statistics ribbon (Phase 7 C7.8).
 */

import React from 'react';
import { Network, GitFork, Boxes, PieChart, Layers } from 'lucide-react';
import { KnowledgeGraphOverviewResponse } from '../types/knowledgeGraph';
import { cn } from '@/lib/utils';

export interface GraphStatsPanelProps {
  overview?: KnowledgeGraphOverviewResponse | null;
  className?: string;
}

export const GraphStatsPanel: React.FC<GraphStatsPanelProps> = ({ overview, className }) => {
  if (!overview || !overview.has_graph || !overview.snapshot) return null;

  const {
    node_count = 0,
    concept_count = 0,
    entity_count = 0,
    edge_count = 0,
    component_count = 1,
    isolated_node_count = 0,
    ontology_version = '1.0.0',
  } = overview.snapshot;

  const density = overview.statistics?.density ?? 0;

  return (
    <div
      className={cn(
        'grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2.5 p-3 bg-surface/80 backdrop-blur-md border border-border rounded-xl shadow-sm text-xs',
        className
      )}
    >
      {/* Total Nodes */}
      <div className="flex items-center gap-2.5 px-2">
        <div className="p-1.5 rounded-lg bg-primary/10 text-primary shrink-0">
          <Network className="h-4 w-4" />
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-text-muted font-medium uppercase tracking-wider">
            Total Nodes
          </span>
          <div className="flex items-baseline gap-1.5">
            <span className="text-sm font-bold text-text-primary">{node_count}</span>
            <span className="text-[10px] text-text-muted">
              ({concept_count}c / {entity_count}e)
            </span>
          </div>
        </div>
      </div>

      {/* Relationships / Edges */}
      <div className="flex items-center gap-2.5 px-2 border-l border-border/40">
        <div className="p-1.5 rounded-lg bg-accent/10 text-accent shrink-0">
          <GitFork className="h-4 w-4" />
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-text-muted font-medium uppercase tracking-wider">
            Relationships
          </span>
          <span className="text-sm font-bold text-text-primary">{edge_count}</span>
        </div>
      </div>

      {/* Connected Components */}
      <div className="flex items-center gap-2.5 px-2 border-l border-border/40">
        <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 shrink-0">
          <Boxes className="h-4 w-4" />
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-text-muted font-medium uppercase tracking-wider">
            Components
          </span>
          <span className="text-sm font-bold text-text-primary">{component_count}</span>
        </div>
      </div>

      {/* Graph Density */}
      <div className="flex items-center gap-2.5 px-2 border-l border-border/40">
        <div className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 shrink-0">
          <PieChart className="h-4 w-4" />
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-text-muted font-medium uppercase tracking-wider">
            Density
          </span>
          <span className="text-sm font-bold text-text-primary">{density.toFixed(3)}</span>
        </div>
      </div>

      {/* Isolated Nodes */}
      <div className="flex items-center gap-2.5 px-2 border-l border-border/40">
        <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 shrink-0">
          <Layers className="h-4 w-4" />
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-text-muted font-medium uppercase tracking-wider">
            Isolated
          </span>
          <span className="text-sm font-bold text-text-primary">{isolated_node_count}</span>
        </div>
      </div>

      {/* Ontology Version */}
      <div className="flex items-center gap-2.5 px-2 border-l border-border/40">
        <div className="p-1.5 rounded-lg bg-violet-500/10 text-violet-400 shrink-0">
          <Network className="h-4 w-4" />
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-text-muted font-medium uppercase tracking-wider">
            Ontology
          </span>
          <span className="text-sm font-bold text-text-primary font-mono">
            v{ontology_version}
          </span>
        </div>
      </div>
    </div>
  );
};
