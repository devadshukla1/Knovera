import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  X,
  FileText,
  Layers,
  HelpCircle,
  BookOpen,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { analyticsApi } from '../api/analyticsApi';

interface ConceptResourcesModalProps {
  workspaceId: string;
  conceptId: string | null;
  conceptName?: string | null;
  onClose: () => void;
}

export const ConceptResourcesModal: React.FC<ConceptResourcesModalProps> = ({
  workspaceId,
  conceptId,
  conceptName,
  onClose,
}) => {
  const { data: resources, isLoading } = useQuery({
    queryKey: ['concept-resources', workspaceId, conceptId],
    queryFn: () => analyticsApi.getConceptRevisionResources(workspaceId, conceptId!),
    enabled: Boolean(workspaceId && conceptId),
  });

  if (!conceptId) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto"
      onClick={onClose}
      aria-modal="true"
      role="dialog"
    >
      <div
        className="w-full max-w-2xl rounded-xl border border-border bg-surface p-6 shadow-2xl space-y-5 my-8 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-border pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                Revision Resources
              </span>
              <Badge variant="outline" className="text-[11px] font-mono">
                Canonical Concept
              </Badge>
            </div>
            <h2 className="text-xl font-bold text-text-primary mt-1">
              {conceptName || resources?.concept_name || 'Concept Materials'}
            </h2>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-8 w-8 text-text-muted hover:text-text-primary"
            aria-label="Close dialog"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {isLoading ? (
          <div className="py-12 flex flex-col items-center justify-center text-text-muted space-y-2">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <span className="text-sm">Resolving linked learning materials...</span>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Revision Notes */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5 text-accent" />
                Structured Revision Notes ({resources?.revision_notes.length || 0})
              </h3>
              {resources?.revision_notes.length ? (
                <div className="space-y-2">
                  {resources.revision_notes.map((note) => (
                    <div
                      key={note.resource_id}
                      className="p-3 rounded-lg border border-border bg-surface-muted/50 space-y-1 hover:border-accent/40 transition-colors"
                    >
                      <h4 className="text-sm font-semibold text-text-primary">
                        {note.title}
                      </h4>
                      {note.preview && (
                        <p className="text-xs text-text-muted line-clamp-2">
                          {note.preview}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-text-muted italic">
                  No revision notes specifically mapped to this concept.
                </p>
              )}
            </div>

            {/* Flashcards */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-primary" />
                Active Recall Flashcards ({resources?.flashcards.length || 0})
              </h3>
              {resources?.flashcards.length ? (
                <div className="space-y-2">
                  {resources.flashcards.map((fc) => (
                    <div
                      key={fc.resource_id}
                      className="p-3 rounded-lg border border-border bg-surface-muted/50 space-y-1 hover:border-primary/40 transition-colors"
                    >
                      <span className="text-[11px] font-medium text-primary">Prompt</span>
                      <p className="text-xs font-semibold text-text-primary">{fc.title}</p>
                      {fc.preview && (
                        <p className="text-xs text-text-muted mt-1 border-t border-border/40 pt-1">
                          <span className="text-[10px] text-text-muted uppercase">Answer: </span>
                          {fc.preview}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-text-muted italic">
                  No flashcards found matching this concept.
                </p>
              )}
            </div>

            {/* Practice Questions */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted flex items-center gap-1.5">
                <HelpCircle className="h-3.5 w-3.5 text-secondary" />
                Practice Questions ({resources?.practice_questions.length || 0})
              </h3>
              {resources?.practice_questions.length ? (
                <div className="space-y-2">
                  {resources.practice_questions.map((q) => (
                    <div
                      key={q.resource_id}
                      className="p-3 rounded-lg border border-border bg-surface-muted/50 space-y-1"
                    >
                      <span className="text-xs font-medium text-text-primary">
                        {q.title}
                      </span>
                      {q.preview && (
                        <p className="text-xs text-text-muted line-clamp-2">
                          {q.preview}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-text-muted italic">
                  No validated practice questions linked yet.
                </p>
              )}
            </div>

            {/* Source Document Chunks */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted flex items-center gap-1.5">
                <BookOpen className="h-3.5 w-3.5 text-text-secondary" />
                Grounded Source Material ({resources?.source_documents.length || 0})
              </h3>
              {resources?.source_documents.length ? (
                <div className="space-y-2">
                  {resources.source_documents.map((doc) => (
                    <div
                      key={doc.resource_id}
                      className="p-3 rounded-lg border border-border bg-surface-muted/50 space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-text-primary">
                          {doc.title}
                        </span>
                        {doc.page_number && (
                          <Badge variant="outline" className="text-[10px]">
                            Page {doc.page_number}
                          </Badge>
                        )}
                      </div>
                      {doc.preview && (
                        <p className="text-xs text-text-muted line-clamp-2 font-mono text-[11px]">
                          "{doc.preview}"
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-text-muted italic">
                  No direct document chunks identified for this concept.
                </p>
              )}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex justify-end pt-3 border-t border-border">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
