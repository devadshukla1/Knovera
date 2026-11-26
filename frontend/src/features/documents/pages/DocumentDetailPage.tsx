import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Trash2,
  RefreshCw,
  HardDrive,
  Info,
  ChevronRight,
  Cpu,
  FlaskConical,
} from 'lucide-react';
import { PageContainer } from '@/components/layout/PageContainer';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { DocumentStatusBadge } from '../components/DocumentStatusBadge';
import { DeleteDocumentDialog } from '../components/DeleteDocumentDialog';
import {
  useDocument,
  useDeleteDocument,
  useRetryDocument,
} from '../hooks/useDocuments';
import { useWorkspace } from '@/features/workspaces/hooks/useWorkspaces';
import { formatFileSize, getFileIcon } from '../lib/documentUtils';
import { formatDate, formatRelativeTime } from '@/lib/utils';

export const DocumentDetailPage: React.FC = () => {
  const { workspaceId = '', documentId = '' } = useParams<{
    workspaceId: string;
    documentId: string;
  }>();
  const navigate = useNavigate();

  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  const { data: workspace } = useWorkspace(workspaceId);
  const {
    data: document,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useDocument(workspaceId, documentId);

  const deleteMutation = useDeleteDocument(workspaceId);
  const retryMutation = useRetryDocument(workspaceId);

  const handleDeleteConfirm = async () => {
    if (!document) return;
    try {
      await deleteMutation.mutateAsync(document.id);
      setIsDeleteDialogOpen(false);
      navigate(`/app/workspaces/${encodeURIComponent(workspaceId)}/documents`, {
        replace: true,
      });
    } catch (err: unknown) {
      console.error('Delete failed:', err);
    }
  };

  const handleRetry = async () => {
    if (!document) return;
    try {
      await retryMutation.mutateAsync(document.id);
    } catch (err: unknown) {
      console.error('Retry failed:', err);
    }
  };

  if (isLoading) {
    return (
      <PageContainer>
        <div className="py-12">
          <LoadingState message="Loading document details..." />
        </div>
      </PageContainer>
    );
  }

  if (isError || !document) {
    return (
      <PageContainer>
        <div className="py-8">
          <Link
            to={`/app/workspaces/${encodeURIComponent(workspaceId)}/documents`}
            className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary mb-6 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to Document Library</span>
          </Link>
          <ErrorState
            title="Document Not Found"
            message={
              error?.message ||
              `The document "${documentId}" could not be found in this workspace.`
            }
            onRetry={() => refetch()}
            isRetrying={isRefetching}
          />
        </div>
      </PageContainer>
    );
  }

  const FileIcon = getFileIcon(document.original_filename);

  return (
    <PageContainer>
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="mb-4">
        <ol className="flex items-center gap-1.5 text-xs text-text-muted">
          <li>
            <Link to="/app" className="hover:text-text-primary transition-colors">
              Dashboard
            </Link>
          </li>
          <ChevronRight className="h-3 w-3 text-border" />
          <li>
            <Link
              to={`/app/workspaces/${encodeURIComponent(workspaceId)}`}
              className="hover:text-text-primary transition-colors"
            >
              {workspace ? workspace.name : 'Workspace'}
            </Link>
          </li>
          <ChevronRight className="h-3 w-3 text-border" />
          <li>
            <Link
              to={`/app/workspaces/${encodeURIComponent(workspaceId)}/documents`}
              className="hover:text-text-primary transition-colors"
            >
              Documents
            </Link>
          </li>
          <ChevronRight className="h-3 w-3 text-border" />
          <li className="font-medium text-text-primary truncate max-w-[180px]">
            {document.original_filename}
          </li>
        </ol>
      </nav>

      {/* Document Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 pb-6 border-b border-border mb-8">
        <div className="flex items-start gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-surface-muted text-primary border border-border">
            <FileIcon className="h-6 w-6" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-text-primary">
                {document.original_filename}
              </h1>
              <DocumentStatusBadge status={document.processing_status} />
            </div>
            <p className="text-xs text-text-muted mt-1 font-mono">
              ID: {document.id}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="secondary"
            size="sm"
            onClick={() =>
              navigate(
                `/app/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(document.id)}/research-analysis`
              )
            }
            className="gap-1.5 text-xs text-violet-300 border border-violet-500/30 hover:bg-violet-950/40"
          >
            <FlaskConical className="h-3.5 w-3.5 text-violet-400" />
            <span>Research Intelligence</span>
          </Button>

          {document.processing_status === 'failed' && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleRetry}
              disabled={retryMutation.isPending}
              className="gap-1.5 text-xs text-warning"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Retry Processing</span>
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsDeleteDialogOpen(true)}
            className="gap-1.5 text-xs text-danger hover:text-danger hover:border-danger/40 hover:bg-danger/10"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span>Delete</span>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: File Properties */}
        <div className="md:col-span-2 space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Info className="h-4 w-4 text-primary" />
                <span>Source File Properties</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <div className="flex items-center justify-between py-2 border-b border-border">
                <span className="text-text-secondary">MIME Media Type</span>
                <span className="font-mono text-text-primary">{document.media_type}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-border">
                <span className="text-text-secondary">File Size</span>
                <span className="font-mono text-text-primary">
                  {formatFileSize(document.file_size_bytes)} ({document.file_size_bytes.toLocaleString()} bytes)
                </span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-border">
                <span className="text-text-secondary">Extracted Pages / Slides</span>
                <span className="font-medium text-text-primary">
                  {document.page_count !== null ? `${document.page_count} pages` : 'Pending extraction'}
                </span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-border">
                <span className="text-text-secondary">Upload Timestamp</span>
                <span className="text-text-primary">
                  {formatDate(document.created_at)} ({formatRelativeTime(document.created_at)})
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-text-secondary">Last Updated</span>
                <span className="text-text-primary">
                  {formatRelativeTime(document.updated_at)}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Processing Lifecycle Pipeline */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Cpu className="h-4 w-4 text-accent" />
                <span>Ingestion Lifecycle Stages</span>
              </CardTitle>
              <CardDescription className="text-xs">
                Traceable pipeline transforming raw document bytes into indexed vector chunks.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 pt-1">
                <div className="flex items-start gap-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary text-xs font-bold">
                    1
                  </div>
                  <div className="text-xs">
                    <p className="font-semibold text-text-primary">Text & Layout Extraction</p>
                    <p className="text-text-muted mt-0.5 leading-relaxed">
                      PyMuPDF parses PDF pages, preserving bounding boxes and slide headings.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary text-xs font-bold">
                    2
                  </div>
                  <div className="text-xs">
                    <p className="font-semibold text-text-primary">Structure-Aware Chunking</p>
                    <p className="text-text-muted mt-0.5 leading-relaxed">
                      Splits content into 500–800 token sections with page provenance and SHA-256 hashes.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary text-xs font-bold">
                    3
                  </div>
                  <div className="text-xs">
                    <p className="font-semibold text-text-primary">Vector Embedding & Indexing</p>
                    <p className="text-text-muted mt-0.5 leading-relaxed">
                      Indexes embeddings into ChromaDB collection scoped to workspace <code className="font-mono text-accent">{workspaceId.slice(0, 8)}</code>.
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Actions & Storage Context */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <HardDrive className="h-4 w-4 text-primary" />
                <span>Storage Metadata</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <div>
                <span className="text-text-secondary block mb-1">Workspace Bucket</span>
                <span className="font-mono text-text-primary bg-surface-muted px-2 py-1 rounded block truncate">
                  {workspaceId}
                </span>
              </div>
              <div>
                <span className="text-text-secondary block mb-1">Vector Index Collection</span>
                <span className="font-mono text-accent bg-surface-muted px-2 py-1 rounded block truncate">
                  ws_{workspaceId.replace(/-/g, '_')}
                </span>
              </div>
              <div className="pt-2">
                <Link to={`/app/workspaces/${encodeURIComponent(workspaceId)}/chat`}>
                  <Button variant="secondary" size="sm" className="w-full text-xs">
                    Open Research Chat
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <DeleteDocumentDialog
        document={document}
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
      />
    </PageContainer>
  );
};
