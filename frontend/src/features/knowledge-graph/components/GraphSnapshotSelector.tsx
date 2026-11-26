/**
 * Knowledge Graph snapshot selector for switching between active and historical versions (Phase 7 C7.8).
 */

import React from 'react';
import { History, AlertTriangle, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { useKnowledgeGraphSnapshots } from '../hooks/useKnowledgeGraph';
import { cn } from '@/lib/utils';

export interface GraphSnapshotSelectorProps {
  workspaceId: string;
  selectedSnapshotId?: string;
  onSelectSnapshot: (snapshotId?: string) => void;
  className?: string;
}

export const GraphSnapshotSelector: React.FC<GraphSnapshotSelectorProps> = ({
  workspaceId,
  selectedSnapshotId,
  onSelectSnapshot,
  className,
}) => {
  const { data: snapshotsData, isLoading } = useKnowledgeGraphSnapshots(workspaceId);
  const snapshots = snapshotsData?.items || [];

  const activeSnapshot = snapshots.find((s) => s.is_active);
  const currentSnapshot = selectedSnapshotId
    ? snapshots.find((s) => s.id === selectedSnapshotId)
    : activeSnapshot;

  const isHistorical = currentSnapshot && !currentSnapshot.is_active;

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="flex items-center gap-1.5 bg-surface/90 border border-border rounded-xl px-2.5 py-1 text-xs">
        <History className="h-3.5 w-3.5 text-text-muted shrink-0" />
        <span className="text-text-muted text-[11px] font-medium hidden sm:inline">Version:</span>

        <select
          value={selectedSnapshotId || (activeSnapshot ? activeSnapshot.id : '')}
          onChange={(e) => {
            const val = e.target.value;
            if (activeSnapshot && val === activeSnapshot.id) {
              onSelectSnapshot(undefined); // undefined means active snapshot
            } else {
              onSelectSnapshot(val);
            }
          }}
          disabled={isLoading || snapshots.length === 0}
          className="bg-transparent text-text-primary text-xs font-medium focus:outline-none cursor-pointer pr-1"
          aria-label="Select knowledge graph snapshot"
        >
          {snapshots.map((snap, idx) => (
            <option key={snap.id} value={snap.id} className="bg-surface text-text-primary">
              v{snapshots.length - idx} {snap.is_active ? '(Active)' : `(${new Date(snap.created_at).toLocaleDateString()})`} — {snap.node_count} nodes
            </option>
          ))}
          {snapshots.length === 0 && (
            <option value="">No snapshots found</option>
          )}
        </select>

        {isHistorical ? (
          <Badge
            variant="outline"
            className="border-amber-500/30 text-amber-400 bg-amber-500/10 text-[10px] py-0 px-1.5 flex items-center gap-1"
          >
            <AlertTriangle className="h-2.5 w-2.5" />
            <span>Read-Only</span>
          </Badge>
        ) : (
          <Badge
            variant="outline"
            className="border-emerald-500/30 text-emerald-400 bg-emerald-500/10 text-[10px] py-0 px-1.5 flex items-center gap-1"
          >
            <ShieldCheck className="h-2.5 w-2.5" />
            <span>Active</span>
          </Badge>
        )}
      </div>
    </div>
  );
};
