/**
 * Knowledge Graph Path Explorer modal (Phase 7 C7.8, C7.9).
 * Discovers and displays multi-hop reasoning chains between two concepts/entities with step evidence.
 */

import React, { useState } from 'react';
import {
  Route,
  Search,
  Loader2,
  AlertCircle,
  Sparkles,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { GraphNodeItem, GraphPathItem } from '../types/knowledgeGraph';
import { useKnowledgeGraphPaths } from '../hooks/useKnowledgeGraph';

export interface GraphPathExplorerModalProps {
  isOpen: boolean;
  onClose: () => void;
  workspaceId: string;
  snapshotId?: string;
  nodes: GraphNodeItem[];
  initialSourceId?: string | null;
  onHighlightPath?: (path: GraphPathItem) => void;
}

export const GraphPathExplorerModal: React.FC<GraphPathExplorerModalProps> = ({
  isOpen,
  onClose,
  workspaceId,
  snapshotId,
  nodes,
  initialSourceId,
  onHighlightPath,
}) => {
  const [sourceId, setSourceId] = useState<string>(initialSourceId || '');
  const [targetId, setTargetId] = useState<string>('');
  const [maxDepth, setMaxDepth] = useState<number>(3);
  const [shouldSearch, setShouldSearch] = useState<boolean>(false);

  // Sync initialSourceId when modal opens
  React.useEffect(() => {
    if (initialSourceId) {
      setSourceId(initialSourceId);
    }
  }, [initialSourceId]);

  // Query paths
  const {
    data: pathsData,
    isFetching,
    refetch,
  } = useKnowledgeGraphPaths(
    workspaceId,
    {
      sourceNodeId: sourceId,
      targetNodeId: targetId,
      maxHops: maxDepth,
      snapshotId: snapshotId,
    },
    Boolean(shouldSearch && sourceId && targetId && sourceId !== targetId)
  );

  const paths = pathsData?.paths || [];

  const handleFindPaths = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceId || !targetId || sourceId === targetId) return;
    setShouldSearch(true);
    refetch();
  };

  const handleSelectPath = (path: GraphPathItem) => {
    if (onHighlightPath) {
      onHighlightPath(path);
    }
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl bg-surface border border-border p-6 rounded-2xl shadow-2xl max-h-[85vh] flex flex-col">
        <DialogHeader className="pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-accent/10 text-accent">
              <Route className="h-5 w-5" />
            </div>
            <div>
              <DialogTitle className="text-base font-bold text-text-primary">
                Knowledge Path Explorer
              </DialogTitle>
              <DialogDescription className="text-xs text-text-muted">
                Discover multi-hop connection chains and reasoning paths between concepts.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Inputs */}
        <form onSubmit={handleFindPaths} className="py-3 space-y-3 border-b border-border text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Source Node */}
            <div className="space-y-1">
              <label className="text-[11px] font-medium text-text-muted uppercase">
                Source Concept / Entity
              </label>
              <select
                value={sourceId}
                onChange={(e) => {
                  setSourceId(e.target.value);
                  setShouldSearch(false);
                }}
                className="w-full bg-surface-muted text-text-primary text-xs rounded-lg px-2.5 py-1.5 border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                required
              >
                <option value="">Select source...</option>
                {nodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.label} ({n.node_kind})
                  </option>
                ))}
              </select>
            </div>

            {/* Target Node */}
            <div className="space-y-1">
              <label className="text-[11px] font-medium text-text-muted uppercase">
                Target Concept / Entity
              </label>
              <select
                value={targetId}
                onChange={(e) => {
                  setTargetId(e.target.value);
                  setShouldSearch(false);
                }}
                className="w-full bg-surface-muted text-text-primary text-xs rounded-lg px-2.5 py-1.5 border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                required
              >
                <option value="">Select target...</option>
                {nodes
                  .filter((n) => n.id !== sourceId)
                  .map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label} ({n.node_kind})
                    </option>
                  ))}
              </select>
            </div>
          </div>

          {/* Options */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-1.5">
              <span className="text-text-muted">Max Hops:</span>
              <select
                value={maxDepth}
                onChange={(e) => {
                  setMaxDepth(parseInt(e.target.value, 10));
                  setShouldSearch(false);
                }}
                className="bg-surface-muted text-text-primary text-xs rounded px-2 py-0.5 border border-border"
              >
                <option value={1}>1 hop</option>
                <option value={2}>2 hops</option>
                <option value={3}>3 hops</option>
                <option value={4}>4 hops</option>
              </select>
            </div>

            <Button
              type="submit"
              disabled={!sourceId || !targetId || sourceId === targetId || isFetching}
              size="sm"
              className="text-xs gap-1.5 h-8 px-4"
            >
              {isFetching ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Search className="h-3.5 w-3.5" />
              )}
              <span>Find Paths</span>
            </Button>
          </div>
        </form>

        {/* Results */}
        <div className="flex-1 overflow-y-auto py-3 space-y-2.5 min-h-[160px]">
          {isFetching ? (
            <div className="flex flex-col items-center justify-center p-8 text-xs text-text-muted gap-2">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <span>Searching knowledge graph for connection paths...</span>
            </div>
          ) : !shouldSearch ? (
            <div className="p-8 text-center text-xs text-text-muted">
              Select a source and target concept to explore the reasoning paths connecting them.
            </div>
          ) : paths.length === 0 ? (
            <div className="p-8 text-center text-xs text-text-muted bg-surface-muted/30 rounded-xl border border-border">
              <AlertCircle className="h-6 w-6 text-text-muted mx-auto mb-2" />
              <p className="font-medium text-text-primary">No connection path found</p>
              <p className="mt-1 text-text-muted">
                No paths connecting these concepts within {maxDepth} hops. Try increasing max hops.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-text-muted">
                <span>Discovered {paths.length} reasoning path{paths.length !== 1 ? 's' : ''}:</span>
                <span className="text-[11px] font-mono">Sorted by hop distance</span>
              </div>

              {paths.map((p, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-surface-muted/40 border border-border/70 hover:border-primary/50 transition-all space-y-2.5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-[10px] font-mono py-0 px-1.5 border-primary/30 text-primary">
                        Path #{idx + 1}
                      </Badge>
                      <span className="text-xs font-semibold text-text-primary">
                        {p.hop_count} hop{p.hop_count !== 1 ? 's' : ''} ({p.nodes.length} nodes)
                      </span>
                    </div>

                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleSelectPath(p)}
                      className="h-7 text-[11px] px-2.5 border-primary/40 text-primary hover:bg-primary/10 gap-1"
                    >
                      <Sparkles className="h-3 w-3" />
                      <span>Highlight in Graph</span>
                    </Button>
                  </div>

                  {/* Step-by-step chain */}
                  <div className="flex items-center flex-wrap gap-1.5 text-xs bg-surface p-2.5 rounded-lg border border-border/50">
                    {p.nodes.map((nodeItem, nIdx) => {
                      const edge = p.edges[nIdx];
                      return (
                        <React.Fragment key={nIdx}>
                          <span className="font-semibold text-text-primary bg-surface-muted px-2 py-0.5 rounded border border-border/50">
                            {nodeItem.label}
                          </span>
                          {edge && (
                            <span className="flex items-center gap-1 text-[11px] font-mono text-primary px-1">
                              ── {edge.predicate} ──▶
                            </span>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
