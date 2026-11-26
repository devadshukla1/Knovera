import React from 'react';
import { Badge, type BadgeProps } from '@/components/ui/badge';
import { CheckCircle2, AlertCircle, AlertTriangle, Info, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

export type StatusType =
  | 'ready'
  | 'healthy'
  | 'success'
  | 'processing'
  | 'warning'
  | 'error'
  | 'offline'
  | 'planned'
  | 'info';

interface StatusBadgeProps extends Omit<BadgeProps, 'variant'> {
  status: StatusType;
  label?: string;
  showIcon?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  showIcon = true,
  className,
  ...props
}) => {
  let variant: BadgeProps['variant'] = 'default';
  let defaultLabel: string = status;
  let Icon = Info;

  switch (status) {
    case 'ready':
    case 'healthy':
    case 'success':
      variant = 'success';
      defaultLabel = 'Healthy';
      Icon = CheckCircle2;
      break;
    case 'processing':
      variant = 'info';
      defaultLabel = 'Processing';
      Icon = Clock;
      break;
    case 'warning':
      variant = 'warning';
      defaultLabel = 'Degraded';
      Icon = AlertTriangle;
      break;
    case 'error':
    case 'offline':
      variant = 'danger';
      defaultLabel = status === 'offline' ? 'Offline' : 'Error';
      Icon = AlertCircle;
      break;
    case 'planned':
      variant = 'secondary';
      defaultLabel = 'Planned';
      Icon = Clock;
      break;
    case 'info':
    default:
      variant = 'info';
      defaultLabel = 'Info';
      Icon = Info;
      break;
  }

  return (
    <Badge variant={variant} className={cn('capitalize', className)} {...props}>
      {showIcon && <Icon className="h-3 w-3 shrink-0" />}
      <span>{label || defaultLabel}</span>
    </Badge>
  );
};
