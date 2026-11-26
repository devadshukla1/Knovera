import React from 'react';
import {
  Clock,
  Loader2,
  Layers,
  Database,
  CheckCircle2,
  AlertCircle,
  Trash2,
} from 'lucide-react';
import { Badge, type BadgeProps } from '@/components/ui/badge';
import { DocumentStatus } from '../types/document';
import { cn } from '@/lib/utils';

interface DocumentStatusBadgeProps {
  status: DocumentStatus;
  className?: string;
}

export const DocumentStatusBadge: React.FC<DocumentStatusBadgeProps> = ({
  status,
  className,
}) => {
  let variant: BadgeProps['variant'] = 'secondary';
  let label: string = status;
  let Icon = Clock;
  let isSpinning = false;

  switch (status) {
    case 'queued':
      variant = 'secondary';
      label = 'Queued';
      Icon = Clock;
      break;
    case 'extracting':
      variant = 'info';
      label = 'Extracting';
      Icon = Loader2;
      isSpinning = true;
      break;
    case 'chunking':
      variant = 'info';
      label = 'Chunking';
      Icon = Layers;
      break;
    case 'indexing':
      variant = 'warning';
      label = 'Indexing';
      Icon = Database;
      break;
    case 'ready':
      variant = 'success';
      label = 'Ready';
      Icon = CheckCircle2;
      break;
    case 'failed':
      variant = 'danger';
      label = 'Failed';
      Icon = AlertCircle;
      break;
    case 'deleting':
      variant = 'danger';
      label = 'Deleting';
      Icon = Trash2;
      break;
  }

  return (
    <Badge
      variant={variant}
      className={cn('capitalize text-[11px] font-medium py-0.5 px-2 gap-1.5', className)}
    >
      <Icon className={cn('h-3 w-3 shrink-0', isSpinning && 'animate-spin')} />
      <span>{label}</span>
    </Badge>
  );
};
