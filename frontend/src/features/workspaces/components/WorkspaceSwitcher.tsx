import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FolderKanban,
  Check,
  ChevronsUpDown,
  Plus,
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
import { useWorkspaceContext } from '../context/WorkspaceContext';
import { WorkspaceFormModal } from './WorkspaceFormModal';
import { useCreateWorkspace } from '../hooks/useWorkspaces';
import { WorkspaceFormValues } from '../schemas/workspaceSchema';
import { cn } from '@/lib/utils';

interface WorkspaceSwitcherProps {
  collapsed?: boolean;
  className?: string;
}

export const WorkspaceSwitcher: React.FC<WorkspaceSwitcherProps> = ({
  collapsed = false,
  className,
}) => {
  const { activeWorkspaceId, activeWorkspace, workspaces, setActiveWorkspaceId } =
    useWorkspaceContext();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const createMutation = useCreateWorkspace();
  const navigate = useNavigate();

  const handleCreateSubmit = async (values: WorkspaceFormValues) => {
    try {
      setFormError(null);
      const created = await createMutation.mutateAsync({
        name: values.name,
        description: values.description || null,
      });
      setIsCreateOpen(false);
      navigate(`/app/workspaces/${encodeURIComponent(created.id)}`);
    } catch (err: unknown) {
      setFormError(
        err instanceof Error ? err.message : 'Failed to create workspace.'
      );
    }
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="default"
            className={cn(
              'w-full justify-between border-border/80 bg-surface-muted/60 hover:bg-surface-elevated text-xs font-medium text-text-primary px-3 h-10',
              collapsed && 'h-9 w-9 p-0 justify-center',
              className
            )}
            title={
              activeWorkspace
                ? `Active Workspace: ${activeWorkspace.name}`
                : 'Select Workspace'
            }
            aria-label="Workspace switcher"
          >
            <div className="flex items-center gap-2.5 truncate">
              <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-primary/20 text-primary">
                <FolderKanban className="h-3.5 w-3.5" />
              </div>
              {!collapsed && (
                <div className="flex flex-col text-left truncate">
                  <span className="text-[10px] text-text-muted font-normal leading-none mb-0.5">
                    Workspace
                  </span>
                  <span className="font-semibold text-text-primary truncate max-w-[130px]">
                    {activeWorkspace ? activeWorkspace.name : 'Select Workspace'}
                  </span>
                </div>
              )}
            </div>
            {!collapsed && (
              <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-text-muted" />
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-60">
          <DropdownMenuLabel className="text-[11px] font-semibold uppercase text-text-muted">
            Personal Workspaces
          </DropdownMenuLabel>
          <DropdownMenuSeparator />

          {workspaces.length === 0 ? (
            <div className="px-2 py-3 text-center text-xs text-text-muted">
              No workspaces created yet.
            </div>
          ) : (
            <div className="max-h-56 overflow-y-auto space-y-0.5">
              {workspaces.map((ws) => {
                const isSelected = ws.id === activeWorkspaceId;
                return (
                  <DropdownMenuItem
                    key={ws.id}
                    onClick={() => setActiveWorkspaceId(ws.id)}
                    className={cn(
                      'flex items-center justify-between text-xs cursor-pointer',
                      isSelected && 'bg-primary/10 text-primary font-semibold'
                    )}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <FolderKanban className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{ws.name}</span>
                    </div>
                    {isSelected && <Check className="h-3.5 w-3.5 text-primary shrink-0 ml-1" />}
                  </DropdownMenuItem>
                );
              })}
            </div>
          )}

          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => {
              setFormError(null);
              setIsCreateOpen(true);
            }}
            className="flex items-center gap-2 text-xs text-primary font-medium cursor-pointer"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Create New Workspace</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <WorkspaceFormModal
        open={isCreateOpen}
        onOpenChange={setIsCreateOpen}
        onSubmit={handleCreateSubmit}
        isLoading={createMutation.isPending}
        serverError={formError}
      />
    </>
  );
};
