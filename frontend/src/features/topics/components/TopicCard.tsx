import React from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  Files,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  Clock,
  AlertCircle,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { TopicSummaryItem } from '../types/topic';

interface TopicCardProps {
  topic: TopicSummaryItem;
  workspaceId: string;
  className?: string;
}

export const TopicCard: React.FC<TopicCardProps> = ({
  topic,
  workspaceId,
  className,
}) => {
  // Format human-friendly cluster badge
  const displayClusterKey = topic.cluster_key.replace(/^cluster_/, 'Cluster #');

  // Format status badge styling
  const renderStatusBadge = () => {
    switch (topic.label_status) {
      case 'approved':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" />
            Approved
          </span>
        );
      case 'reviewed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Sparkles className="w-3 h-3" />
            Reviewed
          </span>
        );
      case 'needs_review':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertCircle className="w-3 h-3" />
            Needs Review
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-primary/10 text-primary border border-primary/20">
            <Clock className="w-3 h-3" />
            Suggested
          </span>
        );
    }
  };

  return (
    <Card
      className={cn(
        'group relative flex flex-col justify-between rounded-xl border border-border bg-surface hover:border-primary/40 hover:shadow-sm transition-colors duration-200 overflow-hidden p-5',
        className
      )}
    >
      <div className="space-y-3.5">
        {/* Header Badges */}
        <div className="flex items-center justify-between gap-2">
          <Badge
            variant="outline"
            className="text-[11px] font-mono font-medium text-text-muted bg-surface-muted/50 border-border/80"
          >
            {displayClusterKey}
          </Badge>
          {renderStatusBadge()}
        </div>

        {/* Topic Title & Description */}
        <div>
          <Link
            to={`/app/workspaces/${encodeURIComponent(workspaceId)}/topics/${encodeURIComponent(topic.id)}`}
            className="text-base sm:text-lg font-semibold text-text-primary group-hover:text-primary transition-colors line-clamp-2 block focus:outline-none focus:underline"
            title={topic.label}
          >
            {topic.label}
          </Link>
          <p className="text-xs text-text-secondary mt-1.5 line-clamp-2 leading-relaxed min-h-[32px]">
            {topic.description || 'Discovered thematic grouping from workspace document content.'}
          </p>
        </div>

        {/* Ranked Keyword Chips */}
        {topic.keywords && topic.keywords.length > 0 && (
          <div className="space-y-1.5 pt-1">
            <div className="flex flex-wrap gap-1.5">
              {topic.keywords.slice(0, 4).map((kw, idx) => (
                <span
                  key={`${kw.term}-${idx}`}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] bg-surface-muted text-text-secondary border border-border/60 hover:text-text-primary transition-colors"
                >
                  <span className="font-medium">{kw.term}</span>
                  <span className="text-[9px] text-text-muted font-mono opacity-80">
                    {(kw.score * 100).toFixed(0)}%
                  </span>
                </span>
              ))}
              {topic.keywords.length > 4 && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] text-text-muted bg-surface-muted/40">
                  +{topic.keywords.length - 4} more
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer Provenance Metrics & Action Link */}
      <div className="mt-5 pt-3.5 border-t border-border/60 flex items-center justify-between">
        <div className="flex items-center gap-3.5 text-xs text-text-muted">
          <div className="flex items-center gap-1.5" title="Assigned document chunks">
            <FileText className="w-3.5 h-3.5 text-primary/70" />
            <span className="font-medium text-text-secondary">{topic.chunk_count}</span>
            <span>{topic.chunk_count === 1 ? 'chunk' : 'chunks'}</span>
          </div>
          <div className="flex items-center gap-1.5" title="Contributing documents">
            <Files className="w-3.5 h-3.5 text-accent/70" />
            <span className="font-medium text-text-secondary">{topic.document_count}</span>
            <span>{topic.document_count === 1 ? 'doc' : 'docs'}</span>
          </div>
        </div>

        <Link
          to={`/app/workspaces/${encodeURIComponent(workspaceId)}/topics/${encodeURIComponent(topic.id)}`}
          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-primary-hover group-hover:translate-x-0.5 transition-all"
          aria-label={`Explore topic ${topic.label}`}
        >
          <span>Explore</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </Card>
  );
};
