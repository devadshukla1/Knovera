import React from 'react';
import { cn } from '@/lib/utils';

interface PageContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  maxWidth?: 'full' | '7xl' | '6xl' | '5xl';
}

export const PageContainer: React.FC<PageContainerProps> = ({
  children,
  maxWidth = '7xl',
  className,
  ...props
}) => {
  const maxWidthClass = {
    full: 'max-w-full',
    '7xl': 'max-w-7xl',
    '6xl': 'max-w-6xl',
    '5xl': 'max-w-5xl',
  }[maxWidth];

  return (
    <div
      className={cn(
        'page-container mx-auto w-full p-4 sm:p-7 lg:p-8 xl:px-10',
        maxWidthClass,
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};
