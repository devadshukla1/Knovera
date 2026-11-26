/**
 * Knowledge Graph filters panel (Phase 7 C7.8).
 * Supports filtering nodes by kind (Concept vs Entity), category, predicate, and confidence threshold.
 */

import React from 'react';
import { Filter, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface GraphFilterState {
  showConcepts: boolean;
  showEntities: boolean;
  selectedCategory: string; // 'all' or specific category
  selectedPredicate: string; // 'all' or specific predicate
  minConfidence: number; // 0.0 to 1.0
}

export interface GraphFiltersProps {
  filters: GraphFilterState;
  onChange: (nextFilters: GraphFilterState) => void;
  availableCategories?: string[];
  availablePredicates?: string[];
  className?: string;
}

export const defaultGraphFilters: GraphFilterState = {
  showConcepts: true,
  showEntities: true,
  selectedCategory: 'all',
  selectedPredicate: 'all',
  minConfidence: 0.0,
};

export const GraphFilters: React.FC<GraphFiltersProps> = ({
  filters,
  onChange,
  availableCategories = [],
  availablePredicates = [],
  className,
}) => {
  const isFiltered =
    !filters.showConcepts ||
    !filters.showEntities ||
    filters.selectedCategory !== 'all' ||
    filters.selectedPredicate !== 'all' ||
    filters.minConfidence > 0;

  const handleReset = () => {
    onChange(defaultGraphFilters);
  };

  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-2 px-3 py-2 bg-surface/80 backdrop-blur-sm border border-border rounded-xl text-xs',
        className
      )}
    >
      <div className="flex items-center gap-1.5 text-text-muted mr-1 font-medium">
        <Filter className="h-3.5 w-3.5 text-primary" />
        <span>Filters:</span>
      </div>

      {/* Node Kind toggles */}
      <div className="flex items-center gap-1 bg-surface-muted/60 p-0.5 rounded-lg border border-border/60">
        <button
          type="button"
          onClick={() => onChange({ ...filters, showConcepts: !filters.showConcepts })}
          className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-colors',
            filters.showConcepts
              ? 'bg-violet-600/20 text-violet-300 border border-violet-500/30'
              : 'text-text-muted hover:text-text-primary'
          )}
          title="Toggle Concepts visibility"
        >
          <span className="w-2 h-2 rounded-full bg-violet-400" />
          <span>Concepts</span>
        </button>

        <button
          type="button"
          onClick={() => onChange({ ...filters, showEntities: !filters.showEntities })}
          className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-colors',
            filters.showEntities
              ? 'bg-teal-600/20 text-teal-300 border border-teal-500/30'
              : 'text-text-muted hover:text-text-primary'
          )}
          title="Toggle Entities visibility"
        >
          <span className="w-2 h-2 rounded-full bg-teal-400" />
          <span>Entities</span>
        </button>
      </div>

      {/* Category selector */}
      {availableCategories.length > 0 && (
        <div className="flex items-center gap-1">
          <select
            value={filters.selectedCategory}
            onChange={(e) => onChange({ ...filters, selectedCategory: e.target.value })}
            className="bg-surface-muted text-text-primary text-xs rounded-lg px-2.5 py-1 border border-border focus:outline-none focus:ring-1 focus:ring-primary h-7"
            aria-label="Filter by node category"
          >
            <option value="all">All Categories</option>
            {availableCategories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Predicate selector */}
      {availablePredicates.length > 0 && (
        <div className="flex items-center gap-1">
          <select
            value={filters.selectedPredicate}
            onChange={(e) => onChange({ ...filters, selectedPredicate: e.target.value })}
            className="bg-surface-muted text-text-primary text-xs rounded-lg px-2.5 py-1 border border-border focus:outline-none focus:ring-1 focus:ring-primary h-7"
            aria-label="Filter by relationship predicate"
          >
            <option value="all">All Predicates</option>
            {availablePredicates.map((pred) => (
              <option key={pred} value={pred}>
                {pred}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Min Confidence slider */}
      <div className="flex items-center gap-1.5 bg-surface-muted/60 px-2 py-1 rounded-lg border border-border/60">
        <span className="text-[11px] text-text-muted">Min Conf:</span>
        <input
          type="range"
          min="0"
          max="0.9"
          step="0.1"
          value={filters.minConfidence}
          onChange={(e) => onChange({ ...filters, minConfidence: parseFloat(e.target.value) })}
          className="w-16 h-1.5 accent-primary cursor-pointer"
          title={`Min Confidence: ${filters.minConfidence.toFixed(1)}`}
        />
        <span className="font-mono text-[10px] text-text-secondary w-5">
          {filters.minConfidence > 0 ? filters.minConfidence.toFixed(1) : 'Any'}
        </span>
      </div>

      {/* Reset button if active filters */}
      {isFiltered && (
        <Button
          variant="ghost"
          size="sm"
          onClick={handleReset}
          className="h-7 px-2 text-[11px] text-text-muted hover:text-text-primary gap-1"
        >
          <RotateCcw className="h-3 w-3" />
          <span>Reset</span>
        </Button>
      )}
    </div>
  );
};
