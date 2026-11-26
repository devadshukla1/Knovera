import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  isRetrying?: boolean;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Something went wrong',
  message,
  onRetry,
  isRetrying = false,
  className,
}) => {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center p-8 rounded-xl border border-danger/30 bg-danger/5 max-w-lg mx-auto',
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-danger/10 text-danger mb-4 border border-danger/20">
        <AlertCircle className="h-6 w-6" />
      </div>
      <h3 className="text-base font-semibold text-text-primary mb-1.5">{title}</h3>
      <p className="text-sm text-text-secondary max-w-sm leading-relaxed mb-5">
        {message}
      </p>
      {onRetry && (
        <Button
          onClick={onRetry}
          disabled={isRetrying}
          variant="secondary"
          size="sm"
          className="gap-2"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', isRetrying && 'animate-spin')} />
          <span>{isRetrying ? 'Retrying...' : 'Retry Request'}</span>
        </Button>
      )}
    </div>
  );
};
