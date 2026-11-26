import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  ChevronRight,
  FolderKanban,
  Layers,
  Sparkles,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileText,
  Files,
  Cpu,
} from 'lucide-react';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { useWorkspace } from '@/features/workspaces/hooks/useWorkspaces';
import {
  useTopicDetail,
  useTopicChunks,
} from '../hooks/useTopics';
import { TopicChunkList } from '../components/TopicChunkList';

export const TopicDetailPage: React.FC = () => {
  const { workspaceId = '', topicId = '' } = useParams<{
    workspaceId: string;
    topicId: string;
  }>();

  const [page, setPage] = useState<number>(1);
  const [representativeOnly, setRepresentativeOnly] = useState<boolean>(false);
  const pageSize = 15;

  // Workspace details
  const { data: workspace } = useWorkspace(workspaceId);

  // Topic detail
  const {
    data: topic,
    isLoading: isTopicLoading,
    isError: isTopicError,
    error: topicError,
    refetch: refetchTopic,
  } = useTopicDetail(workspaceId, topicId);

  // Paginated assigned chunks
  const {
    data: chunksData,
    isLoading: isChunksLoading,
    isError: isChunksError,
    error: chunksError,
    refetch: refetchChunks,
  } = useTopicChunks(workspaceId, topicId, {
    page,
    page_size: pageSize,
    representative_only: representativeOnly,
  });

  const chunks = chunksData?.items || [];
  const totalChunks = chunksData?.total || 0;
  const totalPages = chunksData?.total_pages || 1;

  const handleToggleRepresentative = (val: boolean) => {
    setRepresentativeOnly(val);
    setPage(1); // Reset to page 1 on filter change
  };

  if (isTopicLoading) {
    return (
      <PageContainer>
        <LoadingState message="Loading topic details..." />
      </PageContainer>
    );
  }

  if (isTopicError || !topic) {
    return (
      <PageContainer>
        <div className="space-y-4">
          <Link to={`/app/workspaces/${encodeURIComponent(workspaceId)}/topics`}>
            <Button variant="outline" size="sm" className="gap-1.5 text-xs h-9">
              <ArrowLeft className="w-3.5 h-3.5" />
              Back to Topics
            </Button>
          </Link>
          <ErrorState
            title="Topic not found"
            message={
              topicError?.message ||
              'The requested topic could not be found or does not belong to this workspace.'
            }
            onRetry={() => refetchTopic()}
          />
        </div>
      </PageContainer>
    );
  }

  const renderStatusBadge = () => {
    switch (topic.label_status) {
      case 'approved':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Approved
          </span>
        );
      case 'reviewed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Sparkles className="w-3.5 h-3.5" />
            Reviewed
          </span>
        );
      case 'needs_review':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertCircle className="w-3.5 h-3.5" />
            Needs Review
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20">
            <Clock className="w-3.5 h-3.5" />
            Suggested
          </span>
        );
    }
  };

  return (
    <PageContainer>
      {/* Header with Navigation */}
      <PageHeader
        title={topic.label}
        description={topic.description || 'Semantic topic cluster discovered in workspace documents.'}
        breadcrumbs={
          <div className="flex items-center gap-1.5 text-xs text-text-muted">
            <Link
              to="/app/workspaces"
              className="hover:text-text-primary transition-colors flex items-center gap-1"
            >
              <FolderKanban className="w-3.5 h-3.5" />
              Workspaces
            </Link>
            <ChevronRight className="w-3.5 h-3.5 text-text-muted/60" />
            <Link
              to={`/app/workspaces/${encodeURIComponent(workspaceId)}`}
              className="hover:text-text-primary transition-colors max-w-[120px] truncate"
            >
              {workspace?.name || 'Workspace'}
            </Link>
            <ChevronRight className="w-3.5 h-3.5 text-text-muted/60" />
            <Link
              to={`/app/workspaces/${encodeURIComponent(workspaceId)}/topics`}
              className="hover:text-text-primary transition-colors flex items-center gap-1"
            >
              <Layers className="w-3.5 h-3.5 text-primary" />
              Topics
            </Link>
            <ChevronRight className="w-3.5 h-3.5 text-text-muted/60" />
            <span className="text-text-primary font-medium truncate max-w-[150px]">
              {topic.label}
            </span>
          </div>
        }
        action={
          <Link to={`/app/workspaces/${encodeURIComponent(workspaceId)}/topics`}>
            <Button variant="outline" size="sm" className="gap-1.5 text-xs h-9">
              <ArrowLeft className="w-3.5 h-3.5" />
              Back to Topics
            </Button>
          </Link>
        }
      />

      {/* Hero Overview Card */}
      <Card className="p-5 sm:p-6 rounded-xl border border-border bg-surface mb-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              variant="outline"
              className="text-xs font-mono font-medium text-text-muted bg-surface-muted/60"
            >
              {topic.cluster_key.replace(/^cluster_/, 'Cluster #')}
            </Badge>
            {renderStatusBadge()}
            <Badge variant="secondary" className="text-xs">
              Source: {topic.label_source.replace(/_/g, ' ')}
            </Badge>
          </div>

          {topic.run_summary && (
            <span className="text-xs text-text-muted font-mono">
              run: {topic.run_summary.id.slice(0, 8)} • K={topic.run_summary.k}
            </span>
          )}
        </div>

        {/* Synthesis Description */}
        <p className="text-sm text-text-secondary leading-relaxed bg-surface-muted/30 p-3.5 rounded-lg border border-border/40">
          {topic.description || 'This topic grouping was automatically identified from shared conceptual embeddings.'}
        </p>

        {/* Metrics Row */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
          <div className="p-3 rounded-lg bg-surface-muted/40 border border-border/50 flex items-center gap-3">
            <div className="p-2 rounded-md bg-primary/10 text-primary">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs text-text-muted">Assigned Chunks</div>
              <div className="text-base font-bold text-text-primary">{topic.chunk_count}</div>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-surface-muted/40 border border-border/50 flex items-center gap-3">
            <div className="p-2 rounded-md bg-accent/10 text-accent">
              <Files className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs text-text-muted">Contributing Docs</div>
              <div className="text-base font-bold text-text-primary">{topic.document_count}</div>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-surface-muted/40 border border-border/50 flex items-center gap-3 col-span-2 sm:col-span-1">
            <div className="p-2 rounded-md bg-indigo-500/10 text-indigo-400">
              <Cpu className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs text-text-muted">Centroid Representatives</div>
              <div className="text-base font-bold text-text-primary">
                {topic.representative_chunk_ids?.length || 0}
              </div>
            </div>
          </div>
        </div>

        {/* Keywords Cloud */}
        {topic.keywords && topic.keywords.length > 0 && (
          <div className="pt-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">
              Ranked Semantic Keywords
            </h4>
            <div className="flex flex-wrap gap-2">
              {topic.keywords.map((kw, idx) => (
                <div
                  key={`${kw.term}-${idx}`}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-surface-muted text-text-primary border border-border"
                >
                  <span className="font-medium">{kw.term}</span>
                  <span className="text-[10px] text-text-muted font-mono">
                    {(kw.score * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Chunks Section */}
      {isChunksError ? (
        <ErrorState
          title="Could not load assigned chunks"
          message={chunksError?.message || 'Failed to retrieve chunks for this topic.'}
          onRetry={() => refetchChunks()}
        />
      ) : (
        <TopicChunkList
          chunks={chunks}
          workspaceId={workspaceId}
          total={totalChunks}
          page={page}
          pageSize={pageSize}
          totalPages={totalPages}
          onPageChange={setPage}
          representativeOnly={representativeOnly}
          onToggleRepresentativeOnly={handleToggleRepresentative}
          isLoading={isChunksLoading}
        />
      )}
    </PageContainer>
  );
};
