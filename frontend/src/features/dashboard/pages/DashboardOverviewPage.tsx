import React, { useState } from 'react';
import { WorkspaceActivity } from '../components/WorkspaceActivity';
import { Link } from 'react-router-dom';
import {
  FolderKanban,
  Plus,
  ArrowRight,
  FileText,
  MessageSquare,
  GraduationCap,
  Network,
  ArrowUpRight,
} from 'lucide-react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { WorkspaceCard } from '@/features/workspaces/components/WorkspaceCard';
import { WorkspaceFormModal } from '@/features/workspaces/components/WorkspaceFormModal';
import { DeleteWorkspaceDialog } from '@/features/workspaces/components/DeleteWorkspaceDialog';
import {
  useWorkspaces,
  useCreateWorkspace,
  useUpdateWorkspace,
  useDeleteWorkspace,
} from '@/features/workspaces/hooks/useWorkspaces';
import { Workspace } from '@/features/workspaces/types/workspace';
import { WorkspaceFormValues } from '@/features/workspaces/schemas/workspaceSchema';
import { useWorkspaceContext } from '@/features/workspaces/context/WorkspaceContext';
import { BlurFade } from '@/components/magicui/BlurFade';

export const DashboardOverviewPage: React.FC = () => {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingWorkspace, setEditingWorkspace] = useState<Workspace | null>(null);
  const [deletingWorkspace, setDeletingWorkspace] = useState<Workspace | null>(null);
  const [formServerError, setFormServerError] = useState<string | null>(null);

  const { activeWorkspaceId } = useWorkspaceContext();

  const {
    data: workspaces,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useWorkspaces();

  const createMutation = useCreateWorkspace();
  const updateMutation = useUpdateWorkspace();
  const deleteMutation = useDeleteWorkspace();

  const handleOpenCreate = () => {
    setFormServerError(null);
    setIsCreateModalOpen(true);
  };

  const handleOpenRename = (workspace: Workspace) => {
    setFormServerError(null);
    setEditingWorkspace(workspace);
  };

  const handleOpenDelete = (workspace: Workspace) => {
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
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to create workspace.';
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
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to update workspace.';
      setFormServerError(message);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deletingWorkspace) return;
    try {
      await deleteMutation.mutateAsync(deletingWorkspace.id);
      setDeletingWorkspace(null);
    } catch (err: unknown) {
      console.error('Delete failed:', err);
    }
  };

  const wsPrefix = activeWorkspaceId
    ? `/app/workspaces/${encodeURIComponent(activeWorkspaceId)}`
    : '/app/workspaces';

  return (
    <PageContainer>
      <section className="dashboard-intro">
        <div>
          <span className="eyebrow">Your research, in focus</span>
          <h1>Your knowledge, connected.</h1>
          <p>Organise your research, explore ideas, and turn your documents into actionable knowledge.</p>
        </div>
        <Button onClick={handleOpenCreate} className="gap-2">
          <Plus className="h-4 w-4" /> Create Workspace
        </Button>
      </section>

      <section className="dashboard-metrics" aria-label="Workspace overview">
        <div className="dashboard-metric">
          <span className="text-xs text-text-secondary">Workspaces</span>
          <strong>{isLoading ? '…' : isError ? '—' : workspaces?.length ?? 0}</strong>
          <p>Research collections</p>
        </div>
        <div className="dashboard-metric">
          <span className="text-xs text-text-secondary">Documents</span>
          <strong>{isLoading ? '…' : workspaces?.every(w => typeof w.document_count === 'number') ? workspaces.reduce((sum, w) => sum + (w.document_count ?? 0), 0) : '—'}</strong>
          <p>Across your workspaces</p>
        </div>
        <div className="dashboard-metric">
          <span className="text-xs text-text-secondary">Research formats</span>
          <strong className="!text-base !mt-4 !mb-3">PDF · DOCX · PPTX · TXT</strong>
          <p>Bring your own sources</p>
        </div>
      </section>

      {/* 3. Core Intelligence Hub (Fast Access) */}
      <BlurFade delay={0.15}>
        <div className="mb-8">
          <div className="mb-4">
            <h2 className="text-base sm:text-lg font-semibold text-text-primary">
              A place for every idea
            </h2>
            <p className="text-xs text-text-muted">
              Move from source material to understanding.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <Link to={activeWorkspaceId ? `${wsPrefix}/documents` : '/app/workspaces'} className="group">
              <Card className="p-4 h-full border-border/80 bg-surface/90 hover:bg-surface-elevated hover:border-primary/40 hover:shadow-elevation-2 transition-all duration-200">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 group-hover:scale-105 transition-transform">
                    <FileText className="h-4 w-4" />
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-text-muted group-hover:text-primary transition-colors" />
                </div>
                <h3 className="font-semibold text-sm text-text-primary group-hover:text-primary transition-colors">
                  Document Library
                </h3>
                <p className="text-xs text-text-secondary mt-1 leading-relaxed">
                  Keep your source material organised and ready to explore.
                </p>
              </Card>
            </Link>

            <Link to={activeWorkspaceId ? `${wsPrefix}/chat` : '/app/workspaces'} className="group">
              <Card className="p-4 h-full border-border/80 bg-surface/90 hover:bg-surface-elevated hover:border-primary/40 hover:shadow-elevation-2 transition-all duration-200">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 text-primary border border-primary/25 group-hover:scale-105 transition-transform">
                    <MessageSquare className="h-4 w-4" />
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-text-muted group-hover:text-primary transition-colors" />
                </div>
                <h3 className="font-semibold text-sm text-text-primary group-hover:text-primary transition-colors">
                  Research Chat
                </h3>
                <p className="text-xs text-text-secondary mt-1 leading-relaxed">
                  Ask questions. Follow the evidence back to its source.
                </p>
              </Card>
            </Link>

            <Link to={activeWorkspaceId ? `${wsPrefix}/study-studio` : '/app/workspaces'} className="group">
              <Card className="p-4 h-full border-border/80 bg-surface/90 hover:bg-surface-elevated hover:border-primary/40 hover:shadow-elevation-2 transition-all duration-200">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 group-hover:scale-105 transition-transform">
                    <GraduationCap className="h-4 w-4" />
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-text-muted group-hover:text-primary transition-colors" />
                </div>
                <h3 className="font-semibold text-sm text-text-primary group-hover:text-primary transition-colors">
                  Study Studio
                </h3>
                <p className="text-xs text-text-secondary mt-1 leading-relaxed">
                  Generate adaptive quizzes, active recall flashcards & revision notes.
                </p>
              </Card>
            </Link>

            <Link to={activeWorkspaceId ? `${wsPrefix}/knowledge-graph` : '/app/workspaces'} className="group">
              <Card className="p-4 h-full border-border/80 bg-surface/90 hover:bg-surface-elevated hover:border-primary/40 hover:shadow-elevation-2 transition-all duration-200">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20 group-hover:scale-105 transition-transform">
                    <Network className="h-4 w-4" />
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-text-muted group-hover:text-primary transition-colors" />
                </div>
                <h3 className="font-semibold text-sm text-text-primary group-hover:text-primary transition-colors">
                  Knowledge Graph
                </h3>
                <p className="text-xs text-text-secondary mt-1 leading-relaxed">
                  See how your topics, concepts, and source material connect.
                </p>
              </Card>
            </Link>
          </div>
        </div>
      </BlurFade>

      {/* 4. Recent Workspaces Section */}
      <BlurFade delay={0.2}>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base sm:text-lg font-semibold text-text-primary">
                Recent Workspaces
              </h2>
              <p className="text-xs text-text-secondary mt-0.5">
                Pick up where you left off.
              </p>
            </div>
            {workspaces && workspaces.length > 0 && (
              <Link to="/app/workspaces">
                <Button variant="ghost" size="sm" className="gap-1.5 text-xs text-primary hover:text-primary-hover">
                  <span>View all ({workspaces.length})</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            )}
          </div>

          {/* Data States */}
          {isLoading ? (
            <LoadingState variant="skeleton-cards" count={3} />
          ) : isError ? (
            <ErrorState
              title="Unable to load workspaces"
              message={
                error?.message ||
                'A network error occurred while communicating with the backend workspace service.'
              }
              onRetry={() => refetch()}
              isRetrying={isRefetching}
            />
          ) : workspaces && workspaces.length === 0 ? (
            <EmptyState
              icon={FolderKanban}
              title="Your knowledge journey starts here."
              description="Create your first workspace to organise documents, research, and learning materials."
              actionLabel="Create Your First Workspace"
              onAction={handleOpenCreate}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {workspaces?.slice(0, 6).map((workspace) => (
                <WorkspaceCard
                  key={workspace.id}
                  workspace={workspace}
                  onRename={handleOpenRename}
                  onDelete={handleOpenDelete}
                />
              ))}
            </div>
          )}
        </div>
      </BlurFade>

      {activeWorkspaceId && <WorkspaceActivity workspaceId={activeWorkspaceId} />}

      {/* Create Modal */}
      <WorkspaceFormModal
        open={isCreateModalOpen}
        onOpenChange={setIsCreateModalOpen}
        onSubmit={handleCreateSubmit}
        isLoading={createMutation.isPending}
        serverError={formServerError}
      />

      {/* Rename Modal */}
      <WorkspaceFormModal
        open={Boolean(editingWorkspace)}
        onOpenChange={(open) => !open && setEditingWorkspace(null)}
        workspace={editingWorkspace}
        onSubmit={handleRenameSubmit}
        isLoading={updateMutation.isPending}
        serverError={formServerError}
      />

      {/* Delete Confirmation */}
      <DeleteWorkspaceDialog
        workspace={deletingWorkspace}
        open={Boolean(deletingWorkspace)}
        onOpenChange={(open) => !open && setDeletingWorkspace(null)}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
      />
    </PageContainer>
  );
};
