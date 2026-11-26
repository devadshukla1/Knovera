/**
 * Interactive Knowledge Graph page for Knovera.
 *
 * Defaults to the Knovera interactive hierarchical mind map:
 * ROOT TOPIC -> PRIMARY TOPICS -> SECONDARY CONCEPTS -> DETAILED INFORMATION.
 *
 * Integrates:
 * - Left-to-right horizontal hierarchical layout
 * - Smooth cubic Bezier curves with active branch highlight
 * - Circular junction toggles (< / >)
 * - Knovera color tiers & crisp typography
 * - Direct document-grounded facts & citations
 * - Bayesian Knowledge Tracing learning status updates
 * - Research Chat, Interactive Quiz, and Document deep-linking
 * - Optional toggle to raw entity network view
 */

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  FolderKanban,
  ChevronRight,
  Network,
  Sparkles,
  Search,
  X,
  RefreshCw,
  BookOpen,
} from 'lucide-react';
import { Core } from 'cytoscape';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useWorkspace } from '@/features/workspaces/hooks/useWorkspaces';
import { useDocuments } from '@/features/documents/hooks/useDocuments';
import { useWorkspaceTopics } from '@/features/topics/hooks/useTopics';
import {
  useMindMap,
  useBuildMindMap,
  useKnowledgeGraphSearch,
  useKnowledgeGraphRelationships,
} from '../hooks/useKnowledgeGraph';
import {
  GraphNodeItem,
  GraphEdgeItem,
  MindMapNodeItem,
} from '../types/knowledgeGraph';
import { MindMapCanvas } from '../components/MindMapCanvas';
import { MindMapNodeDetails } from '../components/MindMapNodeDetails';
import { GraphCanvas } from '../components/GraphCanvas';
import { GraphEmptyState } from '../components/GraphEmptyState';
import { GraphLoadingState, GraphErrorState } from '../components/GraphStates';

