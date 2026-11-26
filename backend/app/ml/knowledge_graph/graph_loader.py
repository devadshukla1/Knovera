"""Graph Deserialization and Loader Service for Knovera Knowledge Graph (Phase 7 C7.6).

Reconstructs networkx.MultiDiGraph instances from serialized JSON artifacts,
verifying cryptographic checksums, schema validity, and graph integrity.
"""

import hashlib
import json
import logging
from typing import Optional
import networkx as nx

from backend.app.ml.knowledge_graph.schemas import SerializedGraphDocument

logger = logging.getLogger(__name__)


class GraphLoader:
    """Loads and reconstructs MultiDiGraph from versioned JSON snapshot content."""

    @classmethod
    def load_from_json(
        cls,
        json_content: str,
        expected_checksum: Optional[str] = None,
    ) -> nx.MultiDiGraph:
        """Parses and reconstructs a MultiDiGraph from JSON string.

        Args:
            json_content: The serialized JSON graph string.
            expected_checksum: Optional SHA-256 checksum to verify.

        Raises:
            ValueError: If checksum mismatches, schema fails, or graph integrity fails.
        """
        # 1. Checksum verification if provided
        if expected_checksum:
            actual_checksum = hashlib.sha256(json_content.encode("utf-8")).hexdigest()
            if actual_checksum != expected_checksum:
                raise ValueError(
                    f"Graph artifact checksum mismatch: expected {expected_checksum}, got {actual_checksum}"
                )

        # 2. Schema validation
        data = json.loads(json_content)
        doc = SerializedGraphDocument.model_validate(data)

        # 3. Construct MultiDiGraph
        graph = nx.MultiDiGraph()
        graph.graph.update(doc.graph.model_dump())

        # Add nodes
        for node in doc.nodes:
            graph.add_node(
                node.id,
                node_id=node.id,
                label=node.label,
                normalized_name=node.normalized_name,
                node_kind=node.node_kind,
                node_type=node.node_type,
                workspace_id=node.workspace_id,
                description=node.description,
                aliases=node.aliases,
                ontology_version=node.ontology_version,
            )

        # Add edges
        for edge in doc.edges:
            graph.add_edge(
                edge.source,
                edge.target,
                key=edge.id,
                relationship_id=edge.id,
                predicate=edge.predicate,
                inverse_predicate=edge.inverse_predicate,
                polarity=edge.polarity,
                is_negated=edge.is_negated,
                modality=edge.modality,
                qualifiers=edge.qualifiers,
                evidence_ids=edge.evidence_ids,
                source_chunk_ids=edge.source_chunk_ids,
                confidence=edge.confidence,
                validation_status=edge.validation_status,
                extraction_run_id=edge.extraction_run_id,
                workspace_id=edge.workspace_id,
            )

        # 4. Enforce structural integrity
        cls.verify_integrity(graph)

        return graph

    @classmethod
    def verify_integrity(cls, graph: nx.MultiDiGraph) -> None:
        """Verifies graph endpoints and essential attributes."""
        for u, v, k, attrs in graph.edges(data=True, keys=True):
            if not graph.has_node(u):
                raise ValueError(f"Integrity error: source node {u} missing from graph")
            if not graph.has_node(v):
                raise ValueError(f"Integrity error: target node {v} missing from graph")
            if "predicate" not in attrs:
                raise ValueError(f"Integrity error: edge {k} missing predicate")
