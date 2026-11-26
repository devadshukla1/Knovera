"""Graph Statistics Service for Knovera Knowledge Graph (Phase 7 C7.5).

Computes comprehensive structural, topological, and categorical metrics
for directed multigraph representations (networkx.MultiDiGraph).
"""

from collections import Counter
from typing import Dict
import networkx as nx

from backend.app.ml.knowledge_graph.schemas import GraphStatistics


class GraphStatisticsService:
    """Computes structural metrics and distributions for a knowledge graph."""

    @classmethod
    def calculate_statistics(cls, graph: nx.MultiDiGraph) -> GraphStatistics:
        """Calculates topological and distribution metrics from a MultiDiGraph."""
        total_nodes = graph.number_of_nodes()
        total_edges = graph.number_of_edges()

        if total_nodes == 0:
            return GraphStatistics()

        # Node categorizations
        concept_count = 0
        entity_count = 0
        node_type_counts: Counter = Counter()

        for _, attrs in graph.nodes(data=True):
            kind = attrs.get("node_kind", "concept")
            if kind == "entity":
                entity_count += 1
            else:
                concept_count += 1

            cat = attrs.get("node_type", "unknown")
            node_type_counts[cat] += 1

        # Degree calculations
        in_degrees = [d for _, d in graph.in_degree()]
        out_degrees = [d for _, d in graph.out_degree()]
        total_degrees = [d for _, d in graph.degree()]

        max_in_degree = max(in_degrees) if in_degrees else 0
        max_out_degree = max(out_degrees) if out_degrees else 0
        avg_degree = sum(total_degrees) / total_nodes if total_nodes > 0 else 0.0

        # Isolated nodes (degree == 0)
        isolated_node_count = sum(1 for _, d in graph.degree() if d == 0)

        # Connected components (Weakly connected components for directed graph)
        weakly_connected = nx.number_weakly_connected_components(graph)
        strongly_connected = nx.number_strongly_connected_components(graph)

        # Self-loops
        self_loop_count = nx.number_of_selfloops(graph)

        # Parallel edges count: distinct pair (u, v) with count > 1
        edge_pair_counts: Counter = Counter()
        predicate_counts: Counter = Counter()

        for u, v, k, attrs in graph.edges(data=True, keys=True):
            edge_pair_counts[(u, v)] += 1
            pred = attrs.get("predicate", "unknown")
            predicate_counts[pred] += 1

        parallel_edges = sum(count - 1 for count in edge_pair_counts.values() if count > 1)

        return GraphStatistics(
            total_nodes=total_nodes,
            concept_count=concept_count,
            entity_count=entity_count,
            total_edges=total_edges,
            isolated_node_count=isolated_node_count,
            connected_components_count=weakly_connected,
            strongly_connected_components_count=strongly_connected,
            parallel_edge_count=parallel_edges,
            self_loop_count=self_loop_count,
            average_degree=round(avg_degree, 2),
            max_in_degree=max_in_degree,
            max_out_degree=max_out_degree,
            predicate_distribution=dict(predicate_counts),
            node_type_distribution=dict(node_type_counts),
        )
