import React, { useMemo } from 'react';
import {
  FileText,
  Check,
  AlertTriangle,
  Layers,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useDocuments } from '@/features/documents/hooks/useDocuments';
import { cn } from '@/lib/utils';

interface SourceScopeSelectorProps {
  workspaceId: string;
  selectedDocumentIds: string[];
  onScopeChange: (selectedIds: string[]) => void;
  className?: string;
}

export const SourceScopeSelector: React.FC<SourceScopeSelectorProps> = ({
  workspaceId,
  selectedDocumentIds,
  onScopeChange,
  className,
}) => {
  const { data: documents = [] } = useDocuments(workspaceId);

  // Filter ready documents
  const readyDocuments = useMemo(
    () => documents.filter((d) => d.processing_status === 'ready'),
    [documents]
  );

  const isAllSelected =
    selectedDocumentIds.length === 0 ||
    selectedDocumentIds.length === readyDocuments.length;

  const handleSelectAll = () => {
    onScopeChange([]); // Empty array represents "All Ready Documents"
  };

  const handleToggleDocument = (docId: string) => {
    if (selectedDocumentIds.includes(docId)) {
      const updated = selectedDocumentIds.filter((id) => id !== docId);
      onScopeChange(updated);
    } else {
      onScopeChange([...selectedDocumentIds, docId]);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn(
            'h-8 text-xs gap-2 border-border/80 bg-surface-muted/60 text-text-secondary hover:text-text-primary',
            className
          )}
          title="Filter documents retrieved during research Q&A"
        >
          <Layers className="h-3.5 w-3.5 text-accent" />
          <span className="truncate max-w-[150px]">
            {isAllSelected
              ? `All Ready Sources (${readyDocuments.length})`
              : `${selectedDocumentIds.length} Sources Selected`}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel className="text-[11px] font-semibold text-text-muted uppercase">
          Retrieval Scope
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        {readyDocuments.length === 0 ? (
          <div className="p-3 text-center space-y-1">
            <div className="flex items-center justify-center text-warning mb-1">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <p className="text-xs font-semibold text-text-primary">
              No Ready Documents
            </p>
            <p className="text-[11px] text-text-muted leading-tight">
              Upload documents in this workspace first. Only ready documents can be queried.
            </p>
          </div>
        ) : (
          <div className="max-h-60 overflow-y-auto space-y-1">
            {/* All Sources Option */}
            <DropdownMenuItem
              onClick={handleSelectAll}
              className={cn(
                'flex items-center justify-between text-xs cursor-pointer',
                isAllSelected && 'bg-primary/10 text-primary font-semibold'
              )}
            >
              <span>All Ready Documents ({readyDocuments.length})</span>
              {isAllSelected && <Check className="h-3.5 w-3.5 text-primary" />}
            </DropdownMenuItem>

            <DropdownMenuSeparator />

            {/* Individual Document Toggles */}
            {readyDocuments.map((doc) => {
              const isChecked = selectedDocumentIds.includes(doc.id);
              return (
                <DropdownMenuItem
                  key={doc.id}
                  onClick={(e) => {
                    e.preventDefault();
                    handleToggleDocument(doc.id);
                  }}
                  className="flex items-center justify-between text-xs cursor-pointer gap-2"
                >
                  <div className="flex items-center gap-2 truncate">
                    <FileText className="h-3.5 w-3.5 shrink-0 text-primary" />
                    <span className="truncate" title={doc.original_filename}>
                      {doc.original_filename}
                    </span>
                  </div>
                  {isChecked && <Check className="h-3.5 w-3.5 text-primary shrink-0" />}
                </DropdownMenuItem>
              );
            })}
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
