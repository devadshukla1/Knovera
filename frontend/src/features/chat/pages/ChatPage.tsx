import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import {
  MessageSquare,
  Plus,
  FolderKanban,
  ChevronRight,
  Info,
  AlertCircle,
  Trash2,
  Edit2,
  Check,
  X,
  Search,
  PanelLeftClose,
  PanelLeft,
  Clock,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MessageBubble } from '../components/MessageBubble';
import { ChatComposer } from '../components/ChatComposer';
import { ThinkingBubble } from '../components/ThinkingBubble';
import { CitationInspector } from '../components/CitationInspector';
import { SourceScopeSelector } from '../components/SourceScopeSelector';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { useWorkspace } from '@/features/workspaces/hooks/useWorkspaces';
import { useDocuments } from '@/features/documents/hooks/useDocuments';
import { useWorkspaceTopics } from '@/features/topics/hooks/useTopics';
import {
  useSendMessage,
  useConversation,
  useConversations,
  useRenameConversation,
  useDeleteConversation,
} from '../hooks/useChat';
import { ChatMessage, Citation } from '../types/chat';

export const ChatPage: React.FC = () => {
  const { workspaceId = '', conversationId: routeConversationId } = useParams<{
    workspaceId: string;
    conversationId?: string;
  }>();

  const [searchParams, setSearchParams] = useSearchParams();
  const urlConvId = searchParams.get('c') || searchParams.get('conversationId') || routeConversationId;

  const storageKey = `knovera_active_conv_${workspaceId}`;
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    return urlConvId || localStorage.getItem(storageKey) || null;
  });

  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [localMessages, setLocalMessages] = useState<ChatMessage[]>([]);
  const [apiNotice, setApiNotice] = useState<string | null>(null);
  const [failedQuery, setFailedQuery] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 768);
  const [searchFilter, setSearchFilter] = useState('');
  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [deleteConfirmConvId, setDeleteConfirmConvId] = useState<string | null>(null);
  const [isDeletingConv, setIsDeletingConv] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeConvRef = useRef<string | null>(activeConversationId);
  useEffect(() => {
    activeConvRef.current = activeConversationId;
  }, [activeConversationId]);

  const { data: workspace } = useWorkspace(workspaceId);
  const { data: documents = [] } = useDocuments(workspaceId);
  const { data: topicsData } = useWorkspaceTopics(workspaceId, { page_size: 6 });
  const topics = topicsData?.items || [];
  const { data: conversations = [], isLoading: isLoadingConversations } = useConversations(workspaceId);
  const { data: conversationData, isLoading: isLoadingConversation } = useConversation(
    workspaceId,
    activeConversationId || undefined
  );

  const sendMessageMutation = useSendMessage(workspaceId);
  const renameMutation = useRenameConversation(workspaceId);
  const deleteMutation = useDeleteConversation(workspaceId);

  // Sync state with URL or localStorage on workspace change
  useEffect(() => {
    setSelectedDocIds([]);
    setActiveCitation(null);
    setApiNotice(null);
    const initialId = urlConvId || localStorage.getItem(`knovera_active_conv_${workspaceId}`) || null;
    setActiveConversationId(initialId);
  }, [workspaceId, urlConvId]);

  // Persist activeConversationId to localStorage & URL
  useEffect(() => {
    if (activeConversationId) {
      localStorage.setItem(storageKey, activeConversationId);
      if (searchParams.get('c') !== activeConversationId) {
        setSearchParams({ c: activeConversationId }, { replace: true });
      }
    } else {
      localStorage.removeItem(storageKey);
      if (searchParams.has('c')) {
        setSearchParams({}, { replace: true });
      }
    }
  }, [activeConversationId, storageKey, searchParams, setSearchParams]);

  // Load conversation messages into local state when conversationData arrives
  useEffect(() => {
    if (conversationData && conversationData.messages) {
      setLocalMessages(conversationData.messages);
    } else if (!activeConversationId) {
      setLocalMessages([]);
    }
  }, [conversationData, activeConversationId]);

  // Auto-scroll on new message or thinking state change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [localMessages, sendMessageMutation.isPending]);

  const readyDocuments = useMemo(() => {
    return documents.filter((d) => d.processing_status === 'ready');
  }, [documents]);

  const filteredConversations = useMemo(() => {
    if (!searchFilter.trim()) return conversations;
    const q = searchFilter.toLowerCase().trim();
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, searchFilter]);

  const executeChatRequest = async (text: string, appendUserMessage: boolean) => {
    setApiNotice(null);
    setFailedQuery(null);

    if (appendUserMessage) {
      const tempUserMsg: ChatMessage = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: text,
        created_at: new Date().toISOString(),
      };
      setLocalMessages((prev) => [...prev, tempUserMsg]);
    } else {
      // Remove any previous failed assistant placeholder before retrying
      setLocalMessages((prev) =>
        prev.filter((m, idx) => !(idx === prev.length - 1 && m.role === 'assistant' && m.status === 'failed'))
      );
    }

    try {
      const response = await sendMessageMutation.mutateAsync({
        message: text,
        conversation_id: activeConversationId || undefined,
        selected_document_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
      });

      if (response.conversation_id && response.conversation_id !== activeConvRef.current) {
        setActiveConversationId(response.conversation_id);
      }

      const contentText = response.content || (response as any).response || '';
      if (!contentText.trim()) {
        throw new Error('Provider returned an empty response.');
      }

      const assistantMsg: ChatMessage = {
        id: response.id || `turn-${Date.now()}`,
        role: 'assistant',
        content: contentText,
        status: 'complete',
        citations: response.citations || [],
        evidence_status: response.evidence_status === 'insufficient' || response.evidence_status === 'partial' || response.evidence_status === 'full'
          ? response.evidence_status
          : 'full',
        created_at: new Date().toISOString(),
      };

      setLocalMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to generate answer. Please try again.';
      setApiNotice(errorMessage);
      setFailedQuery(text);
    }
  };

  const handleSendMessage = async (text: string) => {
    await executeChatRequest(text, true);
  };

  const handleRetryFailed = async (fallbackText?: string) => {
    const queryToRetry = failedQuery || fallbackText;
    if (!queryToRetry || sendMessageMutation.isPending) return;
    await executeChatRequest(queryToRetry, false);
  };

  const handleNewConversation = () => {
    setActiveConversationId(null);
    setLocalMessages([]);
    setActiveCitation(null);
    setApiNotice(null);
    setEditingConvId(null);
  };

  const handleSelectConversation = (convId: string) => {
    if (window.innerWidth < 768) setSidebarOpen(false);
    if (activeConversationId === convId) return;
    setActiveConversationId(convId);
    setActiveCitation(null);
    setApiNotice(null);
    setEditingConvId(null);
  };

  const handleStartRename = (convId: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingConvId(convId);
    setEditingTitle(currentTitle);
  };

  const handleSaveRename = async (convId: string, e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!editingTitle.trim()) return;

    try {
      await renameMutation.mutateAsync({
        conversationId: convId,
        title: editingTitle.trim(),
      });
      setEditingConvId(null);
    } catch (err) {
      console.error('Failed to rename conversation:', err);
    }
  };

  const handleDeleteConversation = (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteConfirmConvId(convId);
  };

  const handleConfirmDelete = async () => {
    if (!deleteConfirmConvId) return;
    try {
      setIsDeletingConv(true);
      await deleteMutation.mutateAsync({ conversationId: deleteConfirmConvId });
      if (activeConversationId === deleteConfirmConvId) {
        handleNewConversation();
      }
      setDeleteConfirmConvId(null);
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    } finally {
      setIsDeletingConv(false);
    }
  };

  // Generate dynamic, document-aware research suggestions based on workspace documents and topics
  const suggestedQueries = useMemo(() => {
    if (readyDocuments.length === 0) return [];
    const suggestions: string[] = [];

    // Suggestions derived from ready document titles
    for (const doc of readyDocuments.slice(0, 2)) {
      const cleanName = doc.original_filename.replace(/\.[^/.]+$/, '').trim();
      suggestions.push(`Summarize the core insights and findings from "${cleanName}"`);
      suggestions.push(`What key methodologies and evidence are presented in "${cleanName}"?`);
    }

    // Suggestions derived from extracted topics
    for (const top of topics.slice(0, 2)) {
      suggestions.push(`Explain the fundamental concepts and principles of ${top.label}`);
    }

    if (readyDocuments.length > 1) {
      suggestions.push('Synthesize and compare the key takeaways across all indexed documents in this workspace');
    }

    return Array.from(new Set(suggestions)).slice(0, 4);
  }, [readyDocuments, topics]);

  return (
    <div className="flex flex-col h-[calc(100dvh-4rem)] bg-background">
      {/* Top Header Bar */}
      <div className="shrink-0 border-b border-border/80 bg-surface/90 px-4 py-3 flex flex-wrap items-center justify-between gap-3 backdrop-blur-xl">
        <div className="flex items-center gap-2 text-xs">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setSidebarOpen((prev) => !prev)}
            className="text-text-muted hover:text-text-primary hover:bg-surface-muted"
            title={sidebarOpen ? 'Hide conversation history' : 'Show conversation history'}
          >
            {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
          </Button>

          <Link
            to="/app/workspaces"
            className="text-text-muted hover:text-text-primary transition-colors flex items-center gap-1"
          >
            <FolderKanban className="h-3.5 w-3.5 text-primary" />
            <span>Workspaces</span>
          </Link>
          <ChevronRight className="h-3 w-3 text-border" />
          <Link
            to={`/app/workspaces/${encodeURIComponent(workspaceId)}`}
            className="text-text-muted hover:text-text-primary transition-colors font-medium truncate max-w-[150px]"
          >
            {workspace ? workspace.name : 'Workspace'}
          </Link>
          <ChevronRight className="h-3 w-3 text-border" />
          <span className="text-text-primary font-semibold flex items-center gap-1.5">
            <MessageSquare className="h-3.5 w-3.5 text-primary" />
            <span>Research Chat</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Source Scope Dropdown */}
          <SourceScopeSelector
            workspaceId={workspaceId}
            selectedDocumentIds={selectedDocIds}
            onScopeChange={setSelectedDocIds}
          />

          {/* New Chat Button */}
          <Button
            variant="subtle"
            size="sm"
            onClick={handleNewConversation}
            className="h-8 text-xs gap-1.5"
            title="Start new conversation"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>New Chat</span>
          </Button>
        </div>
      </div>

      {/* Main Split Layout: History Sidebar + Chat Area + Citation Inspector */}
      <div className="relative flex min-h-0 flex-1 overflow-hidden">
        {/* Left Conversation History Sidebar */}
        {sidebarOpen && (
          <aside className="chat-history w-64 sm:w-72 border-r border-border/80 bg-surface/95 flex flex-col shrink-0 overflow-hidden transition-all duration-200 shadow-elevation-1">
            {/* Sidebar Header & New Chat button */}
            <div className="p-3 border-b border-border/80 space-y-2">
              <Button
                variant="default"
                size="sm"
                onClick={handleNewConversation}
                className="w-full justify-center text-xs gap-1.5 h-8 font-semibold shadow-sm"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>New Conversation</span>
              </Button>

              {/* Filter / Search input */}
              <div className="relative">
                <Search className="h-3.5 w-3.5 text-text-muted absolute left-2.5 top-2.5" />
                <Input
                  type="text"
                  placeholder="Filter past chats..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="pl-8 h-8 text-xs bg-surface-muted/60 border-border/80 focus:border-primary/50"
                />
              </div>
            </div>

            {/* Conversation List */}
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {isLoadingConversations ? (
                <div className="flex items-center justify-center p-6 text-text-muted text-xs gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                  <span>Loading history...</span>
                </div>
              ) : filteredConversations.length === 0 ? (
                <div className="p-4 text-center text-xs text-text-muted space-y-1">
                  <Clock className="h-4 w-4 mx-auto text-text-muted/60 mb-1" />
                  <p>{searchFilter ? 'No matching chats found' : 'No past conversations yet'}</p>
                  <p className="text-[11px] text-text-muted/70">Ask a question to start your first chat thread.</p>
                </div>
              ) : (
                filteredConversations.map((conv) => {
                  const isActive = activeConversationId === conv.id;
                  const isEditing = editingConvId === conv.id;

                  return (
                    <div
                      key={conv.id}
                      onClick={() => !isEditing && handleSelectConversation(conv.id)}
                      className={`group relative flex items-center justify-between rounded-lg px-2.5 py-2 text-xs cursor-pointer transition-all ${
                        isActive
                          ? 'bg-primary/15 text-primary font-semibold border border-primary/30 shadow-sm'
                          : 'text-text-secondary hover:bg-surface-elevated hover:text-text-primary'
                      }`}
                    >
                      {isEditing ? (
                        <form
                          onSubmit={(e) => handleSaveRename(conv.id, e)}
                          className="flex items-center gap-1 w-full"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Input
                            autoFocus
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            className="h-7 text-xs bg-surface px-2 py-0 border-primary"
                          />
                          <button
                            type="submit"
                            className="p-1 text-primary hover:text-primary-hover rounded hover:bg-surface-muted transition-colors"
                            title="Save"
                          >
                            <Check className="h-3 w-3" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingConvId(null)}
                            className="p-1 text-text-muted hover:text-text-primary rounded hover:bg-surface-muted transition-colors"
                            title="Cancel"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </form>
                      ) : (
                        <>
                          <div className="flex items-center gap-2 truncate pr-2">
                            <MessageSquare className="h-3.5 w-3.5 shrink-0 text-primary/70" />
                            <span className="truncate">{conv.title || 'Untitled Thread'}</span>
                          </div>

                          <div className="flex sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100 items-center gap-1 shrink-0">
                            <button
                              onClick={(e) => handleStartRename(conv.id, conv.title, e)}
                              className="p-1 text-text-muted hover:text-text-primary rounded hover:bg-surface-muted transition-colors"
                              title="Rename chat"
                            >
                              <Edit2 className="h-3 w-3" />
                            </button>
                            <button
                              onClick={(e) => handleDeleteConversation(conv.id, e)}
                              className="p-1 text-text-muted hover:text-danger rounded hover:bg-danger/10 transition-colors"
                              title="Delete chat"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </aside>
        )}

        {/* Center Chat Stream Column */}
        <div className="chat-stage flex flex-1 flex-col overflow-hidden bg-background">
          {/* Messages Scroll Area */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
            {/* Zero Ready Documents Notice */}
            {readyDocuments.length === 0 && (
              <div className="mx-auto max-w-2xl rounded-2xl border border-warning/30 bg-warning/5 p-4 text-xs text-warning flex items-start gap-3 shadow-sm">
                <Info className="h-4 w-4 shrink-0 mt-0.5 text-warning" />
                <div className="space-y-1">
                  <p className="font-semibold text-text-primary">
                    No Ready Documents in this Workspace
                  </p>
                  <p className="text-text-secondary leading-relaxed">
                    Research Q&A synthesizes answers from verified source documents. Upload PDFs, Word documents (.docx), or text notes in the Document Library.
                  </p>
                  <div className="pt-2">
                    <Link
                      to={`/app/workspaces/${encodeURIComponent(workspaceId)}/documents`}
                    >
                      <Button variant="secondary" size="sm" className="h-7 text-xs">
                        Open Document Library
                      </Button>
                    </Link>
                  </div>
                </div>
              </div>
            )}

            {/* Conversation Loading Spinner */}
            {isLoadingConversation && activeConversationId && (
              <div className="flex items-center justify-center p-8 text-xs text-text-muted gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <span>Restoring conversation history...</span>
              </div>
            )}

            {/* Empty Conversation Initial View */}
            {!isLoadingConversation && localMessages.length === 0 && (
              <div className="flex flex-col items-center justify-center p-8 sm:p-12 text-center max-w-xl mx-auto space-y-4 my-auto">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-accent-purple/10 border border-primary/30 text-primary shadow-glow-sm">
                  <MessageSquare className="h-7 w-7" />
                </div>

                {readyDocuments.length === 0 ? (
                  <>
                    <div>
                      <h3 className="text-lg sm:text-xl font-bold text-text-primary tracking-tight">
                        Your Research Workspace is Ready
                      </h3>
                      <p className="text-xs sm:text-sm text-text-secondary mt-1.5 leading-relaxed max-w-md mx-auto">
                        Upload and index documents to explore your knowledge, ask questions and discover connections.
                      </p>
                    </div>
                    <div className="pt-2">
                      <Link to={`/app/workspaces/${encodeURIComponent(workspaceId)}/documents`}>
                        <Button size="sm" className="gap-2 text-xs h-9 px-4 rounded-xl shadow-sm">
                          <Plus className="h-3.5 w-3.5" />
                          <span>Open Document Library</span>
                        </Button>
                      </Link>
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <h3 className="text-lg sm:text-xl font-bold text-text-primary tracking-tight">
                        Ask Questions Grounded in Your Sources
                      </h3>
                      <p className="text-xs sm:text-sm text-text-secondary mt-1.5 leading-relaxed">
                        Knovera performs hybrid BM25 + dense vector retrieval across your active workspace documents with verified page-level citations.
                      </p>
                    </div>

                    {/* Dynamic Document-Aware Suggestions */}
                    {suggestedQueries.length > 0 && (
                      <div className="flex flex-col w-full gap-2 pt-3">
                        <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wider text-left px-1">
                          Suggested Research Queries
                        </p>
                        {suggestedQueries.map((prompt, i) => (
                          <button
                            key={i}
                            onClick={() => handleSendMessage(prompt)}
                            className="text-left text-xs text-text-secondary hover:text-text-primary bg-surface/90 border border-border/80 hover:border-primary/40 hover:bg-surface-elevated rounded-xl p-3 transition-all duration-150 shadow-sm hover:shadow-elevation-1 flex items-center justify-between group"
                          >
                            <span>“{prompt}”</span>
                            <ChevronRight className="h-3.5 w-3.5 text-text-muted group-hover:text-primary transition-colors shrink-0" />
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Conversation Messages */}
            {localMessages.map((msg, idx) => {
              const prevUserMsg = idx > 0 && localMessages[idx - 1]?.role === 'user' ? localMessages[idx - 1].content : undefined;
              return (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onSelectCitation={setActiveCitation}
                  activeCitationId={activeCitation?.id}
                  onRetry={msg.status === 'failed' ? () => handleRetryFailed(prevUserMsg) : undefined}
                />
              );
            })}

            {/* In-Flight AI Thinking & Response State Indicator */}
            {sendMessageMutation.isPending && (
              <ThinkingBubble />
            )}

            {/* In-Flight Query Error & Retry Notice */}
            {apiNotice && (
              <div className="mx-auto max-w-2xl rounded-xl border border-destructive/30 bg-destructive/10 p-3.5 text-xs text-text-primary flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5">
                  <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-destructive">Generation Failed</p>
                    <p className="text-text-secondary mt-0.5 leading-relaxed">
                      {apiNotice}
                    </p>
                  </div>
                </div>
                {failedQuery && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleRetryFailed()}
                    disabled={sendMessageMutation.isPending}
                    className="h-7 text-xs shrink-0 border-destructive/30 text-destructive hover:bg-destructive/10"
                  >
                    Retry
                  </Button>
                )}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Message Composer Area */}
          <div className="shrink-0 border-t border-border/80 bg-surface/90 p-4 backdrop-blur-xl">
            <div className="max-w-3xl mx-auto">
              <ChatComposer
                onSend={handleSendMessage}
                isLoading={sendMessageMutation.isPending}
                disabled={readyDocuments.length === 0}
                placeholder={
                  readyDocuments.length === 0
                    ? 'Upload and index documents to start research Q&A...'
                    : 'Ask a question about your documents... (Press Enter to send)'
                }
              />
              <p className="text-[11px] text-text-muted mt-2.5 text-center">
                Responses in Knovera are strictly synthesized from workspace sources with verified page-level citations.
              </p>
            </div>
          </div>
        </div>

        {/* Citation Inspector Side Panel */}
        {activeCitation && (
          <div className="chat-citations w-80 shrink-0 hidden md:block">
            <CitationInspector
              citation={activeCitation}
              workspaceId={workspaceId}
              onClose={() => setActiveCitation(null)}
            />
          </div>
        )}
      </div>

      {/* Delete Conversation Thread Confirmation Dialog */}
      <ConfirmDialog
        open={Boolean(deleteConfirmConvId)}
        onOpenChange={(open) => !open && setDeleteConfirmConvId(null)}
        title="Delete Conversation Thread"
        description="Are you sure you want to delete this conversation thread and its message history? This action cannot be undone."
        confirmText="Delete Thread"
        cancelText="Cancel"
        isDestructive
        isLoading={isDeletingConv}
        onConfirm={handleConfirmDelete}
      />
    </div>
  );
};
