import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';

interface LoadingStateProps {
  message?: string;
  variant?: 'spinner' | 'skeleton-cards' | 'skeleton-list';
  count?: number;
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading data...',
  variant = 'spinner',
  count = 3,
  className,
}) => {
  if (variant === 'skeleton-cards') {
    return (
      <div className={cn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5', className)}>
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className="flex flex-col rounded-xl border border-border bg-surface p-5 space-y-4 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-5 w-12 rounded-full" />
            </div>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
            <div className="pt-4 border-t border-border flex justify-between items-center">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-8 w-20 rounded-md" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (variant === 'skeleton-list') {
    return (
      <div className={cn('space-y-3', className)}>
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className="flex items-center justify-between rounded-lg border border-border bg-surface p-4"
          >
            <div className="space-y-2 w-1/2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
            <Skeleton className="h-8 w-24 rounded-md" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center p-12 text-center text-text-muted space-y-3',
        className
      )}
    >
      <Loader2 className="h-7 w-7 animate-spin text-primary" />
      <p className="text-sm text-text-secondary">{message}</p>
    </div>
  );
};
