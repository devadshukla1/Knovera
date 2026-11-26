/**
 * Knovera interactive Mind Map canvas.
 *
 * Implements a strict left-to-right hierarchical tree:
 * ROOT (Level 0) -> PRIMARY TOPICS (Level 1) -> SECONDARY CONCEPTS (Level 2) -> DETAILED LEAF NODES (Level 3).
 *
 * Features:
 * - Deterministic, non-overlapping subtree layout
 * - Smooth cubic Bezier curves with branch highlight
 * - Circular expand/collapse junction toggles (< / >)
 * - Knovera color tiers & crisp typography
 * - Smooth pan, zoom, fit-to-screen, and search filtering
 */

import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  BookOpen,
  FileText,
  CheckCircle2,
  Clock,
  HelpCircle,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  MindMapNodeItem,
  MindMapTreeResponse,
} from '../types/knowledgeGraph';

interface MindMapCanvasProps {
  tree: MindMapTreeResponse;
  selectedNodeId: string | null;
  onSelectNode: (node: MindMapNodeItem) => void;
  searchQuery?: string;
  className?: string;
}

interface LayoutNode extends MindMapNodeItem {
  x: number;
  y: number;
  width: number;
  height: number;
  subtreeHeight: number;
  visible: boolean;
}

// Layout Dimensions
const LEVEL_X: Record<number, number> = {
  0: 60,   // Root
  1: 390,  // Primary Topics
  2: 740,  // Secondary Concepts
  3: 1100, // Leaf Nodes
};

const NODE_WIDTH: Record<number, number> = {
  0: 270,
  1: 280,
  2: 290,
  3: 320,
};

const NODE_BASE_HEIGHT: Record<number, number> = {
  0: 90,
  1: 95,
  2: 100,
  3: 105,
};

const VERTICAL_GAP = 20;

