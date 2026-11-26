import React, { createContext, useContext, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useWorkspaces, useWorkspace } from '../hooks/useWorkspaces';
import { Workspace } from '../types/workspace';

interface WorkspaceContextValue {
  activeWorkspaceId: string | null;
  activeWorkspace: Workspace | null;
  workspaces: Workspace[];
  isLoading: boolean;
  setActiveWorkspaceId: (workspaceId: string) => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

const ACTIVE_WORKSPACE_STORAGE_KEY = 'knovera_active_workspace_id';

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const { workspaceId: paramWorkspaceId } = useParams<{ workspaceId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const { data: workspaces = [], isLoading: isListLoading } = useWorkspaces();

  // Auto-heal stale workspace URLs: if paramWorkspaceId doesn't exist in loaded workspaces, redirect safely
  React.useEffect(() => {
    if (!isListLoading && workspaces.length > 0 && paramWorkspaceId) {
      const exists = workspaces.some((w) => w.id === paramWorkspaceId.trim());
      if (!exists) {
        const fallbackId = workspaces[0].id;
        try {
          localStorage.setItem(ACTIVE_WORKSPACE_STORAGE_KEY, fallbackId);
        } catch {
          // ignore
        }
        // Redirect current view to the fallback valid workspace
        const currentPath = location.pathname;
        if (currentPath.includes('/chat')) {
          navigate(`/app/workspaces/${encodeURIComponent(fallbackId)}/chat`, { replace: true });
        } else if (currentPath.includes('/documents')) {
          navigate(`/app/workspaces/${encodeURIComponent(fallbackId)}/documents`, { replace: true });
        } else if (currentPath.includes('/knowledge-graph')) {
          navigate(`/app/workspaces/${encodeURIComponent(fallbackId)}/knowledge-graph`, { replace: true });
        } else {
          navigate(`/app/workspaces/${encodeURIComponent(fallbackId)}`, { replace: true });
        }
      }
    }
  }, [isListLoading, workspaces, paramWorkspaceId, location.pathname, navigate]);

  // If URL has workspaceId, use it and persist; otherwise fallback to stored workspace or first available
  const activeWorkspaceId = useMemo(() => {
    if (paramWorkspaceId && paramWorkspaceId.trim().length > 0) {
      if (!isListLoading && workspaces.length > 0) {
        const found = workspaces.some((w) => w.id === paramWorkspaceId.trim());
        if (!found) {
          return workspaces[0].id;
        }
      }
      try {
        localStorage.setItem(ACTIVE_WORKSPACE_STORAGE_KEY, paramWorkspaceId.trim());
      } catch {
        // ignore localStorage errors
      }
      return paramWorkspaceId.trim();
    }

    try {
      const storedId = localStorage.getItem(ACTIVE_WORKSPACE_STORAGE_KEY);
      if (storedId && workspaces.some((w) => w.id === storedId)) {
        return storedId;
      }
    } catch {
      // ignore localStorage errors
    }

    if (workspaces.length > 0) {
      return workspaces[0].id;
    }

    return null;
  }, [paramWorkspaceId, workspaces]);

  const { data: activeWorkspaceData, isLoading: isDetailLoading } = useWorkspace(
    activeWorkspaceId || '',
    { retry: false }
  );

  // If the active workspace is already in the list, use it; otherwise use the fetched detail
  const activeWorkspace = useMemo(() => {
    if (!activeWorkspaceId) return null;
    const found = workspaces.find((w) => w.id === activeWorkspaceId);
    return found || activeWorkspaceData || null;
  }, [activeWorkspaceId, workspaces, activeWorkspaceData]);

  const setActiveWorkspaceId = (newId: string) => {
    try {
      localStorage.setItem(ACTIVE_WORKSPACE_STORAGE_KEY, newId);
    } catch {
      // ignore
    }
    // If currently on a workspace-scoped path, redirect to corresponding path with new ID
    if (location.pathname.includes('/documents')) {
      navigate(`/app/workspaces/${encodeURIComponent(newId)}/documents`);
    } else if (location.pathname.includes('/chat')) {
      navigate(`/app/workspaces/${encodeURIComponent(newId)}/chat`);
    } else if (location.pathname.includes('/topics')) {
      navigate(`/app/workspaces/${encodeURIComponent(newId)}/topics`);
    } else if (location.pathname.includes('/knowledge-graph')) {
      navigate(`/app/workspaces/${encodeURIComponent(newId)}/knowledge-graph`);
    } else if (location.pathname.includes('/study-studio')) {
      navigate(`/app/workspaces/${encodeURIComponent(newId)}/study-studio`);
    } else if (location.pathname.includes('/learning-analytics')) {
      navigate(`/app/workspaces/${encodeURIComponent(newId)}/learning-analytics`);
    } else if (location.pathname.includes('/research-intelligence')) {
      navigate(`/app/workspaces/${encodeURIComponent(newId)}/research-intelligence`);
    } else {
      navigate(`/app/workspaces/${encodeURIComponent(newId)}`);
    }
  };

  const value = useMemo(
    () => ({
      activeWorkspaceId,
      activeWorkspace,
      workspaces,
      isLoading: isListLoading || isDetailLoading,
      setActiveWorkspaceId,
    }),
    [activeWorkspaceId, activeWorkspace, workspaces, isListLoading, isDetailLoading]
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
};

export function useWorkspaceContext(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) {
    return {
      activeWorkspaceId: null,
      activeWorkspace: null,
      workspaces: [],
      isLoading: false,
      setActiveWorkspaceId: () => {},
    };
  }
  return context;
}
