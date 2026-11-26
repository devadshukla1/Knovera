import React from 'react';
import { Skeleton } from '@/components/ui/skeleton';

export const LoadingFallback: React.FC = () => (
  <div className="p-6 space-y-4 max-w-7xl mx-auto w-full" data-testid="route-loading-fallback">
    <div className="flex items-center justify-between pb-4 border-b border-border/40">
      <Skeleton className="h-8 w-48 rounded" />
      <Skeleton className="h-9 w-32 rounded" />
    </div>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
      <Skeleton className="h-28 rounded-lg" />
      <Skeleton className="h-28 rounded-lg" />
      <Skeleton className="h-28 rounded-lg" />
    </div>
    <div className="space-y-3 pt-4">
      <Skeleton className="h-6 w-full rounded" />
      <Skeleton className="h-6 w-5/6 rounded" />
      <Skeleton className="h-6 w-4/6 rounded" />
    </div>
  </div>
);

export function withSuspense<P extends object>(
  Component: React.ComponentType<P>
): React.FC<P> {
  return function SuspenseWrapped(props: P) {
    return (
      <React.Suspense fallback={<LoadingFallback />}>
        <Component {...props} />
      </React.Suspense>
    );
  };
}
