import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Compass } from 'lucide-react';
import { Button } from '@/components/ui/button';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="flex min-h-[calc(100dvh-4rem)] flex-col items-center justify-center p-6 text-center bg-background text-text-primary">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-muted border border-border text-primary mb-6">
        <Compass className="h-8 w-8" />
      </div>
      <h1 className="text-3xl font-bold tracking-tight mb-2">Page Not Found</h1>
      <p className="text-sm text-text-secondary max-w-md mb-6 leading-relaxed">
        The route you requested could not be located in Knovera. Return to your dashboard to continue your research.
      </p>
      <div className="flex flex-wrap justify-center items-center gap-3">
        <Link to="/app">
          <Button variant="default" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            <span>Return to Dashboard</span>
          </Button>
        </Link>
        <Link to="/">
          <Button variant="outline">Knovera Home</Button>
        </Link>
      </div>
    </div>
  );
};
