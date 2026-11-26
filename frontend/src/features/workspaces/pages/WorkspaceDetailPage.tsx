import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  FolderKanban,
  FileText,
  MessageSquare,
  Network,
  GraduationCap,
  LineChart,
  Pencil,
  Trash2,
  Calendar,
  Clock,
  ChevronRight,
  ArrowLeft,
  ArrowUpRight,
} from 'lucide-react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { WorkspaceFormModal } from '../components/WorkspaceFormModal';
import { DeleteWorkspaceDialog } from '../components/DeleteWorkspaceDialog';
import {
  useWorkspace,
  useUpdateWorkspace,
  useDeleteWorkspace,
} from '../hooks/useWorkspaces';
import { WorkspaceFormValues } from '../schemas/workspaceSchema';
import { formatDate, formatRelativeTime } from '@/lib/utils';
import { BlurFade } from '@/components/magicui/BlurFade';

export const WorkspaceDetailPage: React.FC = () => {
  const { workspaceId = '' } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();

  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [formServerError, setFormServerError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const {
    data: workspace,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useWorkspace(workspaceId);

  const updateMutation = useUpdateWorkspace();
  const deleteMutation = useDeleteWorkspace();

  const handleRenameSubmit = async (values: WorkspaceFormValues) => {
    if (!workspace) return;
    try {
      setFormServerError(null);
      await updateMutation.mutateAsync({
        id: workspace.id,
        payload: {
          name: values.name,
          description: values.description || null,
        },
      });
      setIsRenameModalOpen(false);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to rename workspace.';
      setFormServerError(message);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!workspace) return;
    try {
      setDeleteError(null);
      await deleteMutation.mutateAsync(workspace.id);
      setIsDeleteDialogOpen(false);
      navigate('/app/workspaces', { replace: true });
    } catch (err: unknown) {
      console.error('Delete failed:', err);
      const message =
        err instanceof Error ? err.message : 'Failed to delete workspace. Please try again.';
      setDeleteError(message);
    }
  };

  if (isLoading) {
    return (
      <PageContainer>
        <div className="py-12">
          <LoadingState message="Loading workspace details..." />
        </div>
      </PageContainer>
    );
  }

  if (isError || !workspace) {
    return (
      <PageContainer>
        <div className="py-8">
          <Link
            to="/app/workspaces"
            className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary mb-6 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to Workspaces</span>
          </Link>
          <ErrorState
            title="Workspace Not Found"
            message={
              error?.message ||
              `The workspace "${workspaceId}" could not be located or you may not have access.`
            }
            onRetry={() => refetch()}
            isRetrying={isRefetching}
          />
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      {/* Breadcrumb Navigation */}
      <BlurFade delay={0.03}>
        <nav aria-label="Breadcrumb" className="mb-4">
          <ol className="flex items-center gap-1.5 text-xs text-text-muted">
            <li>
              <Link
                to="/app/workspaces"
                className="hover:text-text-primary transition-colors flex items-center gap-1"
              >
                <FolderKanban className="h-3.5 w-3.5 text-primary" />
                <span>Workspaces</span>
              </Link>
            </li>
            <ChevronRight className="h-3 w-3 text-border" />
            <li className="font-medium text-text-primary truncate max-w-[200px]">
              {workspace.name}
            </li>
          </ol>
        </nav>
      </BlurFade>

      {/* Workspace Header Card */}
      <BlurFade delay={0.06}>
        <div className="relative overflow-hidden rounded-xl border border-border bg-surface p-5 sm:p-7 shadow-sm mb-7">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div className="space-y-3">
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary border border-primary/30 shadow-glow-sm">
                  <FolderKanban className="h-6 w-6" />
                </div>
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text-primary">
                    {workspace.name}
                  </h1>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted mt-1.5">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3 text-text-muted/60" />
                      Created {formatDate(workspace.created_at)}
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3 text-text-muted/60" />
                      Updated {formatRelativeTime(workspace.updated_at)}
                    </span>
                    <span>•</span>
                    <span className="font-mono text-[11px] text-primary/80">
                      ID: {workspace.id.slice(0, 8)}...
                    </span>
                  </div>
                </div>
              </div>

              {workspace.description && (
                <p className="text-sm text-text-secondary mt-2 max-w-3xl leading-relaxed">
                  {workspace.description}
                </p>
              )}
            </div>

            {/* Header Actions */}
            <div className="flex items-center gap-2 shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setFormServerError(null);
                  setIsRenameModalOpen(true);
                }}
                className="gap-1.5 text-xs h-8"
              >
                <Pencil className="h-3.5 w-3.5 text-primary" />
                <span>Rename</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsDeleteDialogOpen(true)}
                className="gap-1.5 text-xs h-8 text-danger hover:text-danger hover:border-danger/40 hover:bg-danger/10"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Delete</span>
              </Button>
            </div>
          </div>
        </div>
      </BlurFade>

      {/* Workspace Intelligence Hub */}
      <BlurFade delay={0.1}>
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base sm:text-lg font-semibold text-text-primary">
                Workspace Intelligence Modules
              </h2>
              <p className="text-xs text-text-secondary mt-0.5">
                Explore connected documents, conversational research, and adaptive study aids for this workspace.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {/* Documents Module */}
            <Card className="border-border/80 bg-surface/80 hover:bg-surface-elevated hover:border-blue-500/40 hover:shadow-elevation-2 transition-all duration-200 flex flex-col justify-between group">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 group-hover:scale-105 transition-transform">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-sm font-semibold">Document Library</CardTitle>
                      <CardDescription className="text-xs">
                        PDF, DOCX, PPTX & TXT notes
                      </CardDescription>
                    </div>
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-text-muted group-hover:text-blue-400 transition-colors" />
                </div>
              </CardHeader>
              <CardContent className="text-xs text-text-muted space-y-3">
                <p className="leading-relaxed">
                  Browse uploaded notes, inspect chunk provenance, and manage vectors in ChromaDB.
                </p>
                <Link to={`/app/workspaces/${encodeURIComponent(workspace.id)}/documents`}>
                  <Button variant="secondary" size="sm" className="w-full text-xs gap-1.5 h-8 group-hover:bg-blue-500/20 group-hover:text-blue-300 group-hover:border-blue-500/30 transition-all">
                    <span>Open Document Library</span>
                    <ChevronRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardContent>
            </Card>

            {/* Research Chat Module */}
            <Card className="border-border/80 bg-surface/80 hover:bg-surface-elevated hover:border-primary/40 hover:shadow-elevation-2 transition-all duration-200 flex flex-col justify-between group">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary border border-primary/25 group-hover:scale-105 transition-transform">
                      <MessageSquare className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-sm font-semibold">Research Chat</CardTitle>
                      <CardDescription className="text-xs">
                        Grounded RAG with exact citations
                      </CardDescription>
                    </div>
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-text-muted group-hover:text-primary transition-colors" />
                </div>
              </CardHeader>
              <CardContent className="text-xs text-text-muted space-y-3">
                <p className="leading-relaxed">
                  Ask questions across all notes, inspect verbatim source passages, and navigate citations.
                </p>
                <Link to={`/app/workspaces/${encodeURIComponent(workspace.id)}/chat`}>
                  <Button variant="secondary" size="sm" className="w-full text-xs gap-1.5 h-8 group-hover:bg-primary group-hover:text-primary-foreground transition-all">
                    <span>Open Research Chat</span>
                    <ChevronRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardContent>
            </Card>

            {/* Study Studio Module */}
            <Card className="border-border/80 bg-surface/80 hover:bg-surface-elevated hover:border-emerald-500/40 hover:shadow-elevation-2 transition-all duration-200 flex flex-col justify-between group">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 group-hover:scale-105 transition-transform">
                      <GraduationCap className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-sm font-semibold">Study Studio</CardTitle>
                      <CardDescription className="text-xs">
                        Revision notes, flashcards & quizzes
                      </CardDescription>
                    </div>
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-text-muted group-hover:text-emerald-400 transition-colors" />
                </div>
              </CardHeader>
              <CardContent className="text-xs text-text-muted space-y-3">
                <p className="leading-relaxed">
                  Generate adaptive practice tests, interactive flashcard decks, and structured revision guides.
                </p>
                <Link to={`/app/workspaces/${encodeURIComponent(workspace.id)}/study-studio`}>
                  <Button variant="secondary" size="sm" className="w-full text-xs gap-1.5 h-8 group-hover:bg-emerald-500/20 group-hover:text-emerald-300 group-hover:border-emerald-500/30 transition-all">
                    <span>Open Study Studio</span>
                    <ChevronRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardContent>
            </Card>

            {/* Knowledge Explorer & Graph */}
            <Card className="border-border/80 bg-surface/80 hover:bg-surface-elevated hover:border-purple-500/40 hover:shadow-elevation-2 transition-all duration-200 flex flex-col justify-between group">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 group-hover:scale-105 transition-transform">
                      <Network className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-sm font-semibold">Knowledge Graph</CardTitle>
                      <CardDescription className="text-xs">
                        Topics & concept ontology map
                      </CardDescription>
                    </div>
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-text-muted group-hover:text-purple-400 transition-colors" />
                </div>
              </CardHeader>
              <CardContent className="text-xs text-text-muted space-y-3">
                <p className="leading-relaxed">
                  Interactive Cytoscape visualization of extracted entities, relations, and topic clusters.
                </p>
                <div className="flex gap-2">
                  <Link to={`/app/workspaces/${encodeURIComponent(workspace.id)}/topics`} className="flex-1">
                    <Button variant="secondary" size="sm" className="w-full text-xs gap-1 h-8">
                      <span>Topics</span>
                      <ChevronRight className="h-3 w-3" />
                    </Button>
                  </Link>
                  <Link to={`/app/workspaces/${encodeURIComponent(workspace.id)}/knowledge-graph`} className="flex-1">
                    <Button variant="secondary" size="sm" className="w-full text-xs gap-1 h-8">
                      <span>Graph</span>
                      <ChevronRight className="h-3 w-3" />
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>

            {/* Learning Analytics Module */}
            <Card className="border-border/80 bg-surface/80 hover:bg-surface-elevated hover:border-amber-500/40 hover:shadow-elevation-2 transition-all duration-200 flex flex-col justify-between group">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 group-hover:scale-105 transition-transform">
                      <LineChart className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-sm font-semibold">Learning Analytics</CardTitle>
                      <CardDescription className="text-xs">
                        BKT mastery & revision planner
                      </CardDescription>
                    </div>
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-text-muted group-hover:text-amber-400 transition-colors" />
                </div>
              </CardHeader>
              <CardContent className="text-xs text-text-muted space-y-3">
                <p className="leading-relaxed">
                  Inspect Bayesian Knowledge Tracing scores, concept retention rates, and smart revision alerts.
                </p>
                <Link to={`/app/workspaces/${encodeURIComponent(workspace.id)}/learning-analytics`}>
                  <Button variant="secondary" size="sm" className="w-full text-xs gap-1.5 h-8 group-hover:bg-amber-500/20 group-hover:text-amber-300 group-hover:border-amber-500/30 transition-all">
                    <span>Open Analytics</span>
                    <ChevronRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>
      </BlurFade>

      {/* Rename Modal */}
      <WorkspaceFormModal
        open={isRenameModalOpen}
        onOpenChange={setIsRenameModalOpen}
        workspace={workspace}
        onSubmit={handleRenameSubmit}
        isLoading={updateMutation.isPending}
        serverError={formServerError}
      />

      {/* Delete Confirmation */}
      <DeleteWorkspaceDialog
        workspace={workspace}
        open={isDeleteDialogOpen}
        onOpenChange={(open) => {
          setIsDeleteDialogOpen(open);
          if (!open) setDeleteError(null);
        }}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
        error={deleteError}
      />
    </PageContainer>
  );
};
