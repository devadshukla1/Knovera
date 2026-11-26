"""Graph Serialization Service for Knovera Knowledge Graph (Phase 7 C7.6).

Converts NetworkX MultiDiGraph instances into deterministic, versioned,
cryptographically verified JSON snapshot documents.
"""

import hashlib
import json
import platform
from typing import Any, Dict, List, Tuple
import networkx as nx

from backend.app.ml.knowledge_graph.graph_statistics import GraphStatisticsService
from backend.app.ml.knowledge_graph.schemas import (
    GraphEdgeData,
    GraphMetadata,
    GraphNodeData,
    GraphSnapshotManifest,
    GraphStatistics,
    SerializedGraphDocument,
)


class GraphSerializer:
    """Serializes MultiDiGraph instances into deterministic JSON snapshot artifacts."""

    @classmethod
    def serialize_graph(
        cls,
        graph: nx.MultiDiGraph,
        statistics: GraphStatistics,
        validation_policy_version: str = "1.0.0",
    ) -> Tuple[str, str, GraphSnapshotManifest]:
        """Serializes graph to deterministic JSON string, SHA-256 checksum, and Manifest.

        Returns:
            Tuple of (json_content, sha256_checksum, manifest).
        """
        # 1. Extract and sort nodes deterministically
        nodes_list: List[GraphNodeData] = []
        for node_id, attrs in graph.nodes(data=True):
            node_data = GraphNodeData(
                id=str(node_id),
                label=attrs.get("label", str(node_id)),
                normalized_name=attrs.get("normalized_name", str(node_id).lower()),
                node_kind=attrs.get("node_kind", "concept"),
                node_type=attrs.get("node_type", "technical_concept"),
                workspace_id=attrs.get("workspace_id", ""),
                description=attrs.get("description"),
                aliases=sorted(list(set(attrs.get("aliases", [])))),
                ontology_version=attrs.get("ontology_version", "1.0.0"),
            )
            nodes_list.append(node_data)

        sorted_nodes = sorted(nodes_list, key=lambda n: n.id)

        # 2. Extract and sort edges deterministically
        edges_list: List[GraphEdgeData] = []
        for u, v, k, attrs in graph.edges(data=True, keys=True):
            edge_data = GraphEdgeData(
                id=str(attrs.get("relationship_id", k)),
                source=str(u),
                target=str(v),
                predicate=attrs.get("predicate", "related_to"),
                inverse_predicate=attrs.get("inverse_predicate"),
                polarity=attrs.get("polarity", "positive"),
                is_negated=attrs.get("is_negated", False),
                modality=attrs.get("modality", "certain"),
                qualifiers=attrs.get("qualifiers", {}),
                evidence_ids=sorted(list(set(attrs.get("evidence_ids", [])))),
                source_chunk_ids=sorted(list(set(attrs.get("source_chunk_ids", [])))),
                confidence=attrs.get("confidence", 1.0),
                validation_status=attrs.get("validation_status", "validated"),
                extraction_run_id=attrs.get("extraction_run_id"),
                workspace_id=attrs.get("workspace_id", ""),
            )
            edges_list.append(edge_data)

        sorted_edges = sorted(
            edges_list,
            key=lambda e: (e.source, e.predicate, e.target, e.id),
        )

        # 3. Construct GraphMetadata
        g_meta_dict = graph.graph
        meta = GraphMetadata(
            snapshot_id=g_meta_dict.get("snapshot_id", ""),
            workspace_id=g_meta_dict.get("workspace_id", ""),
            extraction_run_id=g_meta_dict.get("extraction_run_id"),
            ontology_version=g_meta_dict.get("ontology_version", "1.0.0"),
            relationship_ontology_version=g_meta_dict.get("relationship_ontology_version", "1.0.0"),
            graph_schema_version=g_meta_dict.get("graph_schema_version", "1.0.0"),
            builder_version=g_meta_dict.get("builder_version", "1.0.0"),
            source_snapshot_hash=g_meta_dict.get("source_snapshot_hash"),
            created_at=g_meta_dict.get("created_at", ""),
        )

        doc = SerializedGraphDocument(
            schema_version="1.0.0",
            graph=meta,
            nodes=sorted_nodes,
            edges=sorted_edges,
            statistics=statistics,
        )

        # Deterministic JSON dump
        json_str = json.dumps(
            doc.model_dump(),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )

        # Compute SHA-256 checksum over exact bytes
        checksum = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

        # Build Manifest
        manifest = GraphSnapshotManifest(
            snapshot_id=meta.snapshot_id,
            workspace_id=meta.workspace_id,
            extraction_run_id=meta.extraction_run_id,
            source_snapshot_hash=meta.source_snapshot_hash,
            validation_policy_version=validation_policy_version,
            ontology_version=meta.ontology_version,
            relationship_ontology_version=meta.relationship_ontology_version,
            graph_schema_version=meta.graph_schema_version,
            builder_version=meta.builder_version,
            serialization_format="json_node_link",
            created_at=meta.created_at,
            statistics=statistics,
            artifact_checksum=checksum,
            python_version=platform.python_version(),
            networkx_version=nx.__version__,
        )

        return json_str, checksum, manifest
