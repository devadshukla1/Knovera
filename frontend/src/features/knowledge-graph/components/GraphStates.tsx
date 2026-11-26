/**
 * Knowledge Graph loading and error states (Phase 7 C7.8).
 */

import React from 'react';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

export const GraphLoadingState: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center p-16 text-center max-w-md mx-auto my-12 space-y-3">
      <div className="relative">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
      <h4 className="text-sm font-semibold text-text-primary">Loading Knowledge Graph...</h4>
      <p className="text-xs text-text-muted">
        Retrieving active graph snapshot, nodes, and relationship network.
      </p>
    </div>
  );
};

export interface GraphErrorStateProps {
  error?: Error | null;
  onRetry?: () => void;
}

export const GraphErrorState: React.FC<GraphErrorStateProps> = ({ error, onRetry }) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center max-w-md mx-auto my-8 bg-surface/50 border border-border rounded-2xl space-y-3">
      <div className="p-3 rounded-full bg-rose-500/10 text-rose-400">
        <AlertCircle className="h-7 w-7" />
      </div>
      <h4 className="text-sm font-bold text-text-primary">Failed to Load Knowledge Graph</h4>
      <p className="text-xs text-text-muted">
        {error?.message || 'An error occurred while loading the workspace graph snapshot.'}
      </p>
      {onRetry && (
        <Button onClick={onRetry} size="sm" variant="outline" className="gap-2 text-xs mt-2">
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Retry</span>
        </Button>
      )}
    </div>
  );
};
