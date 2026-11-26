/**
 * MindMapNodeDetails side panel for Knovera Knowledge Mind Map.
 *
 * Displays rich concept metadata, document grounding, difficulty,
 * Bayesian Knowledge Tracing learning status, and quick study/chat actions.
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X,
  MessageSquare,
  GraduationCap,
  FileText,
  CheckCircle2,
  Clock,
  AlertCircle,
  HelpCircle,
  ExternalLink,
  BookOpen,
  ArrowRight,
  Layers,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  MindMapNodeItem,
  LearningStatusType,
} from '../types/knowledgeGraph';
import { useUpdateMindMapNodeStatus } from '../hooks/useKnowledgeGraph';

interface MindMapNodeDetailsProps {
  node: MindMapNodeItem | null;
  workspaceId: string;
  onClose: () => void;
  onNodeStatusChanged?: (nodeId: string, status: string) => void;
}

export const MindMapNodeDetails: React.FC<MindMapNodeDetailsProps> = ({
  node,
  workspaceId,
  onClose,
  onNodeStatusChanged,
}) => {
  const navigate = useNavigate();
  const updateStatusMutation = useUpdateMindMapNodeStatus(workspaceId);

  if (!node) return null;

  const handleStatusChange = async (newStatus: LearningStatusType) => {
    try {
      await updateStatusMutation.mutateAsync({
        nodeId: node.id,
        status: newStatus,
      });
      if (onNodeStatusChanged) {
        onNodeStatusChanged(node.id, newStatus);
      }
    } catch (err) {
      console.error('Failed to update node status:', err);
    }
  };

  const handleOpenInChat = () => {
    const prompt = encodeURIComponent(`Can you explain "${node.label}" in detail, including its key concepts and practical applications?`);
    navigate(`/app/workspaces/${workspaceId}/chat?initialQuery=${prompt}`);
  };

  const handleStartQuiz = () => {
    navigate(`/app/workspaces/${workspaceId}/study-studio`);
  };

  const handleViewDocuments = () => {
    navigate(`/app/workspaces/${workspaceId}/documents`);
  };

  const getLevelLabel = () => {
    switch (node.level) {
      case 0:
        return 'Central Subject';
      case 1:
        return 'Primary Topic Area';
      case 2:
        return 'Secondary Concept';
      case 3:
        return 'Grounded Fact / Detail';
      default:
        return 'Concept';
    }
  };

  const statusOptions: Array<{ id: LearningStatusType; label: string; icon: React.ReactNode; color: string }> = [
    {
      id: 'not_started',
      label: 'Not Started',
      icon: <HelpCircle className="w-3.5 h-3.5 text-text-muted" />,
      color: 'hover:border-slate-500',
    },
    {
      id: 'in_progress',
      label: 'In Progress',
      icon: <Clock className="w-3.5 h-3.5 text-amber-400" />,
      color: 'hover:border-amber-500',
    },
    {
      id: 'needs_revision',
      label: 'Needs Revision',
      icon: <AlertCircle className="w-3.5 h-3.5 text-rose-400" />,
      color: 'hover:border-rose-500',
    },
    {
      id: 'learned',
      label: 'Mastered',
      icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />,
      color: 'hover:border-emerald-500',
    },
  ];

  return (
    <div className="graph-details w-96 shrink-0 h-full flex flex-col bg-surface/95 backdrop-blur-xl border-l border-border shadow-2xl z-40 overflow-hidden text-text-primary animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between gap-2 bg-slate-950/40">
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 border-border bg-surface-muted/80 text-primary"
          >
            {getLevelLabel()}
          </Badge>
          {node.category && (
            <span className="text-xs text-text-muted truncate max-w-[160px]">
              {node.category}
            </span>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-text-muted hover:text-text-primary hover:bg-surface-muted rounded-lg"
          onClick={onClose}
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Body Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {/* Title */}
        <div>
          <h2 className="text-lg font-bold text-text-primary tracking-tight leading-snug">
            {node.label}
          </h2>
          {node.difficulty && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[11px] font-medium text-text-muted">Difficulty:</span>
              <span className="text-[11px] font-semibold text-emerald-400 capitalize bg-emerald-950/60 border border-emerald-900 px-2 py-0.5 rounded">
                {node.difficulty}
              </span>
              {node.importance && (
                <span className="text-[11px] font-medium text-indigo-400 capitalize bg-indigo-950/60 border border-indigo-900 px-2 py-0.5 rounded">
                  {node.importance}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Learning Status Selector */}
        <div className="bg-slate-950/60 border border-border/90 rounded-xl p-3.5 space-y-2.5">
          <label className="text-xs font-semibold text-text-secondary flex items-center gap-1.5">
            <GraduationCap className="w-4 h-4 text-primary" />
            Learning Roadmap Status
          </label>
          <div className="grid grid-cols-2 gap-2">
            {statusOptions.map((opt) => {
              const isActive = (node.learning_status || 'not_started') === opt.id;
              return (
                <button
                  key={opt.id}
                  type="button"
                  className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-surface-muted border-primary text-text-primary shadow-sm ring-1 ring-primary/30'
                      : `bg-surface/60 border-border text-text-muted ${opt.color} hover:text-text-primary`
                  }`}
                  onClick={() => handleStatusChange(opt.id)}
                  disabled={updateStatusMutation.isPending}
                >
                  {opt.icon}
                  <span>{opt.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Explanation / Summary */}
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5 text-text-muted" />
            Overview & Summary
          </h3>
          <div className="text-sm text-text-secondary leading-relaxed bg-slate-950/40 border border-border/60 rounded-xl p-3.5">
            {node.summary || node.description || 'No direct summary available.'}
          </div>
        </div>

        {/* Document Grounding Excerpt */}
        {node.source_excerpt && (
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-emerald-400" />
              Source Grounding Excerpt
            </h3>
            <div className="text-xs text-text-secondary italic bg-emerald-950/20 border border-emerald-900/50 rounded-xl p-3.5 leading-relaxed">
              &ldquo;{node.source_excerpt}&rdquo;
            </div>
          </div>
        )}

        {/* Prerequisites */}
        {node.prerequisites && node.prerequisites.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-text-muted" />
              Prerequisites
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {node.prerequisites.map((p, idx) => (
                <span
                  key={idx}
                  className="text-xs font-medium text-text-secondary bg-surface-muted/90 border border-border/80 px-2.5 py-1 rounded-md"
                >
                  {p}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Source Documents & Page Provenance */}
        {((node.source_references && node.source_references.length > 0) ||
          (node.source_documents && node.source_documents.length > 0)) && (
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-text-muted" />
                Source Provenance
              </h3>
              {node.is_shared_across_documents && (
                <span className="text-[10px] font-medium text-sky-400 bg-sky-950/60 border border-sky-800/60 px-2 py-0.5 rounded-full">
                  Merged Multi-Doc
                </span>
              )}
            </div>
            {node.has_conflicting_info && (
              <div className="text-[11px] text-amber-300 bg-amber-950/40 border border-amber-800/60 rounded-lg p-2">
                Sources present differing or conflicting claims on this concept. Review individual excerpts below.
              </div>
            )}
            <div className="space-y-1.5">
              {node.source_references && node.source_references.length > 0
                ? node.source_references.map((ref, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between gap-2 text-xs text-text-secondary bg-slate-950/50 border border-border/80 rounded-lg p-2"
                    >
                      <span className="flex items-center gap-2 truncate">
                        <FileText className="w-3.5 h-3.5 text-primary shrink-0" />
                        <span className="truncate">{ref.document_title}</span>
                      </span>
                      {ref.page_number !== null && ref.page_number !== undefined && (
                        <span className="text-[10px] font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded shrink-0">
                          p. {ref.page_number}
                        </span>
                      )}
                    </div>
                  ))
                : node.source_documents?.map((doc, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-2 text-xs text-text-secondary bg-slate-950/50 border border-border/80 rounded-lg p-2"
                    >
                      <FileText className="w-3.5 h-3.5 text-primary shrink-0" />
                      <span className="truncate">{doc}</span>
                    </div>
                  ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer Quick Actions */}
      <div className="p-4 border-t border-border bg-slate-950/60 space-y-2">
        <Button
          variant="default"
          className="w-full justify-between bg-sky-600 hover:bg-sky-500 text-text-primary font-medium shadow-md shadow-sky-600/20"
          onClick={handleOpenInChat}
        >
          <span className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            Research Chat on Concept
          </span>
          <ArrowRight className="w-4 h-4" />
        </Button>

        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="outline"
            size="sm"
            className="border-border bg-surface hover:bg-surface-muted text-text-primary text-xs"
            onClick={handleStartQuiz}
          >
            <GraduationCap className="w-3.5 h-3.5 mr-1.5 text-emerald-400" />
            Start Quiz
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="border-border bg-surface hover:bg-surface-muted text-text-primary text-xs"
            onClick={handleViewDocuments}
          >
            <ExternalLink className="w-3.5 h-3.5 mr-1.5 text-primary" />
            View Documents
          </Button>
        </div>
      </div>
    </div>
  );
};
