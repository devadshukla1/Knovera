import React from 'react';
import { Moon, Sun, Monitor } from 'lucide-react';
import { useTheme } from '@/context/ThemeContext';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export const ThemeToggle: React.FC<{ className?: string }> = ({ className }) => {
  const { theme, resolvedTheme, setTheme } = useTheme();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={className}
          aria-label="Toggle theme"
          title={`Current theme: ${theme} (showing ${resolvedTheme})`}
        >
          {resolvedTheme === 'dark' ? (
            <Moon className="h-4 w-4 text-primary" />
          ) : (
            <Sun className="h-4 w-4 text-warning" />
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-36">
        <DropdownMenuItem
          onClick={() => setTheme('light')}
          className="flex items-center gap-2"
        >
          <Sun className="h-4 w-4 text-warning" />
          <span>Light</span>
          {theme === 'light' && <span className="ml-auto text-xs text-primary font-bold">✓</span>}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme('dark')}
          className="flex items-center gap-2"
        >
          <Moon className="h-4 w-4 text-primary" />
          <span>Dark</span>
          {theme === 'dark' && <span className="ml-auto text-xs text-primary font-bold">✓</span>}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme('system')}
          className="flex items-center gap-2"
        >
          <Monitor className="h-4 w-4 text-text-muted" />
          <span>System</span>
          {theme === 'system' && <span className="ml-auto text-xs text-primary font-bold">✓</span>}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
