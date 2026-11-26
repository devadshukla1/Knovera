/**
 * Cytoscape.js interactive graph canvas for Knovera (Phase 7 C7.8).
 */

import React, { useEffect, useRef } from 'react';
import cytoscape, { Core, EventObject } from 'cytoscape';
import { GraphEdgeItem, GraphNodeItem } from '../types/knowledgeGraph';
import { cn } from '@/lib/utils';

export interface GraphCanvasProps {
  nodes: GraphNodeItem[];
  edges: GraphEdgeItem[];
  selectedNodeId?: string | null;
  selectedEdgeId?: string | null;
  onSelectNode?: (nodeId: string | null) => void;
  onSelectEdge?: (edgeId: string | null) => void;
  layoutName?: 'cose' | 'concentric' | 'breadthfirst' | 'grid';
  className?: string;
  zoomLevel?: number;
  onCyReady?: (cy: Core) => void;
}

// Category-based color palette adhering to Knovera theme
export function getNodeCategoryColor(nodeKind: string, nodeType?: string | null): string {
  const t = (nodeType || '').toLowerCase();
  if (t === 'algorithm') return '#3b82f6'; // Blue
  if (t === 'model') return '#8b5cf6'; // Violet
  if (t === 'dataset') return '#f59e0b'; // Amber
  if (t === 'technology' || t === 'software') return '#06b6d4'; // Cyan
  if (t === 'programming_language') return '#10b981'; // Emerald
  if (t === 'metric') return '#ec4899'; // Pink
  if (t === 'organization') return '#6366f1'; // Indigo
  if (t === 'person') return '#f43f5e'; // Rose

  if (nodeKind === 'entity') return '#14b8a6'; // Teal
  return '#8b5cf6'; // Violet (concept default)
}

