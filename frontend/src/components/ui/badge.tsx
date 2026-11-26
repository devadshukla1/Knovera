import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-md px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 select-none',
  {
    variants: {
      variant: {
        default:
          'bg-primary/15 text-primary border border-primary/30 shadow-sm',
        glow:
          'bg-primary/20 text-primary border border-primary/40 shadow-glow-sm',
        secondary:
          'bg-surface-muted text-text-secondary border border-border',
        outline:
          'text-text-primary border border-border bg-surface/40',
        success:
          'bg-success/15 text-success border border-success/30',
        warning:
          'bg-warning/15 text-warning border border-warning/30',
        danger:
          'bg-danger/15 text-danger border border-danger/30',
        info:
          'bg-info/15 text-info border border-info/30',
        accent:
          'bg-accent/15 text-accent border border-accent/30',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
