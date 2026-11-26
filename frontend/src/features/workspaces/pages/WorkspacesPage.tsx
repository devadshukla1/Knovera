import React, { useState, useMemo } from 'react';
import { Search, Plus, FolderKanban } from 'lucide-react';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { WorkspaceCard } from '../components/WorkspaceCard';
import { WorkspaceFormModal } from '../components/WorkspaceFormModal';
import { DeleteWorkspaceDialog } from '../components/DeleteWorkspaceDialog';
import {
  useWorkspaces,
  useCreateWorkspace,
  useUpdateWorkspace,
  useDeleteWorkspace,
} from '../hooks/useWorkspaces';
import { Workspace } from '../types/workspace';
import { WorkspaceFormValues } from '../schemas/workspaceSchema';
import { BlurFade } from '@/components/magicui/BlurFade';

export const WorkspacesPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingWorkspace, setEditingWorkspace] = useState<Workspace | null>(null);
  const [deletingWorkspace, setDeletingWorkspace] = useState<Workspace | null>(null);
  const [formServerError, setFormServerError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const { data: workspaces, isLoading, isError, error, refetch, isRefetching } = useWorkspaces();

  const createMutation = useCreateWorkspace();
  const updateMutation = useUpdateWorkspace();
  const deleteMutation = useDeleteWorkspace();

  // Filter workspaces based on search query
  const filteredWorkspaces = useMemo(() => {
    if (!workspaces) return [];
    if (!searchQuery.trim()) return workspaces;
    const query = searchQuery.toLowerCase().trim();
    return workspaces.filter(
      (w) =>
        w.name.toLowerCase().includes(query) ||
        (w.description && w.description.toLowerCase().includes(query))
    );
  }, [workspaces, searchQuery]);

  const handleOpenCreate = () => {
    setFormServerError(null);
    setIsCreateModalOpen(true);
  };

  const handleOpenRename = (workspace: Workspace) => {
    setFormServerError(null);
    setEditingWorkspace(workspace);
  };

  const handleOpenDelete = (workspace: Workspace) => {
    setDeleteError(null);
    setDeletingWorkspace(workspace);
  };

  const handleCreateSubmit = async (values: WorkspaceFormValues) => {
    try {
      setFormServerError(null);
      await createMutation.mutateAsync({
        name: values.name,
        description: values.description || null,
      });
      setIsCreateModalOpen(false);
      setToastMessage({ type: 'success', text: `Workspace "${values.name}" created successfully.` });
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to create workspace. Please try again.';
      setFormServerError(message);
    }
  };

  const handleRenameSubmit = async (values: WorkspaceFormValues) => {
    if (!editingWorkspace) return;
    try {
      setFormServerError(null);
      await updateMutation.mutateAsync({
        id: editingWorkspace.id,
        payload: {
          name: values.name,
          description: values.description || null,
        },
      });
      setEditingWorkspace(null);
      setToastMessage({ type: 'success', text: `Workspace renamed to "${values.name}".` });
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to update workspace. Please try again.';
      setFormServerError(message);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deletingWorkspace) return;
    try {
      setDeleteError(null);
      const name = deletingWorkspace.name;
      await deleteMutation.mutateAsync(deletingWorkspace.id);
      setDeletingWorkspace(null);
      setToastMessage({ type: 'success', text: `Workspace "${name}" was successfully deleted.` });
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err: unknown) {
      console.error('Delete failed:', err);
      const message =
        err instanceof Error ? err.message : 'Failed to delete workspace. Please try again.';
      setDeleteError(message);
    }
  };

  return (
    <PageContainer>
      <BlurFade delay={0.05}>
        <PageHeader
          title="Workspaces"
          description="Organise your personal research domains, textbooks, research papers, and revision notes."
          action={
            <Button onClick={handleOpenCreate} variant="glow" className="gap-2">
              <Plus className="h-4 w-4" />
              <span>Create Workspace</span>
            </Button>
          }
        />
      </BlurFade>

      {/* User Action Feedback Toast */}
      {toastMessage && (
        <BlurFade delay={0.02}>
          <div
            role="status"
            aria-live="polite"
            className={`mb-4 flex items-center justify-between rounded-xl px-4 py-3 text-sm font-medium shadow-sm ${
              toastMessage.type === 'success'
                ? 'bg-success/15 text-success border border-success/30'
                : 'bg-danger/15 text-danger border border-danger/30'
            }`}
          >
            <span>{toastMessage.text}</span>
            <button
              onClick={() => setToastMessage(null)}
              className="text-xs opacity-70 hover:opacity-100"
              aria-label="Dismiss alert"
            >
              ✕
            </button>
          </div>
        </BlurFade>
      )}

      {/* Search and Filter Bar */}
      <BlurFade delay={0.1}>
        <div className="mb-6 flex items-center justify-between gap-4">
          <div className="relative w-full max-w-md">
            <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search workspaces"
              placeholder="Search workspaces by name or description..."
              className="pl-10 h-10 bg-surface/80 border-border/80 focus:border-primary/60"
            />
          </div>
        </div>
      </BlurFade>

      {/* Content States */}
      <BlurFade delay={0.15}>
        {isLoading ? (
          <LoadingState variant="skeleton-cards" count={6} />
        ) : isError ? (
          <ErrorState
            title="Unable to load workspaces"
            message={error?.message || 'A network error occurred while connecting to the workspace API.'}
            onRetry={() => refetch()}
            isRetrying={isRefetching}
          />
        ) : workspaces && workspaces.length === 0 ? (
          <EmptyState
            icon={FolderKanban}
            title="Your knowledge journey starts here"
            description="Create your first workspace to organise documents, research papers, and study materials."
            actionLabel="Create Your First Workspace"
            onAction={handleOpenCreate}
          />
        ) : filteredWorkspaces.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No matching workspaces"
            description={`No workspaces found matching "${searchQuery}". Try a different search term or clear the search.`}
            actionLabel="Clear Search"
            onAction={() => setSearchQuery('')}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredWorkspaces.map((workspace) => (
              <WorkspaceCard
                key={workspace.id}
                workspace={workspace}
                onRename={handleOpenRename}
                onDelete={handleOpenDelete}
              />
            ))}
          </div>
        )}
      </BlurFade>

      {/* Create Workspace Modal */}
      <WorkspaceFormModal
        open={isCreateModalOpen}
        onOpenChange={setIsCreateModalOpen}
        onSubmit={handleCreateSubmit}
        isLoading={createMutation.isPending}
        serverError={formServerError}
      />

      {/* Rename Workspace Modal */}
      <WorkspaceFormModal
        open={Boolean(editingWorkspace)}
        onOpenChange={(open) => !open && setEditingWorkspace(null)}
        workspace={editingWorkspace}
        onSubmit={handleRenameSubmit}
        isLoading={updateMutation.isPending}
        serverError={formServerError}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteWorkspaceDialog
        workspace={deletingWorkspace}
        open={Boolean(deletingWorkspace)}
        onOpenChange={(open) => {
          if (!open) {
            setDeletingWorkspace(null);
            setDeleteError(null);
          }
        }}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
        error={deleteError}
      />
    </PageContainer>
  );
};
