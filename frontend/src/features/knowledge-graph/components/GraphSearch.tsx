/**
 * Knowledge Graph server-backed search with autocomplete dropdown (Phase 7 C7.8).
 */

import React, { useState, useEffect, useRef } from 'react';
import { Search, X, Loader2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useKnowledgeGraphSearch } from '../hooks/useKnowledgeGraph';
import { GraphNodeItem } from '../types/knowledgeGraph';
import { cn } from '@/lib/utils';

export interface GraphSearchProps {
  workspaceId: string;
  snapshotId?: string;
  onSelectNode: (nodeId: string, nodeName?: string) => void;
  className?: string;
}

export const GraphSearch: React.FC<GraphSearchProps> = ({
  workspaceId,
  snapshotId,
  onSelectNode,
  className,
}) => {
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);
  const containerRef = useRef<HTMLDivElement>(null);

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 250);
    return () => clearTimeout(handler);
  }, [query]);

  // Query search endpoint
  const { data: searchResponse, isLoading, isFetching } = useKnowledgeGraphSearch(
    workspaceId,
    {
      search: debouncedQuery,
      snapshotId: snapshotId,
      pageSize: 8,
    },
    Boolean(debouncedQuery && debouncedQuery.length >= 2)
  );

  const searchResults = searchResponse?.items || [];

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (item: GraphNodeItem) => {
    onSelectNode(item.id, item.label);
    setQuery(item.label);
    setIsOpen(false);
    setSelectedIndex(-1);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen || searchResults.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < searchResults.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : searchResults.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < searchResults.length) {
        handleSelect(searchResults[selectedIndex]);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  const handleClear = () => {
    setQuery('');
    setDebouncedQuery('');
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} className={cn('relative w-full max-w-xs sm:max-w-sm', className)}>
      <div className="relative flex items-center">
        <Search className="absolute left-3 h-4 w-4 text-text-muted pointer-events-none" />
        <Input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => {
            if (query.trim().length >= 2) setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search concepts or entities..."
          className="pl-9 pr-9 h-9 text-xs bg-surface-muted/80 border-border focus-visible:ring-1 focus-visible:ring-primary rounded-lg"
          aria-label="Search knowledge graph"
        />
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-2.5 p-0.5 text-text-muted hover:text-text-primary rounded-full hover:bg-surface"
            aria-label="Clear search"
          >
            {isFetching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>

      {/* Autocomplete Dropdown */}
      {isOpen && debouncedQuery.length >= 2 && (
        <div className="absolute top-full mt-1.5 left-0 right-0 z-50 bg-surface border border-border rounded-xl shadow-2xl overflow-hidden py-1.5 animate-in fade-in-50 zoom-in-95">
          {isLoading ? (
            <div className="flex items-center justify-center p-4 text-xs text-text-muted gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              <span>Searching knowledge graph...</span>
            </div>
          ) : searchResults.length === 0 ? (
            <div className="p-4 text-center text-xs text-text-muted">
              No concepts or entities found for "{debouncedQuery}".
            </div>
          ) : (
            <div className="max-h-64 overflow-y-auto divide-y divide-border/30">
              {searchResults.map((item, idx) => {
                const isSelected = idx === selectedIndex;
                const isConcept = item.node_kind === 'concept';
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handleSelect(item)}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={cn(
                      'w-full text-left px-3 py-2 flex items-center justify-between gap-2 text-xs transition-colors',
                      isSelected ? 'bg-primary/10 text-text-primary' : 'hover:bg-surface-muted text-text-secondary'
                    )}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <div
                        className={cn(
                          'w-2 h-2 rounded-full shrink-0',
                          isConcept ? 'bg-violet-400' : 'bg-teal-400'
                        )}
                      />
                      <span className="font-medium text-text-primary truncate">
                        {item.label}
                      </span>
                      {item.aliases && item.aliases.length > 0 && (
                        <span className="text-[10px] text-text-muted truncate">
                          alias: {item.aliases[0]}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {item.node_type && (
                        <Badge variant="secondary" className="text-[10px] py-0 px-1.5 font-normal">
                          {item.node_type}
                        </Badge>
                      )}
                      <Badge
                        variant="outline"
                        className={cn(
                          'text-[10px] py-0 px-1.5 uppercase font-mono',
                          isConcept ? 'border-violet-500/30 text-violet-400' : 'border-teal-500/30 text-teal-400'
                        )}
                      >
                        {item.node_kind}
                      </Badge>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
