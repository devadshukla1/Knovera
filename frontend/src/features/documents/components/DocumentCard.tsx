import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  MoreVertical,
  Trash2,
  RefreshCw,
  Layers,
  Calendar,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { WorkspaceDocument } from '../types/document';
import { DocumentStatusBadge } from './DocumentStatusBadge';
import { formatFileSize, getFileIcon } from '../lib/documentUtils';
import { formatRelativeTime } from '@/lib/utils';

interface DocumentCardProps {
  document: WorkspaceDocument;
  onDelete: (doc: WorkspaceDocument) => void;
  onRetry: (doc: WorkspaceDocument) => void;
  isRetrying?: boolean;
}

export const DocumentCard: React.FC<DocumentCardProps> = ({
  document,
  onDelete,
  onRetry,
  isRetrying = false,
}) => {
  const navigate = useNavigate();
  const FileIcon = getFileIcon(document.original_filename);

  const handleOpen = () => {
    navigate(
      `/app/workspaces/${encodeURIComponent(document.workspace_id)}/documents/${encodeURIComponent(document.id)}`
    );
  };

  return (
    <Card className="border-border hover:border-primary/40 transition-all p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-muted text-primary border border-border">
            <FileIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h4
              onClick={handleOpen}
              className="text-sm font-semibold text-text-primary hover:text-primary transition-colors cursor-pointer truncate"
              title={document.original_filename}
            >
              {document.original_filename}
            </h4>
            <p className="text-xs text-text-muted mt-0.5">
              {formatFileSize(document.file_size_bytes)}
            </p>
          </div>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-text-muted hover:text-text-primary"
              aria-label={`Options for ${document.original_filename}`}
            >
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-36">
            <DropdownMenuItem onClick={handleOpen} className="text-xs">
              <span>View Details</span>
            </DropdownMenuItem>

            {document.processing_status === 'failed' && (
              <DropdownMenuItem
                onClick={() => onRetry(document)}
                disabled={isRetrying}
                className="text-xs text-warning"
              >
                <RefreshCw className="mr-2 h-3.5 w-3.5" />
                <span>Retry Job</span>
              </DropdownMenuItem>
            )}

            <DropdownMenuSeparator />
            <DropdownMenuItem
              destructive
              onClick={() => onDelete(document)}
              className="text-xs text-danger"
            >
              <Trash2 className="mr-2 h-3.5 w-3.5" />
              <span>Delete</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="flex items-center justify-between pt-1 text-xs text-text-muted">
        <DocumentStatusBadge status={document.processing_status} />
        {typeof document.page_count === 'number' && (
          <span className="flex items-center gap-1 font-mono">
            <Layers className="h-3 w-3" />
            {document.page_count} pages
          </span>
        )}
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-border/50 text-[11px] text-text-muted">
        <span className="flex items-center gap-1">
          <Calendar className="h-3 w-3" />
          {formatRelativeTime(document.created_at)}
        </span>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleOpen}
          className="h-7 px-2.5 text-xs"
        >
          Open
        </Button>
      </div>
    </Card>
  );
};
