import React from 'react';
import { Search, X, ArrowUpDown } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { TopicSortOption } from '../types/topic';

interface TopicFiltersProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  sortBy: TopicSortOption;
  onSortChange: (sort: TopicSortOption) => void;
  totalFiltered: number;
}

export const TopicFilters: React.FC<TopicFiltersProps> = ({
  searchQuery,
  onSearchChange,
  sortBy,
  onSortChange,
  totalFiltered,
}) => {
  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 mb-6">
      {/* Search Input */}
      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-text-muted pointer-events-none" />
        <Input
          type="text"
          placeholder="Search topics, keywords, descriptions..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9 pr-9 h-9 text-xs sm:text-sm bg-surface border-border text-text-primary placeholder:text-text-muted"
        />
        {searchQuery && (
          <button
            onClick={() => onSearchChange('')}
            className="absolute right-2.5 top-2.5 text-text-muted hover:text-text-primary p-0.5 rounded"
            title="Clear search"
            aria-label="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Sorting Control */}
      <div className="flex items-center gap-2 self-end sm:self-auto">
        <div className="flex items-center gap-1.5 text-xs text-text-muted">
          <ArrowUpDown className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Sort:</span>
        </div>
        <select
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value as TopicSortOption)}
          className="bg-surface border border-border rounded-md px-2.5 py-1.5 text-xs text-text-primary focus:outline-none focus:border-primary cursor-pointer"
        >
          <option value="chunk_count-desc">Most Chunks</option>
          <option value="chunk_count-asc">Least Chunks</option>
          <option value="document_count-desc">Most Documents</option>
          <option value="label-asc">Label (A–Z)</option>
          <option value="cluster_key-asc">Cluster Key</option>
        </select>

        {searchQuery && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onSearchChange('')}
            className="text-xs text-primary hover:text-primary-hover h-8 px-2"
          >
            Clear ({totalFiltered})
          </Button>
        )}
      </div>
    </div>
  );
};
