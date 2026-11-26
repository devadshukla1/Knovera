import React from 'react';
import { Link } from 'react-router-dom';
import { Layers, SearchX, FilePlus2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface TopicEmptyStateProps {
  isSearchFiltered?: boolean;
  workspaceId: string;
  onResetSearch?: () => void;
}

export const TopicEmptyState: React.FC<TopicEmptyStateProps> = ({
  isSearchFiltered,
  workspaceId,
  onResetSearch,
}) => {
  if (isSearchFiltered) {
    return (
      <div className="flex flex-col items-center justify-center text-center p-8 sm:p-12 rounded-xl border border-dashed border-border bg-surface/50 max-w-lg mx-auto my-8">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-surface-muted text-primary mb-4 border border-border/80">
          <SearchX className="h-6 w-6" />
        </div>
        <h3 className="text-lg font-semibold text-text-primary mb-2">No matching topics found</h3>
        <p className="text-sm text-text-secondary max-w-sm leading-relaxed mb-6">
          We couldn't find any topics matching your query. Try searching for different keywords or clear your search filter.
        </p>
        {onResetSearch && (
          <Button onClick={onResetSearch} variant="default" size="default">
            Clear Search Filter
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center text-center p-8 sm:p-12 rounded-xl border border-dashed border-border bg-surface/50 max-w-xl mx-auto my-8">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary mb-4 border border-primary/20">
        <Layers className="h-6 w-6" />
      </div>
      <h3 className="text-xl font-semibold text-text-primary mb-2">No topics discovered yet</h3>
      <p className="text-sm text-text-secondary max-w-md leading-relaxed mb-6">
        Topic Discovery automatically analyzes and clusters document chunks into high-level themes using K-Means and semantic embeddings. Add documents to your workspace to generate topics.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link to={`/app/workspaces/${encodeURIComponent(workspaceId)}/documents`}>
          <Button variant="default" size="default" className="gap-2">
            <FilePlus2 className="w-4 h-4" />
            Go to Documents
          </Button>
        </Link>
      </div>
    </div>
  );
};
