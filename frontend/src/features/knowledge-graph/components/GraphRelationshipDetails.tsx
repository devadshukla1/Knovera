/**
 * Relationship details drawer with verified source evidence and document traceability (Phase 7 C7.8, C7.9).
 * Features direct navigation to source documents with page, slide, section, and chunk location parameters.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import {
  X,
  FileText,
  ExternalLink,
  GitFork,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  useKnowledgeGraphRelationshipDetails,
  useKnowledgeGraphRelationshipEvidence,
} from '../hooks/useKnowledgeGraph';
import { cn } from '@/lib/utils';

export interface GraphRelationshipDetailsProps {
  workspaceId: string;
  relationshipId: string;
  snapshotId?: string;
  onClose: () => void;
  onSelectNode: (nodeId: string) => void;
  className?: string;
}

export const GraphRelationshipDetails: React.FC<GraphRelationshipDetailsProps> = ({
  workspaceId,
  relationshipId,
  snapshotId,
  onClose,
  onSelectNode,
  className,
}) => {
  // Fetch relationship metadata
  const { data: rel, isLoading: isLoadingRel } = useKnowledgeGraphRelationshipDetails(
    workspaceId,
    relationshipId,
    snapshotId
  );

  // Fetch verified source evidence
  const { data: evidenceData, isLoading: isLoadingEvidence } =
    useKnowledgeGraphRelationshipEvidence(workspaceId, relationshipId);

  const evidenceList = evidenceData?.items || [];

  if (isLoadingRel) {
    return (
      <div className={cn('w-80 md:w-96 bg-surface border-l border-border p-6 flex flex-col items-center justify-center', className)}>
        <Loader2 className="h-6 w-6 animate-spin text-primary mb-2" />
        <span className="text-xs text-text-muted">Loading relationship details...</span>
      </div>
    );
  }

  if (!rel) {
    return (
      <div className={cn('w-80 md:w-96 bg-surface border-l border-border p-6', className)}>
        <div className="flex justify-between items-center mb-4">
          <span className="text-sm font-semibold text-text-primary">Relationship Details</span>
          <Button variant="ghost" size="icon" onClick={onClose} className="h-7 w-7">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <p className="text-xs text-text-muted">Relationship could not be found in active snapshot.</p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'w-80 md:w-96 bg-surface/95 backdrop-blur-xl border-l border-border flex flex-col h-full shadow-2xl z-30 transition-all',
        className
      )}
    >
      {/* Header */}
      <div className="p-4 border-b border-border flex items-start justify-between gap-3 bg-surface-muted/30">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2">
            <GitFork className="h-3.5 w-3.5 text-primary" />
            <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Relationship Details
            </span>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
            <Badge variant="outline" className="font-mono text-xs font-bold border-primary/40 text-primary">
              {rel.predicate}
            </Badge>
            <Badge variant="secondary" className="text-[10px] py-0 px-1.5">
              {rel.validation_status}
            </Badge>
          </div>
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="h-7 w-7 text-text-muted hover:text-text-primary shrink-0"
          aria-label="Close details"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Connection Triple (Source -> Predicate -> Target) */}
        <div className="p-3 rounded-lg bg-surface-muted/40 border border-border/70 space-y-2">
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block">
            Knowledge Triple
          </span>

          <div className="flex flex-col gap-1.5 text-xs">
            <div className="flex items-center justify-between gap-2 p-1.5 rounded-md bg-surface border border-border/50">
              <span className="text-[10px] text-text-muted font-mono">Subject:</span>
              <button
                type="button"
                onClick={() => onSelectNode(rel.source_node_id)}
                className="font-semibold text-text-primary hover:text-primary truncate text-right transition-colors"
                title={`Jump to ${rel.source_node_label}`}
              >
                {rel.source_node_label}
              </button>
            </div>

            <div className="flex items-center justify-center gap-1 text-[11px] text-primary font-mono py-0.5">
              <span>── {rel.predicate} ──▶</span>
            </div>

            <div className="flex items-center justify-between gap-2 p-1.5 rounded-md bg-surface border border-border/50">
              <span className="text-[10px] text-text-muted font-mono">Object:</span>
              <button
                type="button"
                onClick={() => onSelectNode(rel.target_node_id)}
                className="font-semibold text-text-primary hover:text-primary truncate text-right transition-colors"
                title={`Jump to ${rel.target_node_label}`}
              >
                {rel.target_node_label}
              </button>
            </div>
          </div>
        </div>

        {/* Triple Metadata Badges */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="p-2 rounded-lg bg-surface-muted/30 border border-border/50">
            <span className="text-[10px] text-text-muted block">Confidence</span>
            <span className="font-mono font-bold text-text-primary">
              {(rel.confidence * 100).toFixed(1)}%
            </span>
          </div>

          <div className="p-2 rounded-lg bg-surface-muted/30 border border-border/50">
            <span className="text-[10px] text-text-muted block">Polarity</span>
            <span className={cn('font-mono font-semibold', rel.polarity === 'negative' ? 'text-rose-400' : 'text-emerald-400')}>
              {rel.polarity || 'positive'}
            </span>
          </div>

          <div className="p-2 rounded-lg bg-surface-muted/30 border border-border/50">
            <span className="text-[10px] text-text-muted block">Modality</span>
            <span className="font-mono text-text-secondary">
              {rel.modality || 'asserted'}
            </span>
          </div>

          <div className="p-2 rounded-lg bg-surface-muted/30 border border-border/50">
            <span className="text-[10px] text-text-muted block">Evidence Records</span>
            <span className="font-mono font-bold text-primary">
              {rel.evidence_count}
            </span>
          </div>
        </div>

        {/* Source Evidence Section (C7.9) */}
        <div className="space-y-2 pt-2 border-t border-border">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
              Supporting Source Evidence
            </span>
            <span className="text-[10px] text-text-muted font-mono">
              {evidenceList.length} source{evidenceList.length !== 1 ? 's' : ''}
            </span>
          </div>

          {isLoadingEvidence ? (
            <div className="flex items-center justify-center p-6 text-xs text-text-muted gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              <span>Loading verified evidence...</span>
            </div>
          ) : evidenceList.length === 0 ? (
            <div className="p-3 rounded-lg bg-surface-muted/30 border border-border text-center text-xs text-text-muted">
              No evidence snippets stored for this relationship.
            </div>
          ) : (
            <div className="space-y-2.5">
              {evidenceList.map((ev) => {
                const docParams = new URLSearchParams();
                if (ev.chunk_id) docParams.set('chunk_id', ev.chunk_id);
                if (ev.page_start) docParams.set('page', String(ev.page_start));
                if (ev.slide_number) docParams.set('slide', String(ev.slide_number));
                if (ev.section_title) docParams.set('section', ev.section_title);

                const documentHref = ev.document_id
                  ? `/app/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(ev.document_id)}?${docParams.toString()}`
                  : null;

                return (
                  <div
                    key={ev.id}
                    className="p-3 rounded-lg bg-surface-muted/40 border border-border/70 space-y-2 text-xs"
                  >
                    {/* Document Header */}
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 truncate text-text-primary font-medium">
                        <FileText className="h-3.5 w-3.5 text-text-muted shrink-0" />
                        <span className="truncate" title={ev.document_title}>
                          {ev.document_title}
                        </span>
                      </div>
                      <div className="flex items-center gap-1 shrink-0 font-mono text-[9px]">
                        {ev.page_start && (
                          <Badge variant="secondary" className="py-0 px-1">
                            p. {ev.page_start}
                          </Badge>
                        )}
                        {ev.slide_number && (
                          <Badge variant="secondary" className="py-0 px-1">
                            slide {ev.slide_number}
                          </Badge>
                        )}
                      </div>
                    </div>

                    {/* Excerpt with Provenance */}
                    <p className="text-[11px] text-text-secondary italic border-l-2 border-primary/50 pl-2 leading-relaxed">
                      "{ev.evidence_text}"
                    </p>

                    {/* Section title & Confidence */}
                    <div className="flex items-center justify-between text-[10px] text-text-muted pt-1">
                      {ev.section_title ? (
                        <span className="truncate max-w-[160px]">
                          Section: <span className="text-text-secondary">{ev.section_title}</span>
                        </span>
                      ) : (
                        <span />
                      )}
                      <span className="font-mono">
                        Conf: {(ev.confidence * 100).toFixed(0)}%
                      </span>
                    </div>

                    {/* Navigation Link to Document */}
                    {documentHref && (
                      <div className="pt-1 flex justify-end">
                        <Link
                          to={documentHref}
                          className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:text-primary-hover hover:underline transition-colors"
                        >
                          <span>Open in Document</span>
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
