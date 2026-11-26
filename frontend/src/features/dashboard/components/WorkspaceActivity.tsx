import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, FileText, MessageSquare, GraduationCap } from 'lucide-react';
import { useDocuments } from '@/features/documents/hooks/useDocuments';
import { useConversations } from '@/features/chat/hooks/useChat';
import { analyticsApi } from '@/features/analytics/api/analyticsApi';
import { DocumentStatusBadge } from '@/features/documents/components/DocumentStatusBadge';
import { Skeleton } from '@/components/ui/skeleton';
import { formatRelativeTime } from '@/lib/utils';

/** Read-only overview composed from the same queries used by the workspace pages. */
export function WorkspaceActivity({ workspaceId }: { workspaceId: string }) {
  const documents = useDocuments(workspaceId);
  const conversations = useConversations(workspaceId);
  const overview = useQuery({
    queryKey: ['analytics-overview', workspaceId, 'all'],
    queryFn: () => analyticsApi.getOverview(workspaceId, 'all'),
  });
  const prefix = `/app/workspaces/${encodeURIComponent(workspaceId)}`;
  const recentDocuments = [...(documents.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 3);
  const recentConversations = [...(conversations.data ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 3);

  return (
    <section className="mt-8 grid min-w-0 gap-6 xl:grid-cols-2" aria-label="Active workspace activity">
      <div className="min-w-0 rounded-xl border border-border bg-surface p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">Recent documents</h2>
          <Link to={`${prefix}/documents`} className="flex items-center gap-1 text-xs text-primary">Open library <ArrowUpRight className="h-3.5 w-3.5" /></Link>
        </div>
        {documents.isLoading ? <Skeleton className="h-24 w-full" /> : documents.isError ? (
          <p className="text-sm text-text-muted">Documents couldn’t load. <button className="text-primary underline" onClick={() => documents.refetch()}>Retry</button></p>
        ) : recentDocuments.length === 0 ? <p className="py-4 text-sm text-text-muted">Add your first source to start exploring.</p> : (
          <ul className="divide-y divide-border-subtle">
            {recentDocuments.map(doc => <li key={doc.id}>
              <Link to={`${prefix}/documents/${encodeURIComponent(doc.id)}`} className="-mx-2 flex min-w-0 items-center gap-3 rounded-lg px-2 py-3 hover:bg-surface-muted">
                <FileText className="h-4 w-4 shrink-0 text-primary" />
                <div className="min-w-0 flex-1"><p className="truncate text-sm" title={doc.original_filename}>{doc.original_filename}</p><p className="mt-1 text-xs text-text-muted">{formatRelativeTime(doc.created_at)}</p></div>
                <DocumentStatusBadge status={doc.processing_status} />
              </Link>
            </li>)}
          </ul>
        )}
      </div>
      <div className="min-w-0 rounded-xl border border-border bg-surface p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">Recent conversations</h2>
          <Link to={`${prefix}/chat`} className="flex items-center gap-1 text-xs text-primary">Research chat <ArrowUpRight className="h-3.5 w-3.5" /></Link>
        </div>
        {conversations.isLoading ? <Skeleton className="h-24 w-full" /> : conversations.isError ? (
          <p className="text-sm text-text-muted">Conversations couldn’t load. <button className="text-primary underline" onClick={() => conversations.refetch()}>Retry</button></p>
        ) : recentConversations.length === 0 ? <p className="py-4 text-sm text-text-muted">Your questions and discoveries will appear here.</p> : (
          <ul className="divide-y divide-border-subtle">
            {recentConversations.map(conversation => <li key={conversation.id}>
              <Link to={`${prefix}/chat/${encodeURIComponent(conversation.id)}`} className="-mx-2 flex min-w-0 items-center gap-3 rounded-lg px-2 py-3 hover:bg-surface-muted">
                <MessageSquare className="h-4 w-4 shrink-0 text-primary" />
                <div className="min-w-0 flex-1"><p className="truncate text-sm">{conversation.title || 'Untitled conversation'}</p><p className="mt-1 text-xs text-text-muted">{formatRelativeTime(conversation.updated_at)}</p></div>
                <ArrowUpRight className="h-4 w-4 shrink-0 text-text-muted" />
              </Link>
            </li>)}
          </ul>
        )}
      </div>
      <Link to={`${prefix}/learning-analytics`} className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-surface px-5 py-4 hover:border-border-highlight xl:col-span-2">
        <GraduationCap className="h-5 w-5 text-primary" />
        <div className="flex-1"><h2 className="text-sm font-semibold">Your learning progress</h2><p className="mt-1 text-xs text-text-secondary">{overview.isLoading ? 'Loading learning activity…' : overview.isError ? 'Open analytics to view your learning activity.' : `${overview.data?.completed_attempts ?? 0} completed quizzes · ${overview.data?.concepts_assessed ?? 0} concepts assessed · ${overview.data?.pending_recommendations_count ?? 0} revision recommendations`}</p></div>
        <ArrowUpRight className="h-4 w-4 text-text-muted" />
      </Link>
    </section>
  );
}
