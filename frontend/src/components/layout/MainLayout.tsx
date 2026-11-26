import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { AppSidebar } from './AppSidebar';
import { AppHeader } from './AppHeader';
import { WorkspaceProvider } from '@/features/workspaces/context/WorkspaceContext';

export const MainLayout: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();

  // Derive active page title based on path
  const getPageTitle = (path: string) => {
    if (path === '/app') return 'Overview';
    if (path === '/app/workspaces') return 'Workspaces';
    if (path.includes('/documents')) return 'Document Library';
    if (path.includes('/chat')) return 'Research Chat';
    if (path.startsWith('/app/workspaces/')) return 'Workspace Details';
    if (path === '/app/settings') return 'Settings';
    return '';
  };

  return (
    <WorkspaceProvider>
      <div className="app-shell flex min-h-screen bg-background text-text-primary antialiased">
        <a href="#main-content" className="skip-link">Skip to content</a>
        {/* Sidebar (desktop fixed / mobile drawer) */}
        <AppSidebar
          isOpen={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
        />

        {/* Main Content Area */}
        <div className="flex flex-1 flex-col min-w-0">
          <AppHeader
            title={getPageTitle(location.pathname)}
            onOpenMobileMenu={() => setMobileMenuOpen(true)}
          />
          <main id="main-content" tabIndex={-1} className="app-main flex-1 overflow-y-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </WorkspaceProvider>
  );
};
