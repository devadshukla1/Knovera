import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Menu, Sparkles, User, ChevronRight, MessageSquare, UploadCloud, FolderKanban } from 'lucide-react';
import { ThemeToggle } from '@/components/shared/ThemeToggle';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useWorkspaceContext } from '@/features/workspaces/context/WorkspaceContext';

interface AppHeaderProps {
  onOpenMobileMenu?: () => void;
  title?: string;
}

export const AppHeader: React.FC<AppHeaderProps> = ({
  onOpenMobileMenu,
  title,
}) => {
  const location = useLocation();
  const { activeWorkspaceId, activeWorkspace } = useWorkspaceContext();

  // Generate breadcrumb items from location path
  const renderBreadcrumbs = () => {
    const path = location.pathname;

    if (path === '/app' || path === '/app/dashboard') {
      return (
        <div className="flex items-center gap-1.5 text-xs text-text-muted">
          <span className="font-semibold text-text-primary text-sm">Dashboard</span>
        </div>
      );
    }

    if (path === '/app/workspaces') {
      return (
        <div className="flex items-center gap-1.5 text-xs text-text-muted">
          <Link to="/app" className="hover:text-text-primary transition-colors">Home</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-text-primary text-sm">Workspaces</span>
        </div>
      );
    }

    if (path === '/app/settings') {
      return (
        <div className="flex items-center gap-1.5 text-xs text-text-muted">
          <Link to="/app" className="hover:text-text-primary transition-colors">Home</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-text-primary text-sm">Settings</span>
        </div>
      );
    }

    if (path.includes('/workspaces/') && activeWorkspace) {
      let subPage = 'Overview';
      if (path.includes('/documents')) subPage = 'Document Library';
      else if (path.includes('/chat')) subPage = 'Research Chat';
      else if (path.includes('/study-studio')) subPage = 'Study Studio';
      else if (path.includes('/learning-analytics')) subPage = 'Learning Analytics';
      else if (path.includes('/knowledge-graph')) subPage = 'Knowledge Graph';
      else if (path.includes('/topics')) subPage = 'Topics';

      return (
        <div className="flex items-center gap-1.5 text-xs text-text-muted truncate">
          <Link to="/app/workspaces" className="hover:text-text-primary transition-colors hidden sm:inline">
            Workspaces
          </Link>
          <ChevronRight className="h-3 w-3 hidden sm:inline" />
          <Link
            to={`/app/workspaces/${encodeURIComponent(activeWorkspace.id)}`}
            className="hover:text-text-primary transition-colors truncate max-w-[140px] sm:max-w-[200px]"
            title={activeWorkspace.name}
          >
            {activeWorkspace.name}
          </Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-text-primary text-sm truncate">{subPage}</span>
        </div>
      );
    }

    return (
      <h2 className="text-sm sm:text-base font-semibold text-text-primary truncate">
        {title || 'Knovera'}
      </h2>
    );
  };

  const wsPrefix = activeWorkspaceId
    ? `/app/workspaces/${encodeURIComponent(activeWorkspaceId)}`
    : null;

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full shrink-0 items-center justify-between border-b border-border/80 bg-background px-4 sm:px-7">
      <div className="flex items-center gap-3 min-w-0">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onOpenMobileMenu}
          className="lg:hidden text-text-secondary"
          aria-label="Open navigation drawer"
        >
          <Menu className="h-5 w-5" />
        </Button>

        {/* Dynamic Breadcrumbs */}
        <div className="min-w-0">
          {renderBreadcrumbs()}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        {/* Contextual Quick Actions */}
        {wsPrefix && !location.pathname.includes('/chat') && (
          <Link to={`${wsPrefix}/chat`} className="hidden md:inline-flex">
            <Button variant="subtle" size="sm" className="gap-1.5 h-8 text-xs">
              <MessageSquare className="h-3.5 w-3.5" />
              <span>Research Chat</span>
            </Button>
          </Link>
        )}

        {wsPrefix && !location.pathname.includes('/documents') && (
          <Link to={`${wsPrefix}/documents`} className="hidden lg:inline-flex">
            <Button variant="outline" size="sm" className="gap-1.5 h-8 text-xs">
              <UploadCloud className="h-3.5 w-3.5 text-accent" />
              <span>Documents</span>
            </Button>
          </Link>
        )}

        {/* Theme Toggle */}
        <ThemeToggle />

        {/* User Account Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="secondary"
              size="sm"
              aria-label="Researcher menu"
              className="gap-2 rounded-lg px-2.5 sm:px-3 py-1 h-8 text-xs font-medium border-border/80 hover:border-primary/40 transition-all"
            >
              <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/20 text-primary">
                <User className="h-3.5 w-3.5" />
              </div>
              <span className="hidden sm:inline text-text-primary font-medium">Researcher</span>
              <span className="h-1.5 w-1.5 rounded-full bg-success"></span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56 p-1.5 bg-surface-elevated/95 backdrop-blur-xl border-border">
            <DropdownMenuLabel className="font-normal px-2 py-1.5">
              <div className="flex flex-col space-y-0.5">
                <p className="text-sm font-semibold text-text-primary">Researcher Workspace</p>
                <p className="text-xs text-text-muted">Personal Knowledge Intelligence</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator className="bg-border/60" />
            <DropdownMenuItem asChild>
              <Link to="/app/workspaces" className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer">
                <FolderKanban className="h-3.5 w-3.5 text-primary" />
                <span>All Workspaces</span>
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link to="/app/settings" className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer">
                <Sparkles className="h-3.5 w-3.5 text-accent" />
                <span>AI Model & Settings</span>
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
};
