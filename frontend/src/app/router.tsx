import { lazy } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { MainLayout } from '@/components/layout/MainLayout';
import { withSuspense } from '@/components/common/LoadingFallback';

// Route-level Code Splitting: Lazy-load all view & feature pages
const LandingView = withSuspense(
  lazy(() => import('@/features/landing/LandingView').then((m) => ({ default: m.LandingView })))
);
const DashboardOverviewPage = withSuspense(
  lazy(() =>
    import('@/features/dashboard/pages/DashboardOverviewPage').then((m) => ({
      default: m.DashboardOverviewPage,
    }))
  )
);
const WorkspacesPage = withSuspense(
  lazy(() =>
    import('@/features/workspaces/pages/WorkspacesPage').then((m) => ({
      default: m.WorkspacesPage,
    }))
  )
);
const WorkspaceDetailPage = withSuspense(
  lazy(() =>
    import('@/features/workspaces/pages/WorkspaceDetailPage').then((m) => ({
      default: m.WorkspaceDetailPage,
    }))
  )
);
const DocumentsPage = withSuspense(
  lazy(() =>
    import('@/features/documents/pages/DocumentsPage').then((m) => ({
      default: m.DocumentsPage,
    }))
  )
);
const DocumentDetailPage = withSuspense(
  lazy(() =>
    import('@/features/documents/pages/DocumentDetailPage').then((m) => ({
      default: m.DocumentDetailPage,
    }))
  )
);
const TopicExplorerPage = withSuspense(
  lazy(() =>
    import('@/features/topics/pages/TopicExplorerPage').then((m) => ({
      default: m.TopicExplorerPage,
    }))
  )
);
const TopicDetailPage = withSuspense(
  lazy(() =>
    import('@/features/topics/pages/TopicDetailPage').then((m) => ({
      default: m.TopicDetailPage,
    }))
  )
);
const KnowledgeGraphPage = withSuspense(
  lazy(() =>
    import('@/features/knowledge-graph/pages/KnowledgeGraphPage').then((m) => ({
      default: m.KnowledgeGraphPage,
    }))
  )
);
const ChatPage = withSuspense(
  lazy(() => import('@/features/chat/pages/ChatPage').then((m) => ({ default: m.ChatPage })))
);
const StudyStudioPage = withSuspense(
  lazy(() =>
    import('@/features/study/pages/StudyStudioPage').then((m) => ({
      default: m.StudyStudioPage,
    }))
  )
);
const QuizSetupPage = withSuspense(
  lazy(() =>
    import('@/features/study/pages/QuizSetupPage').then((m) => ({
      default: m.QuizSetupPage,
    }))
  )
);
const QuizRunnerPage = withSuspense(
  lazy(() =>
    import('@/features/study/pages/QuizRunnerPage').then((m) => ({
      default: m.QuizRunnerPage,
    }))
  )
);
const QuizResultsPage = withSuspense(
  lazy(() =>
    import('@/features/study/pages/QuizResultsPage').then((m) => ({
      default: m.QuizResultsPage,
    }))
  )
);
const LearningAnalyticsPage = withSuspense(
  lazy(() =>
    import('@/features/analytics/pages/LearningAnalyticsPage').then((m) => ({
      default: m.LearningAnalyticsPage,
    }))
  )
);
const SettingsPage = withSuspense(
  lazy(() =>
    import('@/features/settings/pages/SettingsPage').then((m) => ({
      default: m.SettingsPage,
    }))
  )
);
const NotFoundPage = withSuspense(
  lazy(() => import('@/features/error/NotFoundPage').then((m) => ({ default: m.NotFoundPage })))
);

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/app" replace />,
  },
  {
    path: '/landing',
    element: <LandingView />,
  },
  {
    path: '/app',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <DashboardOverviewPage />,
      },
      {
        path: 'dashboard',
        element: <DashboardOverviewPage />,
      },
      {
        path: 'workspaces',
        element: <WorkspacesPage />,
      },
      {
        path: 'workspaces/:workspaceId',
        element: <WorkspaceDetailPage />,
      },
      {
        path: 'workspaces/:workspaceId/documents',
        element: <DocumentsPage />,
      },
      {
        path: 'workspaces/:workspaceId/documents/:documentId',
        element: <DocumentDetailPage />,
      },
      {
        path: 'workspaces/:workspaceId/topics',
        element: <TopicExplorerPage />,
      },
      {
        path: 'workspaces/:workspaceId/topics/:topicId',
        element: <TopicDetailPage />,
      },
      {
        path: 'workspaces/:workspaceId/knowledge-graph',
        element: <KnowledgeGraphPage />,
      },
      {
        path: 'workspaces/:workspaceId/study-studio',
        element: <StudyStudioPage />,
      },
      {
        path: 'workspaces/:workspaceId/study-studio/quiz-setup',
        element: <QuizSetupPage />,
      },
      {
        path: 'workspaces/:workspaceId/study-studio/quiz/:attemptId',
        element: <QuizRunnerPage />,
      },
      {
        path: 'workspaces/:workspaceId/study-studio/quiz/:attemptId/results',
        element: <QuizResultsPage />,
      },
      {
        path: 'workspaces/:workspaceId/learning-analytics',
        element: <LearningAnalyticsPage />,
      },
      {
        path: 'workspaces/:workspaceId/chat',
        element: <ChatPage />,
      },
      {
        path: 'workspaces/:workspaceId/chat/:conversationId',
        element: <ChatPage />,
      },
      {
        path: 'settings',
        element: <SettingsPage />,
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
]);
