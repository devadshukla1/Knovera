import React, { useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  FolderKanban,
  FileText,
  MessageSquare,
  Network,
  GraduationCap,
  LineChart,
  Settings,
  Sparkles,
  X,
  Bot,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { useWorkspaceContext } from '@/features/workspaces/context/WorkspaceContext';
import { WorkspaceSwitcher } from '@/features/workspaces/components/WorkspaceSwitcher';

interface AppSidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
  className?: string;
}

interface NavItem {
  name: string;
  href: string;
  icon: React.ElementType;
  isAvailable: boolean;
  phaseLabel?: string;
  badge?: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

export const AppSidebar: React.FC<AppSidebarProps> = ({
  isOpen = true,
  onClose,
  className,
}) => {
  const { activeWorkspaceId } = useWorkspaceContext();
  const location = useLocation();
  const sidebarRef = useRef<HTMLElement>(null);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 1024);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 1023px)');
    const update = () => setIsMobile(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (!isMobile || !isOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const sidebar = sidebarRef.current;
    const focusable = () => Array.from(sidebar?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex="0"]') ?? []);
    focusable()[0]?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose?.(); }
      if (event.key !== 'Tab') return;
      const items = focusable();
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', trap);
    return () => { document.removeEventListener('keydown', trap); previous?.focus(); };
  }, [isMobile, isOpen, onClose]);

  const navSections: NavSection[] = useMemo(() => {
    const wsPrefix = activeWorkspaceId
      ? `/app/workspaces/${encodeURIComponent(activeWorkspaceId)}`
      : null;

    return [
      {
        title: 'Overview',
        items: [
          {
            name: 'Dashboard',
            href: '/app',
            icon: LayoutDashboard,
            isAvailable: true,
          },
          {
            name: 'All Workspaces',
            href: '/app/workspaces',
            icon: FolderKanban,
            isAvailable: true,
          },
        ],
      },
      {
        title: 'Knowledge Intelligence',
        items: [
          {
            name: 'Document Library',
            href: wsPrefix ? `${wsPrefix}/documents` : '/app/workspaces',
            icon: FileText,
            isAvailable: true,
          },
          {
            name: 'Research Chat',
            href: wsPrefix ? `${wsPrefix}/chat` : '/app/workspaces',
            icon: MessageSquare,
            isAvailable: true,
            badge: 'AI',
          },
          {
            name: 'Knowledge Graph',
            href: wsPrefix ? `${wsPrefix}/knowledge-graph` : '/app/workspaces',
            icon: Network,
            isAvailable: true,
          },
        ],
      },
      {
        title: 'Learning Studio',
        items: [
          {
            name: 'Study Studio',
            href: wsPrefix ? `${wsPrefix}/study-studio` : '/app/workspaces',
            icon: GraduationCap,
            isAvailable: true,
          },
          {
            name: 'Learning Analytics',
            href: wsPrefix ? `${wsPrefix}/learning-analytics` : '/app/workspaces',
            icon: LineChart,
            isAvailable: true,
          },
        ],
      },
      {
        title: 'System',
        items: [
          {
            name: 'Settings',
            href: '/app/settings',
            icon: Settings,
            isAvailable: true,
          },
        ],
      },
    ];
  }, [activeWorkspaceId]);

  return (
    <>
      {/* Mobile backdrop */}
      <div
        className={cn(
          'fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity lg:hidden',
          isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        )}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Sidebar container */}
      <aside
        ref={sidebarRef}
        role={isMobile && isOpen ? 'dialog' : undefined}
        aria-modal={isMobile && isOpen ? true : undefined}
        aria-label="Main navigation"
        {...(isMobile && !isOpen ? { inert: '' } : {})}
        className={cn(
          'fixed top-0 bottom-0 left-0 z-50 flex w-64 flex-col border-r border-border bg-surface transition-transform duration-200 ease-out lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0 shrink-0',
          isOpen ? 'translate-x-0' : '-translate-x-full',
          className
        )}
      >
        {/* Brand Header */}
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-border/80 px-5">
          <NavLink to="/" className="flex items-center gap-3 group">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-transform group-hover:scale-105">
              <Sparkles className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="text-lg font-semibold tracking-tight text-text-primary">
                  Knovera
                </span>
                <span className="inline-block px-1.5 py-0.2 text-[9px] font-semibold bg-primary/20 text-primary rounded border border-primary/30 uppercase tracking-wider">
                  AI
                </span>
              </div>
              <span className="text-[11px] text-text-muted font-normal leading-none mt-0.5">
                Knowledge Intelligence
              </span>
            </div>
          </NavLink>
          {onClose && (
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-text-muted hover:bg-surface-muted hover:text-text-primary lg:hidden transition-colors"
              aria-label="Close navigation"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {/* Active Workspace Switcher */}
        <div className="px-4 pt-4 pb-2">
          <label className="block text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1.5 px-1">
            Active Workspace
          </label>
          <WorkspaceSwitcher className="w-full shadow-sm" />
        </div>

        {/* Navigation Sections */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-5">
          {navSections.map((section) => (
            <div key={section.title} className="space-y-1">
              <h4 className="px-3 text-[10px] font-semibold tracking-wider text-text-muted/80 uppercase">
                {section.title}
              </h4>
              <nav className="space-y-0.5 pt-1" aria-label={section.title}>
                {section.items.map((item) => {
                  const Icon = item.icon;
                  if (!item.isAvailable) {
                    return (
                      <div
                        key={item.name}
                        className="flex items-center justify-between rounded-lg px-3 py-2 text-xs font-medium text-text-muted/60 cursor-not-allowed select-none"
                      >
                        <div className="flex items-center gap-3">
                          <Icon className="h-4 w-4 shrink-0 text-text-muted/40" />
                          <span>{item.name}</span>
                        </div>
                        {item.phaseLabel && (
                          <Badge
                            variant="secondary"
                            className="text-[10px] py-0 px-1.5 opacity-60 font-mono"
                          >
                            {item.phaseLabel}
                          </Badge>
                        )}
                      </div>
                    );
                  }

                  return (
                    <NavLink
                      key={item.name}
                      to={item.href}
                      end={item.href === '/app' || item.href === '/app/workspaces'}
                      onClick={() => {
                        if (window.innerWidth < 1024 && onClose) {
                          onClose();
                        }
                      }}
                      className={({ isActive }) => {
                        const isCurrentActive =
                          isActive ||
                          (item.href !== '/app' &&
                            item.href !== '/app/workspaces' &&
                            location.pathname.startsWith(item.href));
                        return cn(
                          'group flex items-center justify-between rounded-lg px-3 py-2.5 text-[13px] font-medium transition-colors duration-150 border border-transparent',
                          isCurrentActive
                            ? 'bg-primary-soft text-primary font-semibold !border-border-highlight'
                            : 'text-text-secondary hover:bg-surface-elevated hover:text-text-primary'
                        );
                      }}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <Icon className="h-4 w-4 shrink-0" />
                        <span className="truncate">{item.name}</span>
                      </div>
                      {item.badge && (
                        <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-accent/15 text-accent border border-accent/25">
                          {item.badge}
                        </span>
                      )}
                    </NavLink>
                  );
                })}
              </nav>
            </div>
          ))}
        </div>

        {/* Bottom AI Status Card */}
        <div className="border-t border-border/80 p-3 bg-surface/50">
          <div className="rounded-xl border border-border/80 bg-surface-muted/60 p-3 text-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-medium text-text-primary">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/20 text-primary">
                  <Bot className="h-3.5 w-3.5" />
                </div>
                <div className="flex flex-col">
                  <span className="text-[11px] font-semibold text-text-primary leading-tight">
                    Your research space
                  </span>
                  <span className="text-[10px] text-text-muted leading-tight">
                    Documents. Ideas. Understanding.
                  </span>
                </div>
              </div>
              <span className="relative flex h-2 w-2">


              </span>
            </div>
            <div className="mt-2.5 pt-2 border-t border-border/40 flex items-center justify-between text-[10px] text-text-muted">
              <span>Knovera v1.0.0</span>
              <NavLink to="/app/settings" className="hover:text-primary transition-colors">
                Settings &rarr;
              </NavLink>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
