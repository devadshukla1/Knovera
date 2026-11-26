import React, { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Layers, ChevronRight, ChevronLeft, RefreshCw, FolderKanban } from 'lucide-react';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { ErrorState } from '@/components/shared/ErrorState';
import { useWorkspace } from '@/features/workspaces/hooks/useWorkspaces';
import {
  useWorkspaceTopics,
  useTopicRuns,
} from '../hooks/useTopics';
import { TopicCard } from '../components/TopicCard';
import { TopicSummaryHeader } from '../components/TopicSummaryHeader';
import { TopicFilters } from '../components/TopicFilters';
import { TopicSkeleton } from '../components/TopicSkeleton';
import { TopicEmptyState } from '../components/TopicEmptyState';
import { TopicSortOption } from '../types/topic';

export const TopicExplorerPage: React.FC = () => {
  const { workspaceId = '' } = useParams<{ workspaceId: string }>();

  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<TopicSortOption>('chunk_count-desc');
  const [selectedRunId, setSelectedRunId] = useState<string | undefined>(undefined);
  const [page, setPage] = useState<number>(1);
  const pageSize = 18;

  // Split sortBy into backend parameters
  const [sortField, sortOrder] = useMemo(() => {
    const parts = sortBy.split('-');
    return [parts[0], parts[1] || 'desc'];
  }, [sortBy]);

  // Fetch parent workspace metadata
  const { data: workspace } = useWorkspace(workspaceId);

  // Fetch historical clustering runs for workspace
  const { data: runsData } = useTopicRuns(workspaceId);
  const historicalRuns = runsData?.items || [];

  // Fetch paginated topics
  const {
    data: topicsData,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useWorkspaceTopics(workspaceId, {
    run_id: selectedRunId,
    search: searchQuery,
    sort_by: sortField,
    sort_order: sortOrder,
    page,
    page_size: pageSize,
  });

  const topics = topicsData?.items || [];
  const total = topicsData?.total || 0;
  const totalPages = topicsData?.total_pages || 1;
  const activeRun = topicsData?.run;

  // Aggregate stats across current topics
  const totalChunks = useMemo(() => {
    return topics.reduce((acc, t) => acc + (t.chunk_count || 0), 0);
  }, [topics]);

  const totalDocuments = useMemo(() => {
    const docCounts = topics.map((t) => t.document_count || 0);
    return Math.max(0, ...docCounts);
  }, [topics]);

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    setPage(1); // Reset page on new search
  };

  const handleSortChange = (newSort: TopicSortOption) => {
    setSortBy(newSort);
    setPage(1);
  };

  const handleRunChange = (runId?: string) => {
    setSelectedRunId(runId);
    setPage(1);
  };

  return (
    <PageContainer>
      {/* Page Header */}
      <PageHeader
        title="Topic Explorer"
        description="Unsupervised semantic clustering and thematic knowledge discovered across your workspace documents."
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
              className="hover:text-text-primary transition-colors max-w-[140px] truncate"
            >
              {workspace?.name || 'Workspace'}
            </Link>
            <ChevronRight className="w-3.5 h-3.5 text-text-muted/60" />
            <span className="text-text-primary font-medium flex items-center gap-1">
              <Layers className="w-3.5 h-3.5 text-primary" />
              Topics
            </span>
          </div>
        }
        action={
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isRefetching}
            className="text-xs h-9 gap-1.5"
            title="Refresh topic discovery"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefetching ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      {/* Loading Skeleton */}
      {isLoading && <TopicSkeleton />}

      {/* Error State */}
      {!isLoading && isError && (
        <ErrorState
          title="Failed to load topics"
          message={error?.message || 'Could not retrieve discovered topics for this workspace.'}
          onRetry={() => refetch()}
        />
      )}

      {/* Content State */}
      {!isLoading && !isError && (
        <>
          {/* Summary metrics and run selector */}
          <TopicSummaryHeader
            totalTopics={total}
            totalChunks={totalChunks}
            totalDocuments={totalDocuments}
            activeRun={activeRun}
            runs={historicalRuns}
            selectedRunId={selectedRunId}
            onSelectRun={handleRunChange}
          />

          {/* Search and Sort Toolbar */}
          {(total > 0 || searchQuery) && (
            <TopicFilters
              searchQuery={searchQuery}
              onSearchChange={handleSearchChange}
              sortBy={sortBy}
              onSortChange={handleSortChange}
              totalFiltered={topics.length}
            />
          )}

          {/* Empty State: Zero topics discovered */}
          {total === 0 && !searchQuery && (
            <TopicEmptyState workspaceId={workspaceId} />
          )}

          {/* Empty State: Search yielded no matches */}
          {topics.length === 0 && searchQuery && (
            <TopicEmptyState
              isSearchFiltered
              workspaceId={workspaceId}
              onResetSearch={() => handleSearchChange('')}
            />
          )}

          {/* Topics Grid */}
          {topics.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-8">
              {topics.map((topic) => (
                <TopicCard
                  key={topic.id}
                  topic={topic}
                  workspaceId={workspaceId}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t border-border/60">
              <p className="text-xs text-text-muted">
                Showing page <span className="font-semibold text-text-primary">{page}</span> of{' '}
                <span className="font-semibold text-text-primary">{totalPages}</span> ({total} topics)
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="h-8 text-xs gap-1"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="h-8 text-xs gap-1"
                >
                  Next
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </PageContainer>
  );
};
