import React from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  Star,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Filter,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { TopicChunkItem } from '../types/topic';

interface TopicChunkListProps {
  chunks: TopicChunkItem[];
  workspaceId: string;
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  onPageChange: (newPage: number) => void;
  representativeOnly: boolean;
  onToggleRepresentativeOnly: (val: boolean) => void;
  isLoading?: boolean;
}

export const TopicChunkList: React.FC<TopicChunkListProps> = ({
  chunks,
  workspaceId,
  total,
  page,
  totalPages,
  onPageChange,
  representativeOnly,
  onToggleRepresentativeOnly,
  isLoading,
}) => {
  return (
    <div className="space-y-4">
      {/* List Toolbar / Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-border/60">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text-primary">
            Assigned Chunks ({total})
          </span>
          {representativeOnly && (
            <Badge variant="outline" className="text-[10px] bg-accent/10 text-accent border-accent/20">
              Representative Centroids
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={representativeOnly ? 'default' : 'outline'}
            size="sm"
            onClick={() => onToggleRepresentativeOnly(!representativeOnly)}
            className="text-xs h-8"
          >
            <Filter className="w-3 h-3 mr-1.5" />
            {representativeOnly ? 'Show All Chunks' : 'Centroid Representatives Only'}
          </Button>
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-28 rounded-xl bg-surface-muted/50 animate-pulse border border-border" />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && chunks.length === 0 && (
        <div className="text-center py-10 px-4 rounded-xl border border-dashed border-border bg-surface/40">
          <FileText className="w-8 h-8 text-text-muted mx-auto mb-2 opacity-50" />
          <p className="text-sm font-medium text-text-primary">No chunks found</p>
          <p className="text-xs text-text-secondary mt-1">
            {representativeOnly
              ? 'No representative centroid chunks match this filter.'
              : 'No document chunks are currently assigned to this topic.'}
          </p>
          {representativeOnly && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onToggleRepresentativeOnly(false)}
              className="mt-3 text-xs"
            >
              Reset Filter
            </Button>
          )}
        </div>
      )}

      {/* Chunks List */}
      {!isLoading && chunks.length > 0 && (
        <div className="space-y-3">
          {chunks.map((chunk) => (
            <Card
              key={chunk.assignment_id}
              className="p-4 rounded-xl border border-border bg-surface hover:border-primary/30 transition-colors"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2.5">
                {/* Document Provenance Link */}
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-4 h-4 text-primary shrink-0" />
                  <Link
                    to={`/app/workspaces/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(
                      chunk.document_id
                    )}`}
                    className="text-xs sm:text-sm font-semibold text-text-primary hover:text-primary transition-colors truncate flex items-center gap-1.5"
                    title={`Open document ${chunk.document_title}`}
                  >
                    <span className="truncate">{chunk.document_title}</span>
                    <ExternalLink className="w-3 h-3 shrink-0 opacity-60" />
                  </Link>
                </div>

                {/* Metadata Pills */}
                <div className="flex items-center gap-2 shrink-0 flex-wrap">
                  {chunk.is_representative && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <Star className="w-2.5 h-2.5 fill-amber-400" />
                      Representative
                    </span>
                  )}
                  {chunk.page_start !== null && chunk.page_start !== undefined && (
                    <Badge variant="outline" className="text-[10px] py-0 bg-surface-muted/40">
                      Page {chunk.page_start}
                      {chunk.page_end && chunk.page_end !== chunk.page_start ? `–${chunk.page_end}` : ''}
                    </Badge>
                  )}
                  {chunk.slide_number !== null && chunk.slide_number !== undefined && (
                    <Badge variant="outline" className="text-[10px] py-0 bg-surface-muted/40">
                      Slide {chunk.slide_number}
                    </Badge>
                  )}
                  {chunk.distance_to_centroid !== null && chunk.distance_to_centroid !== undefined && (
                    <span className="text-[10px] text-text-muted font-mono" title="Distance to centroid embedding">
                      dist: {chunk.distance_to_centroid.toFixed(3)}
                    </span>
                  )}
                </div>
              </div>

              {/* Chunk Snippet Preview */}
              <div className="text-xs sm:text-sm text-text-secondary leading-relaxed bg-surface-muted/30 p-3 rounded-lg border border-border/40 font-mono text-[12px] sm:text-[13px]">
                {chunk.content_preview}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-4 border-t border-border/60">
          <p className="text-xs text-text-muted">
            Page <span className="font-semibold text-text-primary">{page}</span> of{' '}
            <span className="font-semibold text-text-primary">{totalPages}</span> ({total} chunks)
          </p>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
              className="h-8 text-xs gap-1"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
              className="h-8 text-xs gap-1"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
