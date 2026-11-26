import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  MoreVertical,
  Trash2,
  RefreshCw,
  ExternalLink,
  Layers,
} from 'lucide-react';
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
import { formatFileSize, getFileIcon, getFileBadgeStyle } from '../lib/documentUtils';
import { formatRelativeTime } from '@/lib/utils';

interface DocumentRowProps {
  document: WorkspaceDocument;
  onDelete: (doc: WorkspaceDocument) => void;
  onRetry: (doc: WorkspaceDocument) => void;
  isRetrying?: boolean;
}

export const DocumentRow: React.FC<DocumentRowProps> = ({
  document,
  onDelete,
  onRetry,
  isRetrying = false,
}) => {
  const navigate = useNavigate();
  const FileIcon = getFileIcon(document.original_filename);
  const badgeStyle = getFileBadgeStyle(document.original_filename);

  const handleOpen = () => {
    navigate(
      `/app/workspaces/${encodeURIComponent(document.workspace_id)}/documents/${encodeURIComponent(document.id)}`
    );
  };

  return (
    <tr className="hover:bg-surface-muted/50 transition-colors text-sm group">
      {/* File name & Icon */}
      <td className="py-3.5 px-4 font-medium text-text-primary">
        <div className="flex items-center gap-3">
          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${badgeStyle.bg} ${badgeStyle.text} border ${badgeStyle.border} shadow-sm transition-colors`}>
            <FileIcon className="h-4 w-4" />
          </div>
          <div className="flex flex-col truncate max-w-[220px] xl:max-w-md">
            <div className="flex items-center gap-2">
              <span
                onClick={handleOpen}
                className="font-semibold text-text-primary group-hover:text-primary transition-colors cursor-pointer truncate"
                title={document.original_filename}
              >
                {document.original_filename}
              </span>
              <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded ${badgeStyle.bg} ${badgeStyle.text} border ${badgeStyle.border} uppercase font-mono`}>
                {badgeStyle.label}
              </span>
            </div>
            <span className="text-[11px] text-text-muted mt-0.5">
              {formatFileSize(document.file_size_bytes)}
            </span>
          </div>
        </div>
      </td>

      {/* Processing Status */}
      <td className="py-3.5 px-4">
        <DocumentStatusBadge status={document.processing_status} />
      </td>

      {/* Chunks & Pages */}
      <td className="py-3.5 px-4 text-text-muted">
        <div className="flex items-center gap-2 font-mono text-[11px]">
          {typeof document.chunk_count === 'number' && document.chunk_count > 0 && (
            <span className="flex items-center gap-1 text-accent font-medium">
              <Layers className="h-3 w-3" />
              {document.chunk_count} {document.chunk_count === 1 ? 'chunk' : 'chunks'}
            </span>
          )}
          {typeof document.page_count === 'number' && (
            <span className="text-text-muted">
              ({document.page_count} {document.page_count === 1 ? 'page' : 'pages'})
            </span>
          )}
          {typeof document.chunk_count !== 'number' && typeof document.page_count !== 'number' && (
            <span className="text-text-muted/50">—</span>
          )}
        </div>
      </td>

      {/* Upload Date */}
      <td className="py-3.5 px-4 text-text-muted">
        {formatRelativeTime(document.created_at)}
      </td>

      {/* Actions */}
      <td className="py-3.5 px-4 text-right">
        <div className="flex items-center justify-end gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleOpen}
            className="h-8 px-2.5 text-xs text-text-secondary hover:text-text-primary hover:bg-surface-muted"
            title="Inspect document details"
          >
            <span>Details</span>
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                className="text-text-muted hover:text-text-primary hover:bg-surface-muted"
                aria-label={`Options for ${document.original_filename}`}
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-36 p-1 bg-surface-elevated border-border shadow-elevation-2">
              <DropdownMenuItem
                onClick={handleOpen}
                className="flex items-center gap-2 text-xs text-text-primary cursor-pointer hover:bg-surface-muted"
              >
                <ExternalLink className="h-3.5 w-3.5 text-primary" />
                <span>View Details</span>
              </DropdownMenuItem>

              {document.processing_status === 'failed' && (
                <DropdownMenuItem
                  onClick={() => onRetry(document)}
                  disabled={isRetrying}
                  className="flex items-center gap-2 text-xs text-warning focus:text-warning cursor-pointer hover:bg-warning/10"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  <span>Retry Job</span>
                </DropdownMenuItem>
              )}

              <DropdownMenuSeparator className="bg-border/60" />
              <DropdownMenuItem
                destructive
                onClick={() => onDelete(document)}
                className="flex items-center gap-2 text-xs text-danger focus:text-danger cursor-pointer hover:bg-danger/10"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Delete</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </td>
    </tr>
  );
};
