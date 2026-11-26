/**
 * Knowledge Graph toolbar with viewport navigation, layout selector, and expand actions (Phase 7 C7.8).
 */

import React from 'react';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  RefreshCw,
  GitFork,
  Route,
  Layers,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export interface GraphToolbarProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  onReset: () => void;
  layoutName: 'cose' | 'concentric' | 'breadthfirst' | 'grid';
  onLayoutChange: (layout: 'cose' | 'concentric' | 'breadthfirst' | 'grid') => void;
  selectedNodeId: string | null;
  onExpandNode: () => void;
  isExpanding?: boolean;
  onOpenPathFinder: () => void;
  visibleNodeCount: number;
  visibleEdgeCount: number;
}

export const GraphToolbar: React.FC<GraphToolbarProps> = ({
  onZoomIn,
  onZoomOut,
  onFit,
  onReset,
  layoutName,
  onLayoutChange,
  selectedNodeId,
  onExpandNode,
  isExpanding = false,
  onOpenPathFinder,
  visibleNodeCount,
  visibleEdgeCount,
}) => {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2.5 p-2.5 bg-surface/90 backdrop-blur-md border border-border rounded-xl shadow-lg">
      {/* Left: Viewport Controls */}
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          onClick={onZoomIn}
          className="h-8 w-8 text-text-muted hover:text-text-primary"
          title="Zoom In"
          aria-label="Zoom In"
        >
          <ZoomIn className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onZoomOut}
          className="h-8 w-8 text-text-muted hover:text-text-primary"
          title="Zoom Out"
          aria-label="Zoom Out"
        >
          <ZoomOut className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onFit}
          className="h-8 w-8 text-text-muted hover:text-text-primary"
          title="Fit to Screen"
          aria-label="Fit to Screen"
        >
          <Maximize2 className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onReset}
          className="h-8 w-8 text-text-muted hover:text-text-primary"
          title="Reset View"
          aria-label="Reset View"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>

        <div className="h-4 w-[1px] bg-border mx-1" />

        {/* Layout selector */}
        <div className="flex items-center gap-1.5 text-xs text-text-muted">
          <Layers className="h-3.5 w-3.5" />
          <select
            value={layoutName}
            onChange={(e) => onLayoutChange(e.target.value as any)}
            className="bg-surface-muted text-text-primary text-xs rounded-md px-2 py-1 border border-border focus:outline-none focus:ring-1 focus:ring-primary"
            aria-label="Graph Layout Algorithm"
          >
            <option value="cose">Force-Directed (CoSE)</option>
            <option value="concentric">Concentric Circles</option>
            <option value="breadthfirst">Hierarchical (BFS)</option>
            <option value="grid">Grid</option>
          </select>
        </div>
      </div>

      {/* Center / Right: Graph Actions */}
      <div className="flex items-center gap-2">
        {selectedNodeId && (
          <Button
            variant="outline"
            size="sm"
            onClick={onExpandNode}
            disabled={isExpanding}
            className="h-8 text-xs gap-1.5 border-primary/40 text-primary hover:bg-primary/10"
            title="Fetch connected neighbors and expand graph canvas"
          >
            <GitFork className="h-3.5 w-3.5" />
            <span>{isExpanding ? 'Expanding...' : 'Expand Neighbors'}</span>
          </Button>
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={onOpenPathFinder}
          className="h-8 text-xs gap-1.5 border-accent/40 text-accent hover:bg-accent/10"
          title="Explore connection paths between two concepts"
        >
          <Route className="h-3.5 w-3.5" />
          <span>Path Finder</span>
        </Button>

        <div className="h-4 w-[1px] bg-border mx-1 hidden sm:block" />

        {/* Count indicators */}
        <div className="hidden sm:flex items-center gap-2 text-xs">
          <Badge variant="outline" className="font-mono text-[10px]">
            {visibleNodeCount} nodes
          </Badge>
          <Badge variant="outline" className="font-mono text-[10px]">
            {visibleEdgeCount} edges
          </Badge>
        </div>
      </div>
    </div>
  );
};