export const KnowledgeGraphPage: React.FC = () => {
  const { workspaceId = '' } = useParams<{ workspaceId: string }>();

  // Primary View Mode: Knovera Mind Map vs Network Graph
  const [viewMode, setViewMode] = useState<'mindmap' | 'network'>('mindmap');

  // Search Query for Concept Filtering
  const [searchQuery, setSearchQuery] = useState('');

  // Selected Mind Map Node for slide-over drawer
  const [selectedMindMapNode, setSelectedMindMapNode] = useState<MindMapNodeItem | null>(null);

  // Network View State (for secondary network mode)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const cyRef = useRef<Core | null>(null);

  // Workspace and Document Metadata
  const { data: workspace } = useWorkspace(workspaceId);
  const { data: documents = [] } = useDocuments(workspaceId);
  const readyDocuments = documents.filter((d) => d.processing_status === 'ready');
  const { data: topicsData } = useWorkspaceTopics(workspaceId, { page_size: 10 });
  const topicsCount = topicsData?.total || topicsData?.items?.length || 0;

  // Mind Map Query & Build Mutation
  const {
    data: mindMapData,
    isLoading: isLoadingMindMap,
    isError: isMindMapError,
    error: mindMapError,
    refetch: refetchMindMap,
  } = useMindMap(workspaceId);

  const buildMindMapMutation = useBuildMindMap(workspaceId);

  // Secondary network view queries (loaded on-demand)
  const { data: nodesData } = useKnowledgeGraphSearch(
    workspaceId,
    { pageSize: 100, sortBy: 'degree', sortOrder: 'desc' },
    viewMode === 'network'
  );
  const { data: relationshipsData } = useKnowledgeGraphRelationships(
    workspaceId,
    { pageSize: 150 }
  );

  const [loadedNodes, setLoadedNodes] = useState<Map<string, GraphNodeItem>>(new Map());
  const [loadedEdges, setLoadedEdges] = useState<Map<string, GraphEdgeItem>>(new Map());

  useEffect(() => {
    const nodeMap = new Map<string, GraphNodeItem>();
    if (nodesData?.items) {
      nodesData.items.forEach((n) => nodeMap.set(n.id, n));
    }
    const edgeMap = new Map<string, GraphEdgeItem>();
    if (relationshipsData?.items) {
      relationshipsData.items.forEach((r) => edgeMap.set(r.id, r));
    }
    setLoadedNodes(nodeMap);
    setLoadedEdges(edgeMap);
  }, [nodesData, relationshipsData]);

  // Handle building or regenerating the Mind Map
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [rebuildStageIdx, setRebuildStageIdx] = useState(0);
  const [rebuildSuccessMsg, setRebuildSuccessMsg] = useState<string | null>(null);
  const [rebuildErrorMsg, setRebuildErrorMsg] = useState<string | null>(null);

  const REBUILD_STAGES = [
    'Collecting eligible workspace documents...',
    'Analyzing content & extracting concepts across documents...',
    'Detecting shared concepts & merging provenance...',
    'Organizing hierarchy, validating & saving graph...',
  ];

  const handleRebuildMindMap = async () => {
    if (isRebuilding || buildMindMapMutation.isPending) return;
    setRebuildSuccessMsg(null);
    setRebuildErrorMsg(null);
    setRebuildStageIdx(0);
    setIsRebuilding(true);

    const timer = window.setInterval(() => {
      setRebuildStageIdx((prev) => Math.min(prev + 1, REBUILD_STAGES.length - 1));
    }, 1800);

    try {
      const rebuilt = await buildMindMapMutation.mutateAsync();
      await refetchMindMap();
      const docCount = rebuilt?.source_document_count ?? readyDocuments.length;
      setRebuildSuccessMsg(
        `Knowledge Graph successfully rebuilt from ${docCount} workspace ${docCount === 1 ? 'document' : 'documents'}.`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to rebuild mind map.';
      setRebuildErrorMsg(msg);
      console.error('Failed to rebuild mind map:', err);
    } finally {
      window.clearInterval(timer);
      setIsRebuilding(false);
    }
  };

  const isOutOfDate = Boolean(
    mindMapData?.is_out_of_date ||
      (mindMapData &&
        mindMapData.source_document_count !== undefined &&
        readyDocuments.length > 0 &&
        readyDocuments.length !== mindMapData.source_document_count)
  );

  // Node status updated handler (reflects immediately in state)
  const handleStatusChanged = (nodeId: string, status: string) => {
    if (selectedMindMapNode && selectedMindMapNode.id === nodeId) {
      setSelectedMindMapNode({
        ...selectedMindMapNode,
        learning_status: status,
      });
    }
  };

  // Compute Mind Map Statistics
  const mindMapStats = useMemo(() => {
    if (!mindMapData || !mindMapData.nodes) {
      return { total: 0, primary: 0, secondary: 0, leaves: 0, learned: 0 };
    }
    let primary = 0;
    let secondary = 0;
    let leaves = 0;
    let learned = 0;

    mindMapData.nodes.forEach((n) => {
      if (n.level === 1) primary++;
      if (n.level === 2) secondary++;
      if (n.level === 3) leaves++;
      if (n.learning_status === 'learned') learned++;
    });

    return {
      total: mindMapData.nodes.length,
      primary,
      secondary,
      leaves,
      learned,
    };
  }, [mindMapData]);

  // Empty state check
  const hasNoContent = readyDocuments.length === 0 && (!mindMapData || mindMapData.nodes.length === 0);

  return (
    <PageContainer className="h-[calc(100vh-4rem)] flex flex-col p-4 md:p-6 overflow-hidden bg-background">
      {/* Header Bar */}
      <div className="shrink-0 mb-3">
        <PageHeader
          title="Knovera Mind Map"
          description="Hierarchical Knovera knowledge map: Root topic, primary domains, secondary concepts, and grounded facts."
          breadcrumbs={
            <div className="flex items-center gap-1.5 text-xs text-text-muted">
              <Link to="/app/workspaces" className="hover:text-text-primary transition-colors flex items-center gap-1">
                <FolderKanban className="h-3.5 w-3.5" />
                <span>Workspaces</span>
              </Link>
              <ChevronRight className="h-3 w-3" />
              <Link
                to={`/app/workspaces/${encodeURIComponent(workspaceId)}`}
                className="hover:text-text-primary transition-colors truncate max-w-[150px]"
              >
                {workspace?.name || 'Workspace'}
              </Link>
              <ChevronRight className="h-3 w-3" />
              <span className="text-text-primary font-medium">Knowledge Graph</span>
            </div>
          }
          action={
            <div className="flex items-center gap-2">
              {/* View Mode Toggle: Mind Map vs Network */}
              <div className="flex items-center bg-surface-elevated border border-border rounded-xl p-0.5">
                <Button
                  variant={viewMode === 'mindmap' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setViewMode('mindmap')}
                  className="gap-1.5 text-xs h-8 rounded-lg"
                >
                  <BookOpen className="h-3.5 w-3.5 text-primary" />
                  <span>Mind Map</span>
                </Button>
                <Button
                  variant={viewMode === 'network' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setViewMode('network')}
                  className="gap-1.5 text-xs h-8 rounded-lg"
                >
                  <Network className="h-3.5 w-3.5 text-text-muted" />
                  <span>Network</span>
                </Button>
              </div>

              {/* Rebuild Mind Map Button */}
              <Button
                variant="outline"
                size="sm"
                onClick={handleRebuildMindMap}
                disabled={isRebuilding || buildMindMapMutation.isPending}
                className="gap-1.5 text-xs h-8 border-primary/40 text-primary hover:bg-sky-500/10"
                title="Regenerate hierarchical mind map using Groq AI"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isRebuilding ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">
                  {isRebuilding ? 'Synthesizing...' : 'Rebuild Mind Map'}
                </span>
              </Button>
            </div>
          }
        />

        {/* Mind Map Summary Metrics Ribbon */}
        {viewMode === 'mindmap' && mindMapData && mindMapData.nodes.length > 0 && (
          <div className="mt-2.5 flex flex-wrap items-center gap-2.5 bg-surface/60 border border-border/80 rounded-xl px-4 py-2 text-xs">
            <span className="text-text-muted font-medium flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-primary" />
              Workspace Hierarchy:
            </span>
            <span className="font-semibold text-text-primary">{mindMapData.workspace_name}</span>
            <span className="text-slate-600">•</span>
            <span className="text-text-secondary">
              <strong className="text-text-primary font-mono">{mindMapStats.primary}</strong> Primary Topics
            </span>
            <span className="text-slate-600">•</span>
            <span className="text-text-secondary">
              <strong className="text-text-primary font-mono">{mindMapStats.secondary}</strong> Concepts
            </span>
            <span className="text-slate-600">•</span>
            <span className="text-text-secondary">
              <strong className="text-text-primary font-mono">{mindMapStats.leaves}</strong> Grounded Facts
            </span>
            <span className="text-slate-600">•</span>
            <span className="text-text-secondary">
              <strong className="text-text-primary font-mono">{mindMapData.source_document_count ?? readyDocuments.length}</strong> Docs (v{mindMapData.version ?? 1})
            </span>
            <span className="text-slate-600">•</span>
            <span className="text-emerald-400 font-medium">
              <strong className="font-mono text-emerald-300">{mindMapStats.learned}</strong> Mastered
            </span>
          </div>
        )}

        {/* Out-of-Date Warning / Rebuild Progress / Result Banners */}
        {viewMode === 'mindmap' && isOutOfDate && !isRebuilding && (
          <div className="mt-2 flex items-center justify-between gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-xs text-amber-200">
            <span>
              <strong>{mindMapData?.out_of_date_reason || 'Out of date — New document available.'}</strong>{' '}
              Rebuild to merge all {readyDocuments.length} workspace documents into one unified graph.
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={handleRebuildMindMap}
              className="h-7 text-xs border-amber-400/50 text-amber-200 hover:bg-amber-500/20 shrink-0"
            >
              Rebuild Now
            </Button>
          </div>
        )}

        {viewMode === 'mindmap' && isRebuilding && (
          <div className="mt-2 flex items-center justify-between gap-3 rounded-xl border border-sky-500/40 bg-sky-500/10 px-4 py-2 text-xs text-sky-200">
            <span className="flex items-center gap-2">
              <RefreshCw className="h-3.5 w-3.5 animate-spin text-sky-400" />
              <span>
                Processing {readyDocuments.length} workspace {readyDocuments.length === 1 ? 'document' : 'documents'}:{' '}
                <strong>{REBUILD_STAGES[rebuildStageIdx]}</strong>
              </span>
            </span>
          </div>
        )}

        {viewMode === 'mindmap' && rebuildSuccessMsg && !isRebuilding && (
          <div className="mt-2 flex items-center justify-between gap-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-xs text-emerald-200">
            <span>{rebuildSuccessMsg}</span>
            <button
              type="button"
              onClick={() => setRebuildSuccessMsg(null)}
              className="text-emerald-300 hover:text-white"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {viewMode === 'mindmap' && rebuildErrorMsg && !isRebuilding && (
          <div className="mt-2 flex items-center justify-between gap-3 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-2 text-xs text-destructive">
            <span>Rebuild failed (previous graph preserved): {rebuildErrorMsg}</span>
            <Button
              size="sm"
              variant="outline"
              onClick={handleRebuildMindMap}
              className="h-7 text-xs border-destructive/40 text-destructive hover:bg-destructive/15 shrink-0"
            >
              Retry
            </Button>
          </div>
        )}
      </div>

      {/* Mind Map Search & Quick Filters Bar */}
      {viewMode === 'mindmap' && (
        <div className="shrink-0 flex items-center justify-between gap-3 mb-2.5">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted pointer-events-none" />
            <Input
              type="text"
              placeholder="Search concepts, formulas, definitions, algorithms..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-9 h-9 text-xs bg-surface/80 border-border text-text-primary placeholder:text-text-muted rounded-xl focus:border-primary focus:ring-1 focus:ring-primary"
            />
            {searchQuery && (
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
                onClick={() => setSearchQuery('')}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span className="hidden sm:inline">Tip: Click any node to open details & study actions</span>
          </div>
        </div>
      )}

      {/* Main Interactive Canvas Area */}
      <div className="relative flex-1 rounded-2xl overflow-hidden border border-border shadow-2xl bg-background flex">
        {hasNoContent ? (
          <div className="flex-1 flex items-center justify-center p-6">
            <GraphEmptyState
              workspaceId={workspaceId}
              readyDocumentsCount={readyDocuments.length}
              topicsCount={topicsCount}
              onBuildGraph={handleRebuildMindMap}
              isBuilding={isRebuilding}
            />
          </div>
        ) : isLoadingMindMap ? (
          <div className="flex-1 flex items-center justify-center">
            <GraphLoadingState />
          </div>
        ) : isMindMapError ? (
          <div className="flex-1 flex items-center justify-center p-6">
            <GraphErrorState
              error={mindMapError instanceof Error ? mindMapError : null}
              onRetry={() => refetchMindMap()}
            />
          </div>
        ) : viewMode === 'mindmap' && mindMapData ? (
          <div className="flex-1 h-full w-full relative flex overflow-hidden">
            {/* Mind Map Canvas */}
            <div className="flex-1 h-full w-full relative overflow-hidden">
              <MindMapCanvas
                tree={mindMapData}
                selectedNodeId={selectedMindMapNode?.id || null}
                onSelectNode={(node) => setSelectedMindMapNode(node)}
                searchQuery={searchQuery}
              />
            </div>

            {/* Slide-over Node Details Drawer */}
            {selectedMindMapNode && (
              <MindMapNodeDetails
                node={selectedMindMapNode}
                workspaceId={workspaceId}
                onClose={() => setSelectedMindMapNode(null)}
                onNodeStatusChanged={handleStatusChanged}
              />
            )}
          </div>
        ) : (
          /* Secondary Network View (Cytoscape) */
          <div className="flex-1 h-full w-full relative">
            <GraphCanvas
              nodes={Array.from(loadedNodes.values())}
              edges={Array.from(loadedEdges.values())}
              selectedNodeId={selectedNodeId}
              selectedEdgeId={selectedEdgeId}
              onSelectNode={(nodeId) => setSelectedNodeId(nodeId)}
              onSelectEdge={(edgeId) => setSelectedEdgeId(edgeId)}
              onCyReady={(cy) => {
                cyRef.current = cy;
              }}
            />
          </div>
        )}
      </div>
    </PageContainer>
  );
};
