import React, { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Search,
  Filter,
  ArrowUpDown,
  UploadCloud,
  FolderKanban,
  ChevronRight,
  FileText,
  CheckCircle2,
  Database,
  Layers,
} from 'lucide-react';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { DocumentRow } from '../components/DocumentRow';
import { DocumentCard } from '../components/DocumentCard';
import { DocumentUploadModal } from '../components/DocumentUploadModal';
import { DeleteDocumentDialog } from '../components/DeleteDocumentDialog';
import {
  useDocuments,
  useDeleteDocument,
  useRetryDocument,
} from '../hooks/useDocuments';
import { useWorkspace } from '@/features/workspaces/hooks/useWorkspaces';
import { WorkspaceDocument } from '../types/document';
import { getFileCategory } from '../lib/documentUtils';
import { BlurFade } from '@/components/magicui/BlurFade';
import { NumberTicker } from '@/components/magicui/NumberTicker';

type SortOption = 'date-desc' | 'date-asc' | 'name-asc' | 'size-desc';
type FormatFilter = 'all' | 'pdf' | 'docx' | 'pptx' | 'txt';
type StatusFilter = 'all' | 'ready' | 'processing' | 'failed';

export const DocumentsPage: React.FC = () => {
  const { workspaceId = '' } = useParams<{ workspaceId: string }>();

  const [searchQuery, setSearchQuery] = useState('');
  const [formatFilter, setFormatFilter] = useState<FormatFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [sortBy, setSortBy] = useState<SortOption>('date-desc');

  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [deletingDoc, setDeletingDoc] = useState<WorkspaceDocument | null>(null);

  const { data: workspace } = useWorkspace(workspaceId);
  const {
    data: documents = [],
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useDocuments(workspaceId);

  const deleteMutation = useDeleteDocument(workspaceId);
  const retryMutation = useRetryDocument(workspaceId);

  // Compute live library stats
  const readyCount = useMemo(() => documents.filter((d) => d.processing_status === 'ready').length, [documents]);
  const totalChunks = useMemo(() => documents.reduce((acc, d) => acc + (d.chunk_count || 0), 0), [documents]);

  // Filter and sort documents
  const filteredDocuments = useMemo(() => {
    let result = [...documents];

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter((d) => d.original_filename.toLowerCase().includes(q));
    }

    // Format filter
    if (formatFilter !== 'all') {
      result = result.filter((d) => getFileCategory(d.original_filename) === formatFilter);
    }

    // Status filter
    if (statusFilter !== 'all') {
      if (statusFilter === 'ready') {
        result = result.filter((d) => d.processing_status === 'ready');
      } else if (statusFilter === 'failed') {
        result = result.filter((d) => d.processing_status === 'failed');
      } else if (statusFilter === 'processing') {
        result = result.filter(
          (d) =>
            d.processing_status === 'queued' ||
            d.processing_status === 'extracting' ||
            d.processing_status === 'chunking' ||
            d.processing_status === 'indexing'
        );
      }
    }

    // Sorting
    result.sort((a, b) => {
      if (sortBy === 'date-desc') {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
      if (sortBy === 'date-asc') {
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      if (sortBy === 'name-asc') {
        return a.original_filename.localeCompare(b.original_filename);
      }
      if (sortBy === 'size-desc') {
        return b.file_size_bytes - a.file_size_bytes;
      }
      return 0;
    });

    return result;
  }, [documents, searchQuery, formatFilter, statusFilter, sortBy]);

  const handleDeleteConfirm = async () => {
    if (!deletingDoc) return;
    try {
      await deleteMutation.mutateAsync(deletingDoc.id);
      setDeletingDoc(null);
    } catch (err: unknown) {
      console.error('Document delete failed:', err);
    }
  };

  const handleRetryJob = async (doc: WorkspaceDocument) => {
    try {
      await retryMutation.mutateAsync(doc.id);
    } catch (err: unknown) {
      console.error('Document retry failed:', err);
    }
  };

  return (
    <PageContainer>
      {/* Breadcrumb Navigation */}
      <BlurFade delay={0.03}>
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
                className="hover:text-text-primary transition-colors flex items-center gap-1"
              >
                <FolderKanban className="h-3.5 w-3.5 text-primary" />
                <span>{workspace ? workspace.name : 'Workspace'}</span>
              </Link>
            </li>
            <ChevronRight className="h-3 w-3 text-border" />
            <li className="font-medium text-text-primary">Document Library</li>
          </ol>
        </nav>
      </BlurFade>

      {/* Page Header */}
      <BlurFade delay={0.06}>
        <PageHeader
          title="Document Library"
          description={`Knowledge sources for ${workspace ? `"${workspace.name}"` : 'this workspace'}. Supports PDF, Word (.docx), Slides (.pptx), and Text notes (.txt, .md).`}
          action={
            <Button onClick={() => setIsUploadOpen(true)} variant="glow" className="gap-2">
              <UploadCloud className="h-4 w-4" />
              <span>Add Documents</span>
            </Button>
          }
        />
      </BlurFade>

      {/* Live Library KPI Cards */}
      <BlurFade delay={0.09}>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <Card className="p-3.5 border-border/80 bg-surface/80">
            <span className="text-xs text-text-muted font-medium flex items-center justify-between">
              Total Files
              <FileText className="h-3.5 w-3.5 text-primary" />
            </span>
            <div className="mt-1.5 text-xl font-bold text-text-primary">
              <NumberTicker value={documents.length} />
            </div>
          </Card>

          <Card className="p-3.5 border-border/80 bg-surface/80">
            <span className="text-xs text-text-muted font-medium flex items-center justify-between">
              Indexed & Ready
              <CheckCircle2 className="h-3.5 w-3.5 text-success" />
            </span>
            <div className="mt-1.5 text-xl font-bold text-success">
              <NumberTicker value={readyCount} />
            </div>
          </Card>

          <Card className="p-3.5 border-border/80 bg-surface/80">
            <span className="text-xs text-text-muted font-medium flex items-center justify-between">
              Vector Chunks
              <Layers className="h-3.5 w-3.5 text-accent" />
            </span>
            <div className="mt-1.5 text-xl font-bold text-accent">
              <NumberTicker value={totalChunks} />
            </div>
          </Card>

          <Card className="p-3.5 border-border/80 bg-surface/80">
            <span className="text-xs text-text-muted font-medium flex items-center justify-between">
              ChromaDB Index
              <Database className="h-3.5 w-3.5 text-indigo-400" />
            </span>
            <div className="mt-1.5 text-sm font-semibold text-text-primary pt-1">
              Active (384d)
            </div>
          </Card>
        </div>
      </BlurFade>

      {/* Search, Filter, and Sort Controls */}
      <BlurFade delay={0.12}>
        <div className="mb-6 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search documents"
              placeholder="Search documents by filename..."
              className="pl-10 h-10 bg-surface/80 border-border/80 focus:border-primary/60"
            />
          </div>

          {/* Filter & Sort Controls */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Format Filter */}
            <div className="flex items-center gap-1.5 text-xs">
              <Filter className="h-3.5 w-3.5 text-text-muted hidden sm:inline" />
              <select
                value={formatFilter}
                onChange={(e) => setFormatFilter(e.target.value as FormatFilter)}
                aria-label="Filter by document format"
                className="h-9 rounded-lg border border-border bg-surface-muted px-3 text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-pointer"
              >
                <option value="all">All Formats</option>
                <option value="pdf">PDF Documents</option>
                <option value="docx">Word (.docx)</option>
                <option value="pptx">Slides (.pptx)</option>
                <option value="txt">Text (.txt, .md)</option>
              </select>
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
              aria-label="Filter by processing status"
              className="h-9 rounded-lg border border-border bg-surface-muted px-3 text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-pointer"
            >
              <option value="all">All Statuses</option>
              <option value="ready">Ready (Indexed)</option>
              <option value="processing">Processing</option>
              <option value="failed">Failed</option>
            </select>

            {/* Sort */}
            <div className="flex items-center gap-1.5 text-xs">
              <ArrowUpDown className="h-3.5 w-3.5 text-text-muted hidden sm:inline" />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortOption)}
                aria-label="Sort documents"
                className="h-9 rounded-lg border border-border bg-surface-muted px-3 text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-pointer"
              >
                <option value="date-desc">Newest First</option>
                <option value="date-asc">Oldest First</option>
                <option value="name-asc">Filename (A-Z)</option>
                <option value="size-desc">Size (Largest)</option>
              </select>
            </div>
          </div>
        </div>
      </BlurFade>

      {/* Content States */}
      <BlurFade delay={0.15}>
        {isLoading ? (
          <LoadingState variant="skeleton-list" count={5} />
        ) : isError ? (
          <ErrorState
            title="Unable to load documents"
            message={
              error?.message ||
              'A network error occurred while communicating with the document service.'
            }
            onRetry={() => refetch()}
            isRetrying={isRefetching}
          />
        ) : documents.length === 0 ? (
          <EmptyState
            icon={UploadCloud}
            title="Your workspace is ready for its first document"
            description="Add PDFs, Word documents, PowerPoint slides, and plain text study notes to start conversational exploration."
            actionLabel="Add Documents"
            onAction={() => setIsUploadOpen(true)}
          />
        ) : filteredDocuments.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No matching documents found"
            description={`No documents match the filter criteria "${searchQuery || formatFilter}". Try adjusting your filters.`}
            actionLabel="Clear Filters"
            onAction={() => {
              setSearchQuery('');
              setFormatFilter('all');
              setStatusFilter('all');
            }}
          />
        ) : (
          <>
            {/* Desktop Table View */}
            <div className="hidden md:block overflow-x-auto rounded-xl border border-border/80 bg-surface shadow-elevation-1">
              <table className="w-full min-w-[680px] text-left border-collapse">
                <thead>
                  <tr className="border-b border-border/80 bg-surface-muted/60 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    <th className="py-3 px-4">Document</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Size & Chunks</th>
                    <th className="py-3 px-4">Uploaded</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {filteredDocuments.map((doc) => (
                    <DocumentRow
                      key={doc.id}
                      document={doc}
                      onDelete={setDeletingDoc}
                      onRetry={handleRetryJob}
                      isRetrying={retryMutation.isPending}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile Card View */}
            <div className="grid grid-cols-1 gap-3 md:hidden">
              {filteredDocuments.map((doc) => (
                <DocumentCard
                  key={doc.id}
                  document={doc}
                  onDelete={setDeletingDoc}
                  onRetry={handleRetryJob}
                  isRetrying={retryMutation.isPending}
                />
              ))}
            </div>

            {/* Summary footer */}
            <div className="mt-4 flex items-center justify-between text-xs text-text-muted px-1">
              <span>
                Showing {filteredDocuments.length} of {documents.length}{' '}
                {documents.length === 1 ? 'document' : 'documents'}
              </span>
              <span className="font-mono text-[11px] text-primary/70">
                Workspace ID: {workspaceId.slice(0, 8)}...
              </span>
            </div>
          </>
        )}
      </BlurFade>

      {/* Upload Modal */}
      <DocumentUploadModal
        workspaceId={workspaceId}
        open={isUploadOpen}
        onOpenChange={setIsUploadOpen}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteDocumentDialog
        document={deletingDoc}
        open={Boolean(deletingDoc)}
        onOpenChange={(open) => !open && setDeletingDoc(null)}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
      />
    </PageContainer>
  );
};
