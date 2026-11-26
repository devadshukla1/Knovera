import React, { useEffect, useState } from 'react';
import { Sparkles, Search, BrainCircuit, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ThinkingBubbleProps {
  className?: string;
}

interface ThinkingStep {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  minDurationMs: number;
}

const STEPS: ThinkingStep[] = [
  {
    label: 'Understanding your question...',
    icon: BrainCircuit,
    minDurationMs: 1400,
  },
  {
    label: 'Searching your workspace knowledge...',
    icon: Search,
    minDurationMs: 1800,
  },
  {
    label: 'Analyzing relevant information...',
    icon: FileText,
    minDurationMs: 1800,
  },
  {
    label: 'Preparing your answer...',
    icon: Sparkles,
    minDurationMs: 2000,
  },
];

export const ThinkingBubble: React.FC<ThinkingBubbleProps> = ({ className }) => {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);

  useEffect(() => {
    let timer: NodeJS.Timeout;

    if (currentStepIndex < STEPS.length - 1) {
      const duration = STEPS[currentStepIndex].minDurationMs;
      timer = setTimeout(() => {
        setCurrentStepIndex((prev) => Math.min(prev + 1, STEPS.length - 1));
      }, duration);
    }

    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [currentStepIndex]);

  const currentStep = STEPS[currentStepIndex];
  const StepIcon = currentStep.icon;

  return (
    <div
      className={cn(
        'flex gap-3 max-w-2xl animate-in fade-in slide-in-from-bottom-2 duration-300',
        className
      )}
      role="status"
      aria-live="polite"
    >
      {/* Knovera AI Avatar with breathing pulse ring */}
      <div className="relative shrink-0 flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft border border-primary/40 text-primary shadow-glow-sm">
        <Sparkles className="h-4 w-4 animate-pulse motion-reduce:animate-none" />

      </div>

      {/* Main Thinking Surface Card */}
      <div className="flex-1 rounded-2xl rounded-tl-sm border border-primary/20 bg-surface-elevated/90 p-4 shadow-sm space-y-3">
        {/* Active Stage Indicator */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs font-medium text-text-primary">
            <StepIcon className="h-3.5 w-3.5 text-primary animate-spin motion-reduce:animate-none duration-1000" />
            <span className="tracking-tight">{currentStep.label}</span>
          </div>

          {/* Animated 3-Dot Processing Indicator */}
          <div className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce [animation-delay:-0.3s] motion-reduce:animate-none" />
            <span className="h-1.5 w-1.5 rounded-full bg-primary/80 animate-bounce [animation-delay:-0.15s] motion-reduce:animate-none" />
            <span className="h-1.5 w-1.5 rounded-full bg-primary/60 animate-bounce motion-reduce:animate-none" />
          </div>
        </div>

        {/* Step Progress Pills */}
        <div className="grid grid-cols-4 gap-1.5 pt-1">
          {STEPS.map((step, idx) => {
            const isCompleted = idx < currentStepIndex;
            const isCurrent = idx === currentStepIndex;

            return (
              <div
                key={step.label}
                className={cn(
                  'h-1 rounded-full transition-all duration-500',
                  isCompleted
                    ? 'bg-primary'
                    : isCurrent
                    ? 'bg-gradient-to-r from-primary to-accent-purple animate-pulse'
                    : 'bg-border/60'
                )}
                title={step.label}
              />
            );
          })}
        </div>

        {/* Shimmering Placeholder Lines */}
        <div className="space-y-2 pt-1">
          <div className="h-2.5 w-3/4 rounded-full bg-gradient-to-r from-surface-muted via-surface-muted/50 to-surface-muted animate-pulse motion-reduce:animate-none" />
          <div className="h-2.5 w-1/2 rounded-full bg-gradient-to-r from-surface-muted via-surface-muted/50 to-surface-muted animate-pulse motion-reduce:animate-none [animation-delay:150ms]" />
        </div>
      </div>
    </div>
  );
};
