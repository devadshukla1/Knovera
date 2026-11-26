"""Knowledge Graph Construction Service for Knovera (Phase 7 C7.5).

Constructs an in-memory directed multigraph (networkx.MultiDiGraph) from
validated canonical knowledge records with complete identity and provenance preservation.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
import networkx as nx

from backend.app.ml.knowledge_graph.graph_statistics import GraphStatisticsService
from backend.app.ml.knowledge_graph.ontology import ONTOLOGY_VERSION, NodeType, infer_node_type
from backend.app.ml.knowledge_graph.relationships import RELATIONSHIP_ONTOLOGY_VERSION
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedRelationship,
    GraphMetadata,
    GraphStatistics,
    NormalizedNode,
    RelationshipValidationStatus,
)

logger = logging.getLogger(__name__)


class KnowledgeGraphBuilder:
    """Constructs, validates, and measures networkx.MultiDiGraph instances."""

    def __init__(self, builder_version: str = "1.0.0") -> None:
        self.builder_version = builder_version

    def build_graph(
        self,
        workspace_id: str,
        nodes: List[NormalizedNode],
        relationships: List[ExtractedRelationship],
        extraction_run_id: Optional[str] = None,
        source_snapshot_hash: Optional[str] = None,
        include_needs_review: bool = False,
    ) -> Tuple[nx.MultiDiGraph, GraphStatistics]:
        """Constructs a deterministic MultiDiGraph from validated knowledge records.

        Args:
            workspace_id: The tenancy scope.
            nodes: Canonical knowledge nodes.
            relationships: Validated candidate relationships.
            extraction_run_id: Optional extraction execution ID.
            source_snapshot_hash: Optional corpus checksum.
            include_needs_review: If True, includes 'needs_review' edges for diagnostic use.

        Returns:
            Tuple of (constructed MultiDiGraph, computed GraphStatistics).
        """
        graph = nx.MultiDiGraph()
        now_iso = datetime.now(timezone.utc).isoformat()
        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"

        # Graph-level attributes
        meta = GraphMetadata(
            snapshot_id=snapshot_id,
            workspace_id=workspace_id,
            extraction_run_id=extraction_run_id,
            ontology_version=ONTOLOGY_VERSION,
            relationship_ontology_version=RELATIONSHIP_ONTOLOGY_VERSION,
            graph_schema_version="1.0.0",
            builder_version=self.builder_version,
            source_snapshot_hash=source_snapshot_hash,
            created_at=now_iso,
        )
        graph.graph.update(meta.model_dump())

        # 1. Deterministic Node Insertion
        # Ensure every node has a stable ID
        node_id_map: Dict[str, str] = {}
        sorted_nodes = sorted(nodes, key=lambda n: (str(n.id or ""), n.name.lower()))

        for n in sorted_nodes:
            n_id = str(n.id) if n.id else f"node_{uuid.uuid5(uuid.NAMESPACE_DNS, f'{workspace_id}:{n.normalized_name}').hex}"
            node_id_map[n.name.strip().lower()] = n_id
            node_id_map[n.normalized_name.strip().lower()] = n_id
            for alias in n.aliases:
                node_id_map[alias.strip().lower()] = n_id

            # Resolve node_kind as either 'concept' or 'entity'
            if n.node_type in {NodeType.CONCEPT.value, NodeType.ENTITY.value}:
                node_kind = n.node_type
            elif n.category:
                node_kind = infer_node_type(n.category).value
            else:
                node_kind = NodeType.CONCEPT.value

            graph.add_node(
                n_id,
                node_id=n_id,
                label=n.name,
                normalized_name=n.normalized_name,
                node_kind=node_kind,
                node_type=n.category,
                workspace_id=workspace_id,
                description=n.description,
                aliases=sorted(list(set(n.aliases))),
                ontology_version=ONTOLOGY_VERSION,
            )

        # 2. Filter Eligible Relationships
        allowed_statuses = {RelationshipValidationStatus.VALIDATED.value, "valid", "validated"}
        if include_needs_review:
            allowed_statuses.add(RelationshipValidationStatus.NEEDS_REVIEW.value)

        eligible_relationships = [
            r for r in relationships
            if r.validation_status in allowed_statuses
        ]

        # 3. Deterministic Edge Insertion
        # Sort edges by source, predicate, target, and relationship ID
        sorted_edges = sorted(
            eligible_relationships,
            key=lambda r: (
                r.source_node_name.lower(),
                r.predicate.lower(),
                r.target_node_name.lower(),
                str(r.id or ""),
            ),
        )

        for rel in sorted_edges:
            src_id = str(rel.source_node_id) if rel.source_node_id else node_id_map.get(rel.source_node_name.strip().lower())
            tgt_id = str(rel.target_node_id) if rel.target_node_id else node_id_map.get(rel.target_node_name.strip().lower())

            if not src_id or not tgt_id:
                logger.warning(
                    "Skipping edge (%s -> %s): could not resolve node IDs",
                    rel.source_node_name,
                    rel.target_node_name,
                )
                continue

            if not graph.has_node(src_id) or not graph.has_node(tgt_id):
                logger.warning(
                    "Skipping edge (%s -> %s): node IDs not found in graph nodes",
                    src_id,
                    tgt_id,
                )
                continue

            # Stable edge key
            edge_key = str(rel.id) if rel.id else f"rel_{src_id[:8]}_{rel.predicate}_{tgt_id[:8]}_{uuid.uuid4().hex[:6]}"

            # Evidence references
            evidence_ids = []
            chunk_ids = []
            for ev in rel.evidence:
                if hasattr(ev, "id") and ev.id:
                    evidence_ids.append(str(ev.id))
                if ev.chunk_id:
                    chunk_ids.append(str(ev.chunk_id))

            graph.add_edge(
                src_id,
                tgt_id,
                key=edge_key,
                relationship_id=edge_key,
                predicate=rel.predicate,
                inverse_predicate=rel.inverse_predicate,
                polarity="negative" if rel.is_negated else "positive",
                is_negated=rel.is_negated,
                modality=rel.modality,
                qualifiers=rel.qualifiers,
                evidence_ids=sorted(list(set(evidence_ids))),
                source_chunk_ids=sorted(list(set(chunk_ids))),
                confidence=rel.confidence,
                validation_status=rel.validation_status,
                extraction_run_id=extraction_run_id,
                workspace_id=workspace_id,
            )

        # 4. Graph Integrity Validation
        self.verify_graph_integrity(graph)

        # 5. Graph Statistics Calculation
        stats = GraphStatisticsService.calculate_statistics(graph)

        logger.info(
            "Constructed MultiDiGraph for workspace %s: %d nodes, %d edges, %d parallel edges",
            workspace_id,
            stats.total_nodes,
            stats.total_edges,
            stats.parallel_edge_count,
        )

        return graph, stats

    def verify_graph_integrity(self, graph: nx.MultiDiGraph) -> None:
        """Enforces structural integrity on the constructed MultiDiGraph.

        Raises ValueError if structural defects or dangling references exist.
        """
        for u, v, k, attrs in graph.edges(data=True, keys=True):
            if not graph.has_node(u):
                raise ValueError(f"Dangling edge: source node {u} does not exist in graph")
            if not graph.has_node(v):
                raise ValueError(f"Dangling edge: target node {v} does not exist in graph")
            if "predicate" not in attrs:
                raise ValueError(f"Edge {k} missing required 'predicate' attribute")
            if "relationship_id" not in attrs:
                raise ValueError(f"Edge {k} missing required 'relationship_id' attribute")
