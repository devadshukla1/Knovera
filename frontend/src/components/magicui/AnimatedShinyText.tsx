import React from 'react';
import { cn } from '@/lib/utils';

interface AnimatedShinyTextProps {
  children: React.ReactNode;
  className?: string;
  shimmerWidth?: number;
}

export const AnimatedShinyText: React.FC<AnimatedShinyTextProps> = ({
  children,
  className,
  shimmerWidth = 100,
}) => {
  return (
    <span
      style={
        {
          '--shimmer-width': `${shimmerWidth}px`,
        } as React.CSSProperties
      }
      className={cn(
        'mx-auto max-w-md text-neutral-400/80',
        'animate-shimmer bg-clip-text bg-no-repeat [background-position:0_0] [background-size:var(--shimmer-width)_100%]',
        'bg-gradient-to-r from-transparent via-white/80 via-50% to-transparent dark:via-white/90',
        className
      )}
    >
      {children}
    </span>
  );
};
