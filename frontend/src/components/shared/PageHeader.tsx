import React from 'react';
import { cn } from '@/lib/utils';

interface PageHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  breadcrumbs?: React.ReactNode;
  className?: string;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  action,
  breadcrumbs,
  className,
}) => {
  return (
    <div className={cn('page-heading mb-6 sm:mb-8 space-y-2', className)}>
      {breadcrumbs && <div className="text-xs text-text-muted mb-1">{breadcrumbs}</div>}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-text-primary">
            {title}
          </h1>
          {description && (
            <p className="text-sm text-text-secondary mt-1 max-w-2xl leading-relaxed">
              {description}
            </p>
          )}
        </div>
        {action && <div className="flex flex-wrap items-center gap-3 shrink-0">{action}</div>}
      </div>
    </div>
  );
};
