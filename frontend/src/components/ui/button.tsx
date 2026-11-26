import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'ui-button inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer active:scale-[0.98]',
  {
    variants: {
      variant: {
        default:
          'bg-primary text-primary-foreground shadow-sm hover:bg-primary-hover',
        glow:
          'bg-primary text-primary-foreground font-semibold shadow-sm hover:bg-primary-hover border border-transparent',
        subtle:
          'bg-primary/10 text-primary border border-primary/25 hover:bg-primary/20 hover:border-primary/40',
        destructive:
          'bg-danger text-white shadow-sm hover:bg-danger/90 hover:shadow-sm',
        outline:
          'border border-border bg-surface/50 text-text-primary hover:bg-surface-muted hover:border-border-highlight hover:text-text-primary ',
        secondary:
          'bg-surface-muted text-text-primary border border-border/60 hover:bg-surface-elevated hover:border-border hover:shadow-sm',
        ghost:
          'text-text-secondary hover:bg-surface-muted hover:text-text-primary',
        link: 'text-primary underline-offset-4 hover:underline p-0 h-auto font-normal active:scale-100',
        accent:
          'bg-accent text-slate-950 font-semibold shadow-glow-teal hover:bg-accent/90',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-11 rounded-lg px-6 text-base font-semibold',
        icon: 'h-9 w-9 p-0',
        'icon-sm': 'h-8 w-8 p-0 rounded-md',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