export const MindMapCanvas: React.FC<MindMapCanvasProps> = ({
  tree,
  selectedNodeId,
  onSelectNode,
  searchQuery = '',
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Pan and Zoom
  const [zoom, setZoom] = useState(0.85);
  const [pan, setPan] = useState({ x: 80, y: 120 });
  const [isDragging, setIsDragging] = useState(false);
  const panRef = useRef({ x: 80, y: 120 });
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const dragInitialPosRef = useRef({ x: 0, y: 0 });
  const hasDraggedRef = useRef(false);

  // Keep panRef in sync
  useEffect(() => {
    panRef.current = pan;
  }, [pan]);

  // Collapse / Expand set (stores IDs of nodes whose children are collapsed)
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());

  // Toggle single node collapse
  const toggleCollapse = useCallback((nodeId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  // Expand all
  const expandAll = useCallback(() => {
    setCollapsedIds(new Set());
  }, []);

  // Collapse to primary topics
  const collapseAll = useCallback(() => {
    const toCollapse = new Set<string>();
    tree.nodes.forEach((n) => {
      if (n.level === 1 || n.level === 2) {
        toCollapse.add(n.id);
      }
    });
    setCollapsedIds(toCollapse);
  }, [tree.nodes]);

  // Auto-expand search matches
  useEffect(() => {
    if (!searchQuery.trim()) return;
    const q = searchQuery.toLowerCase().trim();
    const matchingNodeIds = new Set<string>();

    tree.nodes.forEach((n) => {
      if (
        n.label.toLowerCase().includes(q) ||
        (n.description && n.description.toLowerCase().includes(q)) ||
        (n.summary && n.summary.toLowerCase().includes(q))
      ) {
        matchingNodeIds.add(n.id);
      }
    });

    if (matchingNodeIds.size > 0) {
      // Find all parents of matching nodes and uncollapse them
      const parentMap = new Map<string, string>();
      tree.nodes.forEach((n) => {
        if (n.parent_id) parentMap.set(n.id, n.parent_id);
      });

      setCollapsedIds((prev) => {
        const next = new Set(prev);
        matchingNodeIds.forEach((id) => {
          let curr = id;
          while (parentMap.has(curr)) {
            const pId = parentMap.get(curr)!;
            next.delete(pId);
            curr = pId;
          }
        });
        return next;
      });
    }
  }, [searchQuery, tree.nodes]);

  // Compute Active Branch (IDs from Root to Selected Node)
  const activeBranchIds = useMemo(() => {
    if (!selectedNodeId) return new Set<string>();
    const ids = new Set<string>();
    ids.add(selectedNodeId);

    const parentMap = new Map<string, string>();
    tree.nodes.forEach((n) => {
      if (n.parent_id) parentMap.set(n.id, n.parent_id);
    });

    let curr = selectedNodeId;
    while (parentMap.has(curr)) {
      const p = parentMap.get(curr)!;
      ids.add(p);
      curr = p;
    }
    return ids;
  }, [selectedNodeId, tree.nodes]);

  // Hierarchical Layout Calculation
  const layoutNodes = useMemo(() => {
    const nodeMap = new Map<string, MindMapNodeItem>();
    const childrenMap = new Map<string, MindMapNodeItem[]>();

    tree.nodes.forEach((n) => {
      nodeMap.set(n.id, n);
      if (n.parent_id) {
        if (!childrenMap.has(n.parent_id)) childrenMap.set(n.parent_id, []);
        childrenMap.get(n.parent_id)!.push(n);
      }
    });

    // Find root
    const root = tree.nodes.find((n) => n.level === 0) || tree.nodes[0];
    if (!root) return [];

    // Helper: recursively compute subtree height
    function computeSubtreeHeight(n: MindMapNodeItem): number {
      const isCollapsed = collapsedIds.has(n.id);
      const children = isCollapsed ? [] : childrenMap.get(n.id) || [];

      if (children.length === 0) {
        return (NODE_BASE_HEIGHT[n.level] || 90) + VERTICAL_GAP;
      }

      let total = 0;
      for (const child of children) {
        total += computeSubtreeHeight(child);
      }
      return Math.max(total, (NODE_BASE_HEIGHT[n.level] || 90) + VERTICAL_GAP);
    }

    const calculated: LayoutNode[] = [];

    // Helper: position subtree
    function positionSubtree(n: MindMapNodeItem, startY: number): number {
      const height = computeSubtreeHeight(n);
      const isCollapsed = collapsedIds.has(n.id);
      const children = isCollapsed ? [] : childrenMap.get(n.id) || [];

      const baseH = NODE_BASE_HEIGHT[n.level] || 90;
      const width = NODE_WIDTH[n.level] || 280;
      const x = LEVEL_X[n.level] || 60;

      let myY = startY + (height - baseH) / 2;

      calculated.push({
        ...n,
        x,
        y: myY,
        width,
        height: baseH,
        subtreeHeight: height,
        visible: true,
      });

      let currentChildY = startY;
      for (const child of children) {
        const childSubtreeH = computeSubtreeHeight(child);
        positionSubtree(child, currentChildY);
        currentChildY += childSubtreeH;
      }

      return height;
    }

    positionSubtree(root, 40);
    return calculated;
  }, [tree.nodes, collapsedIds]);

  // Compute Layout Edges (Bezier paths)
  const layoutEdges = useMemo(() => {
    const visibleMap = new Map<string, LayoutNode>();
    layoutNodes.forEach((n) => visibleMap.set(n.id, n));

    const edges: Array<{
      id: string;
      source: string;
      target: string;
      path: string;
      startX: number;
      startY: number;
      endX: number;
      endY: number;
      isActive: boolean;
      sourceNode: LayoutNode;
    }> = [];

    tree.edges.forEach((edge) => {
      const source = visibleMap.get(edge.source);
      const target = visibleMap.get(edge.target);

      if (source && target) {
        const startX = source.x + source.width;
        const startY = source.y + source.height / 2;
        const endX = target.x;
        const endY = target.y + target.height / 2;

        const dx = endX - startX;
        // Smooth Cubic Bezier S-curve
        const path = `M ${startX} ${startY} C ${startX + dx * 0.45} ${startY}, ${startX + dx * 0.55} ${endY}, ${endX} ${endY}`;

        const isActive = activeBranchIds.has(source.id) && activeBranchIds.has(target.id);

        edges.push({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          path,
          startX,
          startY,
          endX,
          endY,
          isActive,
          sourceNode: source,
        });
      }
    });

    return edges;
  }, [layoutNodes, tree.edges, activeBranchIds]);

  // Pan interaction handlers with window listeners for smooth, continuous dragging
  const handlePointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    // Support left mouse button (0), right mouse button (2), or touch
    if (e.button !== 0 && e.button !== 2 && e.pointerType !== 'touch') {
      return;
    }

    const target = e.target as HTMLElement;
    // Do not initiate canvas pan if user clicked on a node card, button, link, or input
    if (
      target.closest('[data-node-card="true"]') ||
      target.closest('button') ||
      target.closest('a') ||
      target.closest('input')
    ) {
      return;
    }

    // Prevent default selection during drag
    e.preventDefault();

    isDraggingRef.current = true;
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - panRef.current.x, y: e.clientY - panRef.current.y };
    dragInitialPosRef.current = { x: e.clientX, y: e.clientY };
    hasDraggedRef.current = false;

    const onPointerMove = (ev: PointerEvent) => {
      if (!isDraggingRef.current) return;

      const dx = Math.abs(ev.clientX - dragInitialPosRef.current.x);
      const dy = Math.abs(ev.clientY - dragInitialPosRef.current.y);
      if (dx > 2 || dy > 2) {
        hasDraggedRef.current = true;
      }

      const nextPan = {
        x: ev.clientX - dragStartRef.current.x,
        y: ev.clientY - dragStartRef.current.y,
      };
      panRef.current = nextPan;
      setPan(nextPan);
    };

    const onPointerUp = () => {
      isDraggingRef.current = false;
      setIsDragging(false);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('pointercancel', onPointerUp);
    };

    window.addEventListener('pointermove', onPointerMove, { passive: true });
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerUp);
  }, []);

  const handleContextMenu = (e: React.MouseEvent) => {
    // Suppress context menu if the user was right-click dragging the canvas
    if (hasDraggedRef.current) {
      e.preventDefault();
      e.stopPropagation();
    }
  };

  // Wheel zoom handler
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
    setZoom((prev) => Math.min(Math.max(prev * zoomFactor, 0.35), 2.0));
  };

  // Fit to screen
  const initialViewRoot = useRef<string | null>(null);
  useEffect(() => {
    const root = layoutNodes.find(node => node.level === 0);
    if (!root || !containerRef.current || initialViewRoot.current === root.id) return;
    initialViewRoot.current = root.id;
    const height = containerRef.current.clientHeight;
    // Start at the root; preserve user-controlled pan/zoom after this initial framing.
    setPan({ x: 32 - root.x * 0.85, y: (height - root.height * 0.85) / 2 - root.y * 0.85 });
  }, [layoutNodes]);

  const fitToScreen = useCallback(() => {
    if (!containerRef.current || layoutNodes.length === 0) return;
    const rect = containerRef.current.getBoundingClientRect();

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;

    layoutNodes.forEach((n) => {
      minX = Math.min(minX, n.x);
      maxX = Math.max(maxX, n.x + n.width);
      minY = Math.min(minY, n.y);
      maxY = Math.max(maxY, n.y + n.height);
    });

    const contentWidth = maxX - minX + 100;
    const contentHeight = maxY - minY + 100;

    const scaleX = rect.width / contentWidth;
    const scaleY = rect.height / contentHeight;
    const newZoom = Math.min(Math.max(Math.min(scaleX, scaleY) * 0.9, 0.4), 1.2);

    setZoom(newZoom);
    setPan({
      x: (rect.width - contentWidth * newZoom) / 2 - minX * newZoom + 40,
      y: (rect.height - contentHeight * newZoom) / 2 - minY * newZoom + 40,
    });
  }, [layoutNodes]);

  const resetView = useCallback(() => {
    setZoom(0.85);
    setPan({ x: 80, y: 120 });
  }, []);

  // Compute status badge
  const renderStatusBadge = (status?: string) => {
    switch (status) {
      case 'learned':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-800/80 px-2 py-0.5 rounded-full">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            Learned
          </span>
        );
      case 'in_progress':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-950/60 border border-amber-800/80 px-2 py-0.5 rounded-full">
            <Clock className="w-3 h-3 text-amber-400" />
            In Progress
          </span>
        );
      case 'needs_revision':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-400 bg-rose-950/60 border border-rose-800/80 px-2 py-0.5 rounded-full">
            <AlertCircle className="w-3 h-3 text-rose-400" />
            Revision
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-text-muted bg-surface-muted/60 border border-border/60 px-2 py-0.5 rounded-full">
            <HelpCircle className="w-3 h-3 text-text-muted" />
            Not Started
          </span>
        );
    }
  };

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full overflow-hidden select-none bg-background ${className}`}
      onPointerDown={handlePointerDown}
      onContextMenu={handleContextMenu}
      onWheel={handleWheel}
      style={{
        cursor: isDragging ? 'grabbing' : 'grab',
        touchAction: 'none',
      }}
    >
      {/* Subtle Dot Grid Background */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-40">
        <defs>
          <pattern id="mindmap-dots" width="28" height="28" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1.2" fill="#334155" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#mindmap-dots)" />
      </svg>

      {/* Floating Canvas Controls */}
      <div className="mindmap-toolbar absolute top-4 right-4 z-30 flex items-center gap-2 bg-surface/90 backdrop-blur-md border border-border/80 rounded-xl p-1.5 shadow-xl">
        <Button
          variant="ghost"
          size="sm"
          className="h-8 px-2.5 text-xs text-text-secondary hover:text-text-primary hover:bg-surface-muted"
          onClick={expandAll}
          title="Expand all branches"
        >
          <ChevronRight className="w-3.5 h-3.5 mr-1 text-primary" />
          Expand All
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 px-2.5 text-xs text-text-secondary hover:text-text-primary hover:bg-surface-muted"
          onClick={collapseAll}
          title="Collapse to main topics"
        >
          <ChevronLeft className="w-3.5 h-3.5 mr-1 text-text-muted" />
          Collapse
        </Button>
        <div className="w-[1px] h-5 bg-surface-muted mx-0.5" />
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-text-secondary hover:text-text-primary hover:bg-surface-muted"
          onClick={() => setZoom((z) => Math.min(z + 0.15, 2.0))}
          title="Zoom in"
        >
          <ZoomIn className="w-4 h-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-text-secondary hover:text-text-primary hover:bg-surface-muted"
          onClick={() => setZoom((z) => Math.max(z - 0.15, 0.35))}
          title="Zoom out"
        >
          <ZoomOut className="w-4 h-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-text-secondary hover:text-text-primary hover:bg-surface-muted"
          onClick={fitToScreen}
          title="Fit mind map to screen"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-text-secondary hover:text-text-primary hover:bg-surface-muted"
          onClick={resetView}
          title="Reset zoom and position"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </Button>
        <div className="px-2 text-[11px] font-mono text-text-muted">
          {Math.round(zoom * 100)}%
        </div>
      </div>

      {/* Breadcrumb Info Bar */}
      <div className="mindmap-info absolute top-4 left-4 z-30 flex items-center gap-2 bg-surface/80 backdrop-blur-md border border-border/80 rounded-xl px-3 py-1.5 shadow-lg text-xs">
        <span className="flex items-center gap-1.5 text-text-muted font-medium">
          <BookOpen className="w-3.5 h-3.5 text-primary" />
          Knovera Mind Map
        </span>
        <span className="text-text-muted" aria-hidden="true">·</span>
        <span className="text-text-secondary">
          {tree.nodes.length} concepts ({tree.total_leaves} facts)
        </span>
      </div>

      {/* Main Pan/Zoom World Container */}
      <div
        className="absolute inset-0 origin-top-left"
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transition: isDragging ? 'none' : 'transform 120ms cubic-bezier(0.2, 0, 0, 1)',
          width: '4000px',
          height: '4000px',
        }}
      >
        {/* SVG Connector Lines */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ width: '4000px', height: '4000px' }}
        >
          <defs>
            <linearGradient id="active-line-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="var(--primary)" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>
          </defs>

          {layoutEdges.map((edge) => (
            <g key={edge.id}>
              {/* Glow filter for active branch */}
              {edge.isActive && (
                <path
                  d={edge.path}
                  fill="none"
                  stroke="var(--primary)"
                  strokeWidth="6"
                  strokeOpacity="0.25"
                  strokeLinecap="round"
                />
              )}
              {/* Main Bezier Line */}
              <path
                d={edge.path}
                fill="none"
                stroke={edge.isActive ? 'url(#active-line-gradient)' : 'var(--border)'}
                strokeWidth={edge.isActive ? '2.5' : '1.8'}
                strokeOpacity={edge.isActive ? 1 : 0.65}
                strokeLinecap="round"
              />
            </g>
          ))}
        </svg>

        {/* HTML Node Cards Layer */}
        {layoutNodes.map((node) => {
          const isSelected = selectedNodeId === node.id;
          const isInActiveBranch = activeBranchIds.has(node.id);
          const isCollapsed = collapsedIds.has(node.id);
          const hasChildren = node.children_count > 0;

          const isSearchMatch = Boolean(
            searchQuery.trim() &&
              (node.label.toLowerCase().includes(searchQuery.toLowerCase().trim()) ||
                (node.description && node.description.toLowerCase().includes(searchQuery.toLowerCase().trim())) ||
                (node.summary && node.summary.toLowerCase().includes(searchQuery.toLowerCase().trim())))
          );

          // Card Styles by Level
          let cardStyle = '';
          if (node.level === 0) {
            // Root
            cardStyle = `bg-gradient-to-br from-surface-elevated via-surface to-surface border-2 ${
              isSelected || isInActiveBranch ? 'border-primary shadow-sky-500/20' : 'border-primary/40'
            } shadow-xl shadow-slate-950/50`;
          } else if (node.level === 1) {
            // Primary Topic
            cardStyle = `bg-surface/95 border ${
              isSelected || isInActiveBranch ? 'border-primary ring-2 ring-primary/20' : 'border-border/80 hover:border-slate-600'
            } shadow-lg shadow-slate-950/40`;
          } else if (node.level === 2) {
            // Secondary Concept
            cardStyle = `bg-surface/90 border ${
              isSelected || isInActiveBranch ? 'border-emerald-400 ring-2 ring-emerald-500/20' : 'border-border hover:border-emerald-700/60'
            } shadow-md shadow-slate-950/30`;
          } else {
            // Leaf Node
            cardStyle = `bg-surface/95 border ${
              isSelected ? 'border-emerald-400 ring-2 ring-emerald-500/20' : 'border-border/80 hover:border-border'
            } shadow-sm`;
          }

          if (isSearchMatch) {
            cardStyle += ' ring-2 ring-amber-400/80 shadow-amber-500/20';
          }

          return (
            <div
              key={node.id}
              data-node-card="true"
              role="button"
              tabIndex={0}
              aria-label={node.label}
              aria-pressed={isSelected}
              onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onSelectNode(node); } }}
              className={`absolute rounded-xl mindmap-node transition-colors duration-150 cursor-pointer ${cardStyle}`}
              style={{
                left: `${node.x}px`,
                top: `${node.y}px`,
                width: `${node.width}px`,
                minHeight: `${node.height}px`,
              }}
              onClick={(e) => {
                e.stopPropagation();
                onSelectNode(node);
              }}
            >
              {/* Level 0: Root Card */}
              {node.level === 0 && (
                <div className="p-4 flex flex-col justify-between h-full">
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-primary uppercase tracking-wider bg-sky-950/70 border border-sky-800/50 px-2 py-0.5 rounded-full">
                      <Sparkles className="w-3 h-3 text-primary" />
                      Central Subject
                    </span>
                    <Badge variant="outline" className="text-[10px] border-border text-text-muted">
                      Root
                    </Badge>
                  </div>
                  <h2 className="text-base font-bold text-text-primary mt-2 line-clamp-2 leading-snug">
                    {node.label}
                  </h2>
                  <div className="mt-2 text-xs text-text-muted line-clamp-1">
                    {node.description || 'Workspace Central Mind Map'}
                  </div>
                </div>
              )}

              {/* Level 1: Primary Topic Card */}
              {node.level === 1 && (
                <div className="p-3.5 flex flex-col justify-between h-full">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] font-medium text-text-muted uppercase tracking-wider bg-surface-muted/70 px-2 py-0.5 rounded-full">
                      {node.category || 'Topic Area'}
                    </span>
                    <span className="text-[11px] text-text-muted font-medium">
                      {node.children_count} concepts
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-text-primary mt-1.5 line-clamp-2">
                    {node.label}
                  </h3>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-[11px] text-text-muted line-clamp-1">
                      {node.description || 'Primary Topic Branch'}
                    </span>
                  </div>
                </div>
              )}

              {/* Level 2: Secondary Concept Card */}
              {node.level === 2 && (
                <div className="p-3 flex flex-col justify-between h-full">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] font-medium text-emerald-400 bg-emerald-950/50 border border-emerald-900/60 px-1.5 py-0.5 rounded">
                      {node.difficulty || 'Concept'}
                    </span>
                    {renderStatusBadge(node.learning_status)}
                  </div>
                  <h4 className="text-sm font-semibold text-text-primary mt-1 line-clamp-2">
                    {node.label}
                  </h4>
                  <div className="mt-1 text-[11px] text-text-muted line-clamp-1">
                    {node.description || node.summary || 'Detailed Subconcept'}
                  </div>
                </div>
              )}

              {/* Level 3: Leaf Node Card */}
              {node.level === 3 && (
                <div className="p-3 flex flex-col justify-between h-full">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] font-medium text-text-muted flex items-center gap-1">
                      <FileText className="w-3 h-3 text-text-muted" />
                      Grounded Fact
                    </span>
                    {renderStatusBadge(node.learning_status)}
                  </div>
                  <h5 className="text-xs font-semibold text-text-primary mt-1 line-clamp-2 leading-relaxed">
                    {node.label}
                  </h5>
                  {node.summary && (
                    <p className="mt-1 text-[11px] text-text-muted line-clamp-2 leading-normal">
                      {node.summary}
                    </p>
                  )}
                </div>
              )}

              {/* Circular Expand/Collapse Junction Toggle Button (< / >) */}
              {hasChildren && (
                <button
                  type="button"
                  className={`absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full border flex items-center justify-center transition-transform shadow-md ${
                    isCollapsed
                      ? 'bg-sky-500 text-slate-950 border-primary hover:bg-sky-400 font-bold'
                      : 'bg-surface text-text-secondary border-border hover:text-text-primary hover:border-slate-500'
                  }`}
                  onClick={(e) => toggleCollapse(node.id, e)}
                  title={isCollapsed ? `Expand ${node.children_count} subtopics` : 'Collapse branch'}
                >
                  {isCollapsed ? (
                    <ChevronRight className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronLeft className="w-3.5 h-3.5" />
                  )}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
