import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FolderKanban,
  MoreVertical,
  Pencil,
  Trash2,
  Calendar,
  FileText,
  ArrowRight,
} from 'lucide-react';
import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Workspace } from '../types/workspace';
import { formatRelativeTime } from '@/lib/utils';
import { useWorkspaceContext } from '../context/WorkspaceContext';

interface WorkspaceCardProps {
  workspace: Workspace;
  onRename: (workspace: Workspace) => void;
  onDelete: (workspace: Workspace) => void;
}

export const WorkspaceCard: React.FC<WorkspaceCardProps> = ({
  workspace,
  onRename,
  onDelete,
}) => {
  const navigate = useNavigate();
  const { activeWorkspaceId } = useWorkspaceContext();
  const isActive = activeWorkspaceId === workspace.id;

  const handleOpen = () => {
    navigate(`/app/workspaces/${encodeURIComponent(workspace.id)}`);
  };

  return (
    <Card
      className={`workspace-card group relative flex flex-col justify-between border-border/80 bg-surface/90 hover:bg-surface-elevated/90 hover:border-primary/50 hover:shadow-elevation-1 transition-colors duration-200 overflow-hidden ${
        isActive ? 'ring-1 ring-primary/40 border-primary/50' : ''
      }`}
    >
      {/* Top indicator bar for active workspace */}
      {isActive && (
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-primary" />
      )}

      <CardHeader className="p-5 pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary border border-primary/25 group-hover:border-primary/40 transition-colors duration-200">
              <FolderKanban className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3
                  onClick={handleOpen}
                  role="link"
                  tabIndex={0}
                  onKeyDown={(event) => { if (event.key === 'Enter') handleOpen(); }}
                  className="text-base font-semibold text-text-primary group-hover:text-primary transition-colors cursor-pointer truncate"
                  title={workspace.name}
                >
                  {workspace.name}
                </h3>
                {isActive && (
                  <span className="shrink-0 text-[10px] font-medium px-1.5 py-0.2 rounded bg-primary/20 text-primary border border-primary/30">
                    Active
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5 text-xs text-text-muted mt-0.5">
                <Calendar className="h-3 w-3 shrink-0 text-text-muted/60" />
                <span>Updated {formatRelativeTime(workspace.updated_at)}</span>
              </div>
            </div>
          </div>

          {/* Action Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                className="text-text-muted hover:text-text-primary hover:bg-surface-muted"
                aria-label={`Options for ${workspace.name}`}
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-36 p-1 bg-surface-elevated border-border shadow-elevation-2">
              <DropdownMenuItem
                onClick={() => onRename(workspace)}
                className="flex items-center gap-2 text-xs text-text-primary cursor-pointer hover:bg-surface-muted"
              >
                <Pencil className="h-3.5 w-3.5 text-primary" />
                <span>Rename</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator className="bg-border/60" />
              <DropdownMenuItem
                destructive
                onClick={() => onDelete(workspace)}
                className="flex items-center gap-2 text-xs text-danger focus:text-danger cursor-pointer hover:bg-danger/10"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Delete</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>

      <CardContent className="p-5 pt-0 pb-4 flex-1">
        <p className="text-xs sm:text-sm text-text-secondary line-clamp-2 leading-relaxed min-h-[2.5rem]">
          {workspace.description || 'No description provided.'}
        </p>

        {/* Real document count if returned by API */}
        {typeof workspace.document_count === 'number' && (
          <div className="mt-3 flex items-center gap-1.5 text-xs text-text-muted">
            <Badge variant="outline" className="text-[11px] py-0 px-2 font-normal border-border bg-surface-muted/50">
              <FileText className="h-3 w-3 mr-1 text-accent" />
              {workspace.document_count} {workspace.document_count === 1 ? 'document' : 'documents'}
            </Badge>
          </div>
        )}
      </CardContent>

      <CardFooter className="p-4 px-5 border-t border-border/50 mt-auto flex items-center justify-between bg-surface-muted/20">
        <span className="text-[11px] text-text-muted font-mono truncate max-w-[120px]">
          {workspace.id.slice(0, 8)}...
        </span>
        <Button
          onClick={handleOpen}
          variant="secondary"
          size="sm"
          className="gap-1.5 text-xs h-8 group-hover:bg-primary group-hover:text-primary-foreground group-hover:border-primary transition-all duration-150"
        >
          <span>Open</span>
          <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
        </Button>
      </CardFooter>
    </Card>
  );
};
