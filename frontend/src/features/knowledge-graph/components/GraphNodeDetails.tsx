/**
 * Node details drawer with connected relations and source mentions (Phase 7 C7.8, C7.9).
 * Features direct navigation to source documents with page, slide, section, and chunk location parameters.
 */

import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  X,
  FileText,
  ExternalLink,
  GitFork,
  ArrowRight,
  Route,
  Loader2,
  GraduationCap,
  MessageSquare,
  BookOpen,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  useKnowledgeGraphNodeDetails,
  useKnowledgeGraphNodeEvidence,
  useKnowledgeGraphRelationships,
  useUpdateNodeStatus,
} from '../hooks/useKnowledgeGraph';
import { cn } from '@/lib/utils';

export interface GraphNodeDetailsProps {
  workspaceId: string;
  nodeId: string;
  snapshotId?: string;
  onClose: () => void;
  onSelectNode: (nodeId: string) => void;
  onExpandNeighbors: () => void;
  onStartPath: (nodeId: string) => void;
  className?: string;
}

export const GraphNodeDetails: React.FC<GraphNodeDetailsProps> = ({
  workspaceId,
  nodeId,
  snapshotId,
  onClose,
  onSelectNode,
  onExpandNeighbors,
  onStartPath,
  className,
}) => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'details' | 'evidence'>('details');

  // Mutation for updating learning roadmap status
  const updateStatusMutation = useUpdateNodeStatus(workspaceId);

  // Fetch node metadata & counts
  const { data: node, isLoading: isLoadingNode } = useKnowledgeGraphNodeDetails(
    workspaceId,
    nodeId,
    snapshotId
  );

  // Fetch connected relationships
  const { data: relsData, isLoading: isLoadingRels } = useKnowledgeGraphRelationships(
    workspaceId,
    {
      sourceNodeId: nodeId,
      snapshotId,
      pageSize: 30,
    },
    Boolean(nodeId && activeTab === 'details')
  );

  const relationships = relsData?.items || [];

  // Fetch source document mentions
  const { data: evidenceData, isLoading: isLoadingEvidence } = useKnowledgeGraphNodeEvidence(
    workspaceId,
    nodeId,
    1,
    20
  );

  const mentions = evidenceData?.items || [];

  if (isLoadingNode) {
    return (
      <div className={cn('w-80 md:w-96 bg-surface border-l border-border p-6 flex flex-col items-center justify-center', className)}>
        <Loader2 className="h-6 w-6 animate-spin text-primary mb-2" />
        <span className="text-xs text-text-muted">Loading node details...</span>
      </div>
    );
  }

  if (!node) {
    return (
      <div className={cn('w-80 md:w-96 bg-surface border-l border-border p-6', className)}>
        <div className="flex justify-between items-center mb-4">
          <span className="text-sm font-semibold text-text-primary">Node Details</span>
          <Button variant="ghost" size="icon" onClick={onClose} className="h-7 w-7">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <p className="text-xs text-text-muted">Node could not be found in active snapshot.</p>
      </div>
    );
  }

  const isConcept = node.node_kind === 'concept';

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
            <span
              className={cn(
                'w-2.5 h-2.5 rounded-full shrink-0',
                isConcept ? 'bg-violet-400' : 'bg-teal-400'
              )}
            />
            <Badge
              variant="outline"
              className={cn(
                'text-[10px] py-0 px-1.5 uppercase font-mono font-medium',
                isConcept ? 'border-violet-500/30 text-violet-400' : 'border-teal-500/30 text-teal-400'
              )}
            >
              {node.node_kind}
            </Badge>
            {node.node_type && (
              <Badge variant="secondary" className="text-[10px] py-0 px-1.5 font-normal">
                {node.node_type}
              </Badge>
            )}
          </div>
          <h3 className="text-sm font-bold text-text-primary truncate" title={node.label}>
            {node.label}
          </h3>
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

      {/* Tabs */}
      <div className="flex border-b border-border bg-surface-muted/20 text-xs">
        <button
          type="button"
          onClick={() => setActiveTab('details')}
          className={cn(
            'flex-1 py-2 font-medium text-center border-b-2 transition-colors',
            activeTab === 'details'
              ? 'border-primary text-primary font-semibold'
              : 'border-transparent text-text-muted hover:text-text-primary'
          )}
        >
          Overview & Links ({node.degree})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('evidence')}
          className={cn(
            'flex-1 py-2 font-medium text-center border-b-2 transition-colors',
            activeTab === 'evidence'
              ? 'border-primary text-primary font-semibold'
              : 'border-transparent text-text-muted hover:text-text-primary'
          )}
        >
          Source Mentions ({node.mention_count})
        </button>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeTab === 'details' ? (
          <>
            {/* Description */}
            {node.description ? (
              <div className="space-y-1">
                <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
                  Description
                </span>
                <p className="text-xs text-text-secondary leading-relaxed bg-surface-muted/40 p-2.5 rounded-lg border border-border/60">
                  {node.description}
                </p>
              </div>
            ) : null}

            {/* Aliases / Surface Forms */}
            {node.aliases && node.aliases.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
                  Surface Forms / Aliases
                </span>
                <div className="flex flex-wrap gap-1">
                  {node.aliases.map((alias, i) => (
                    <Badge
                      key={i}
                      variant="secondary"
                      className="text-[10px] py-0 px-1.5 text-text-secondary bg-surface-muted"
                    >
                      {alias}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Degree Statistics */}
            <div className="grid grid-cols-3 gap-2 bg-surface-muted/30 p-2.5 rounded-lg border border-border/60 text-center">
              <div>
                <span className="text-[10px] text-text-muted block">In-Degree</span>
                <span className="text-xs font-bold text-text-primary">{node.in_degree}</span>
              </div>
              <div>
                <span className="text-[10px] text-text-muted block">Out-Degree</span>
                <span className="text-xs font-bold text-text-primary">{node.out_degree}</span>
              </div>
              <div>
                <span className="text-[10px] text-text-muted block">Total Conns</span>
                <span className="text-xs font-bold text-primary">{node.degree}</span>
              </div>
            </div>

            {/* Learning Roadmap Status */}
            <div className="space-y-2 p-3 rounded-xl border border-border/80 bg-surface-muted/20">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider flex items-center gap-1.5">
                  <GraduationCap className="h-3.5 w-3.5 text-primary" />
                  Roadmap Mastery Status
                </span>
                {updateStatusMutation.isPending && (
                  <Loader2 className="h-3 w-3 animate-spin text-primary" />
                )}
              </div>

              <div className="grid grid-cols-2 gap-1.5">
                <button
                  type="button"
                  onClick={() => updateStatusMutation.mutate({ nodeId: node.id, status: 'not_started' })}
                  className={cn(
                    'text-left px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all',
                    (node.learning_status || 'not_started') === 'not_started'
                      ? 'bg-surface-elevated border-border text-text-primary shadow-sm font-semibold'
                      : 'border-transparent text-text-muted hover:text-text-primary hover:bg-surface-muted'
                  )}
                >
                  ⚪ Not Started
                </button>
                <button
                  type="button"
                  onClick={() => updateStatusMutation.mutate({ nodeId: node.id, status: 'in_progress' })}
                  className={cn(
                    'text-left px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all',
                    node.learning_status === 'in_progress'
                      ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300 shadow-sm font-semibold'
                      : 'border-transparent text-text-muted hover:text-text-primary hover:bg-surface-muted'
                  )}
                >
                  🔵 In Progress
                </button>
                <button
                  type="button"
                  onClick={() => updateStatusMutation.mutate({ nodeId: node.id, status: 'learned' })}
                  className={cn(
                    'text-left px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all',
                    node.learning_status === 'learned'
                      ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300 shadow-sm font-semibold'
                      : 'border-transparent text-text-muted hover:text-text-primary hover:bg-surface-muted'
                  )}
                >
                  🟢 Learned
                </button>
                <button
                  type="button"
                  onClick={() => updateStatusMutation.mutate({ nodeId: node.id, status: 'needs_revision' })}
                  className={cn(
                    'text-left px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all',
                    node.learning_status === 'needs_revision'
                      ? 'bg-amber-500/15 border-amber-500/40 text-amber-300 shadow-sm font-semibold'
                      : 'border-transparent text-text-muted hover:text-text-primary hover:bg-surface-muted'
                  )}
                >
                  🟡 Needs Revision
                </button>
              </div>
            </div>

            {/* Functional Study & Research Actions */}
            <div className="space-y-1.5">
              <Button
                size="sm"
                onClick={() => navigate(`/app/workspaces/${encodeURIComponent(workspaceId)}/chat`)}
                className="w-full text-xs gap-2 h-8 rounded-xl justify-center bg-primary hover:bg-primary-hover text-white shadow-sm"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                <span>Open in Research Chat</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate(`/app/workspaces/${encodeURIComponent(workspaceId)}/study-studio`)}
                className="w-full text-xs gap-2 h-8 rounded-xl justify-center border-border hover:bg-surface-muted text-text-secondary hover:text-text-primary"
              >
                <BookOpen className="h-3.5 w-3.5 text-accent-purple" />
                <span>Start a Related Quiz</span>
              </Button>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={onExpandNeighbors}
                className="flex-1 text-xs gap-1.5 border-border hover:bg-surface-muted"
              >
                <GitFork className="h-3.5 w-3.5 text-primary" />
                <span>Expand Neighbors</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onStartPath(node.id)}
                className="flex-1 text-xs gap-1.5 border-border hover:bg-surface-muted"
              >
                <Route className="h-3.5 w-3.5 text-accent" />
                <span>Find Path</span>
              </Button>
            </div>

            {/* Connected Relationships */}
            <div className="space-y-2 pt-2 border-t border-border">
              <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider block">
                Connected Relationships ({relationships.length})
              </span>

              {isLoadingRels ? (
                <div className="flex items-center justify-center p-4 text-xs text-text-muted gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                  <span>Loading connections...</span>
                </div>
              ) : relationships.length === 0 ? (
                <p className="text-xs text-text-muted italic">No relationships recorded for this node.</p>
              ) : (
                <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                  {relationships.map((rel) => {
                    const isOutgoing = rel.source === node.id;
                    const neighborId = isOutgoing ? rel.target : rel.source;
                    const neighborLabel = isOutgoing
                      ? rel.target_label || rel.target
                      : rel.source_label || rel.source;

                    return (
                      <div
                        key={rel.id}
                        className="p-2 rounded-lg bg-surface-muted/50 border border-border/50 text-xs hover:border-primary/40 transition-colors flex items-center justify-between gap-2"
                      >
                        <div className="flex items-center gap-1.5 truncate">
                          <ArrowRight className="h-3 w-3 text-emerald-400 shrink-0" />
                          <Badge variant="outline" className="text-[9px] py-0 px-1 font-mono shrink-0">
                            {rel.predicate}
                          </Badge>
                          <button
                            type="button"
                            onClick={() => onSelectNode(neighborId)}
                            className="text-text-primary hover:text-primary font-medium truncate text-left"
                            title={`Jump to ${neighborLabel}`}
                          >
                            {neighborLabel}
                          </button>
                        </div>

                        <span className="text-[10px] text-text-muted shrink-0 font-mono">
                          {(rel.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        ) : (
          /* Evidence Mentions Tab */
          <div className="space-y-3">
            {isLoadingEvidence ? (
              <div className="flex items-center justify-center p-6 text-xs text-text-muted gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <span>Loading source mentions...</span>
              </div>
            ) : mentions.length === 0 ? (
              <div className="p-4 text-center text-xs text-text-muted bg-surface-muted/30 rounded-lg border border-border">
                No verified source mentions found for this node.
              </div>
            ) : (
              <div className="space-y-2.5">
                <span className="text-[11px] text-text-muted font-medium">
                  Found in {mentions.length} document mention{mentions.length > 1 ? 's' : ''}:
                </span>

                {mentions.map((mention, idx) => {
                  const docParams = new URLSearchParams();
                  if (mention.chunk_id) docParams.set('chunk_id', mention.chunk_id);
                  if (mention.page_start) docParams.set('page', String(mention.page_start));
                  if (mention.slide_number) docParams.set('slide', String(mention.slide_number));
                  if (mention.section_title) docParams.set('section', mention.section_title);

                  const documentHref = mention.document_id
                    ? `/app/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(mention.document_id)}?${docParams.toString()}`
                    : null;

                  return (
                    <div
                      key={idx}
                      className="p-3 rounded-lg bg-surface-muted/40 border border-border/70 space-y-2 text-xs"
                    >
                      {/* Document Title & Badge */}
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 truncate text-text-primary font-medium">
                          <FileText className="h-3.5 w-3.5 text-text-muted shrink-0" />
                          <span className="truncate" title={mention.document_title}>
                            {mention.document_title}
                          </span>
                        </div>
                        {mention.page_start && (
                          <Badge variant="secondary" className="text-[9px] py-0 px-1 shrink-0 font-mono">
                            Page {mention.page_start}
                          </Badge>
                        )}
                        {mention.slide_number && (
                          <Badge variant="secondary" className="text-[9px] py-0 px-1 shrink-0 font-mono">
                            Slide {mention.slide_number}
                          </Badge>
                        )}
                      </div>

                      {/* Excerpt */}
                      {mention.excerpt ? (
                        <p className="text-[11px] text-text-secondary italic border-l-2 border-primary/40 pl-2 leading-relaxed">
                          "{mention.excerpt}"
                        </p>
                      ) : null}

                      {/* Section Title */}
                      {mention.section_title && (
                        <div className="text-[10px] text-text-muted truncate">
                          Section: <span className="text-text-secondary">{mention.section_title}</span>
                        </div>
                      )}

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
        )}
      </div>
    </div>
  );
};
