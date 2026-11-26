import React from 'react';
import { Link } from 'react-router-dom';
import {
  X,
  FileText,
  ExternalLink,
  ShieldCheck,
  Layers,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Citation } from '../types/chat';

interface CitationInspectorProps {
  citation: Citation | null;
  workspaceId: string;
  onClose: () => void;
}

export const CitationInspector: React.FC<CitationInspectorProps> = ({
  citation,
  workspaceId,
  onClose,
}) => {
  if (!citation) return null;

  return (
    <div className="flex flex-col h-full border-l border-border bg-surface p-4 overflow-y-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/80 pb-3">
        <div className="flex items-center gap-2">
          <Badge variant="default" className="font-mono text-xs font-semibold px-2">
            [{citation.citation_number}]
          </Badge>
          <span className="text-xs font-semibold text-text-primary">
            Source Grounding
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="h-7 w-7 text-text-muted hover:text-text-primary"
          aria-label="Close citation details"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Document Reference Info */}
      <div className="space-y-3">
        <div className="flex items-start gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-muted text-primary border border-border">
            <FileText className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h4
              className="text-xs font-semibold text-text-primary leading-tight truncate"
              title={citation.document_title}
            >
              {citation.document_title}
            </h4>
            <div className="flex items-center gap-2 text-[11px] text-text-muted mt-1">
              {citation.page_number !== null && (
                <span className="flex items-center gap-1 font-mono text-accent">
                  <Layers className="h-3 w-3" />
                  Page {citation.page_number}
                </span>
              )}
              {typeof citation.confidence_score === 'number' && (
                <span className="flex items-center gap-1 font-mono text-success">
                  <ShieldCheck className="h-3 w-3" />
                  {(citation.confidence_score * 100).toFixed(0)}% Match
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Verbatim Evidence Box */}
        <div className="space-y-1.5">
          <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
            Verified Source Passage
          </span>
          <div className="rounded-xl border border-primary/20 bg-primary/5 p-3.5 text-xs text-text-primary leading-relaxed font-sans italic relative">
            <span className="text-primary text-base font-serif mr-1">“</span>
            {citation.snippet}
            <span className="text-primary text-base font-serif ml-1">”</span>
          </div>
        </div>

        {/* Action Link to Full Document */}
        <div className="pt-2">
          <Link
            to={`/app/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(citation.document_id)}`}
          >
            <Button variant="secondary" size="sm" className="w-full text-xs gap-1.5">
              <span>View Source Document</span>
              <ExternalLink className="h-3 w-3" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
};