export function getNodeStatusBorderColor(status?: string): string {
  if (status === 'learned') return '#10b981'; // Emerald
  if (status === 'in_progress') return '#06b6d4'; // Cyan
  if (status === 'needs_revision') return '#f59e0b'; // Amber
  return '#475569'; // Slate for not_started
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  nodes,
  edges,
  selectedNodeId,
  selectedEdgeId,
  onSelectNode,
  onSelectEdge,
  layoutName = 'cose',
  className,
  onCyReady,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  // Initialize or update Cytoscape
  useEffect(() => {
    if (!containerRef.current) return;

    if (!cyRef.current) {
      const cy = cytoscape({
        container: containerRef.current,
        style: [
          {
            selector: 'node',
            style: {
              'label': 'data(label)',
              'text-valign': 'bottom',
              'text-margin-y': 6,
              'color': '#cbd5e1', // Slate-300
              'font-size': '11px',
              'font-family': 'Inter, system-ui, sans-serif',
              'font-weight': 500,
              'text-wrap': 'ellipsis',
              'text-max-width': '120px',
              'background-color': 'data(bgColor)',
              'border-width': 2,
              'border-color': 'data(borderColor)',
              'width': 'data(size)',
              'height': 'data(size)',
              'transition-property': 'background-color, border-color, border-width, width, height',
              'transition-duration': 0.2,
            },
          },
          {
            selector: 'node:selected, node.highlighted',
            style: {
              'border-width': 4,
              'border-color': '#f8fafc',
              'color': '#ffffff',
              'font-weight': 700,
              'underlay-color': '#ffffff',
              'underlay-padding': 6,
              'underlay-opacity': 0.35,
              'z-index': 999,
            },
          },
          {
            selector: 'node.connected-neighbor',
            style: {
              'border-width': 3,
              'border-color': '#a78bfa',
              'color': '#f1f5f9',
            },
          },
          {
            selector: 'edge',
            style: {
              'width': 2,
              'line-color': '#475569', // Slate-600
              'target-arrow-color': '#475569',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              'label': 'data(predicate)',
              'font-size': '9px',
              'color': '#94a3b8',
              'font-family': 'Inter, system-ui, sans-serif',
              'text-rotation': 'autorotate',
              'text-background-opacity': 0.85,
              'text-background-color': '#0f172a',
              'text-background-padding': '2px',
              'text-background-shape': 'roundrectangle',
              'arrow-scale': 1.1,
              'transition-property': 'line-color, target-arrow-color, width',
              'transition-duration': 0.2,
            },
          },
          {
            selector: 'edge:selected, edge.highlighted',
            style: {
              'width': 3.5,
              'line-color': '#8b5cf6', // Violet
              'target-arrow-color': '#8b5cf6',
              'color': '#ffffff',
              'font-weight': 600,
              'z-index': 990,
            },
          },
          {
            selector: 'edge.negated',
            style: {
              'line-style': 'dashed',
              'line-color': '#f43f5e',
              'target-arrow-color': '#f43f5e',
            },
          },
        ],
        elements: [],
        layout: { name: 'grid' },
        minZoom: 0.2,
        maxZoom: 3.5,
        wheelSensitivity: 0.3,
      });

      // Events
      cy.on('tap', 'node', (evt: EventObject) => {
        const nodeId = evt.target.id();
        if (onSelectNode) onSelectNode(nodeId);
      });

      cy.on('tap', 'edge', (evt: EventObject) => {
        const edgeId = evt.target.id();
        if (onSelectEdge) onSelectEdge(edgeId);
      });

      cy.on('tap', (evt: EventObject) => {
        if (evt.target === cy) {
          if (onSelectNode) onSelectNode(null);
          if (onSelectEdge) onSelectEdge(null);
        }
      });

      cyRef.current = cy;
      if (onCyReady) onCyReady(cy);
    }

    const cy = cyRef.current;
    if (!cy) return;

    // Convert nodes and edges into Cytoscape elements
    const elements: cytoscape.ElementDefinition[] = [];

    nodes.forEach((n) => {
      const color = getNodeCategoryColor(n.node_kind, n.node_type);
      const degree = n.degree || 0;
      const size = Math.min(Math.max(26 + degree * 3, 26), 56);

      elements.push({
        group: 'nodes',
        data: {
          id: n.id,
          label: n.label,
          nodeKind: n.node_kind,
          nodeType: n.node_type || '',
          bgColor: color,
          borderColor: n.learning_status ? getNodeStatusBorderColor(n.learning_status) : (color === '#8b5cf6' ? '#a78bfa' : '#38bdf8'),
          size: size,
        },
      });
    });

    edges.forEach((e) => {
      elements.push({
        group: 'edges',
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          predicate: e.predicate,
          isNegated: e.is_negated,
        },
        classes: e.is_negated ? 'negated' : '',
      });
    });

    // Update Cytoscape elements gracefully (batching)
    cy.batch(() => {
      cy.elements().remove();
      cy.add(elements);
    });

    // Run configured layout
    const layout = cy.layout({
      name: layoutName,
      animate: true,
      animationDuration: 400,
      fit: true,
      padding: 40,
    } as any);

    layout.run();
  }, [nodes, edges, layoutName]);

  // Synchronize selection and connection highlighting
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().removeClass('highlighted connected-neighbor');

    if (selectedNodeId && cy.hasElementWithId(selectedNodeId)) {
      const selNode = cy.getElementById(selectedNodeId);
      selNode.addClass('highlighted');

      // Highlight adjacent edges and direct neighbors
      const connectedEdges = selNode.connectedEdges();
      connectedEdges.addClass('highlighted');
      connectedEdges.connectedNodes().forEach((nbr) => {
        if (nbr.id() !== selectedNodeId) {
          nbr.addClass('connected-neighbor');
        }
      });
    }

    if (selectedEdgeId && cy.hasElementWithId(selectedEdgeId)) {
      const selEdge = cy.getElementById(selectedEdgeId);
      selEdge.addClass('highlighted');
      selEdge.connectedNodes().addClass('connected-neighbor');
    }
  }, [selectedNodeId, selectedEdgeId]);

  return (
    <div
      ref={containerRef}
      className={cn(
        'w-full h-full relative bg-surface-muted/40 overflow-hidden cursor-grab active:cursor-grabbing',
        className
      )}
      role="region"
      aria-label="Interactive Knowledge Graph Canvas"
    />
  );
};
