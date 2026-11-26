"""Knowledge Graph Service for Knovera (Phase 7 C7.7).

Provides authenticated, workspace-scoped graph querying, bounded traversal,
node search, relationship inspection, source evidence attribution, and path exploration.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
import networkx as nx
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from backend.app.core.logging import get_logger
from backend.app.ml.knowledge_graph.graph_persistence import GraphPersistenceService
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_graph_snapshot import KnowledgeGraphSnapshot
from backend.app.models.knowledge_mention import KnowledgeMention
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.knowledge_relationship import KnowledgeRelationship
from backend.app.models.relationship_evidence import RelationshipEvidence
from backend.app.repositories.knowledge_graph_snapshot_repository import (
    KnowledgeGraphSnapshotRepository,
)
from backend.app.schemas.knowledge_graph import (
    GraphCapabilities,
    GraphEdgeItem,
    GraphNeighborhoodResponse,
    GraphNodeDetailResponse,
    GraphNodeItem,
    GraphPathItem,
    GraphPathStep,
    GraphPathsResponse,
    GraphRelationshipDetailResponse,
    GraphSnapshotSummaryItem,
    GraphStatisticsSummary,
    KnowledgeGraphOverviewResponse,
    NodeMentionItem,
    PaginatedGraphNodesResponse,
    PaginatedGraphRelationshipsResponse,
    PaginatedGraphSnapshotsResponse,
    PaginatedNodeMentionsResponse,
    PaginatedRelationshipEvidenceResponse,
    RelationshipEvidenceItem,
)

logger = get_logger("knovera.services.knowledge_graph")


def _is_valid_uuid(val: Any) -> bool:
    """Checks whether a string or value can parse as valid UUID."""
    if not val:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError):
        return False


class KnowledgeGraphService:
    """Service orchestrating graph loading, traversal, searching, and source hydration."""

    _CACHE_MAX_SIZE = 20
    _graph_cache: OrderedDict[Tuple[str, str], Tuple[nx.MultiDiGraph, KnowledgeGraphSnapshot]] = OrderedDict()

    def __init__(self, persistence_service: Optional[GraphPersistenceService] = None) -> None:
        self.persistence = persistence_service or GraphPersistenceService()

    @classmethod
    def clear_cache(cls) -> None:
        """Clears the in-memory graph snapshot cache."""
        cls._graph_cache.clear()

    def _get_or_load_graph(
        self,
        workspace_id: uuid.UUID,
        snapshot_id: Optional[uuid.UUID],
        session: Session,
    ) -> Tuple[Optional[nx.MultiDiGraph], Optional[KnowledgeGraphSnapshot]]:
        """Retrieves graph from bounded in-process cache or loads from storage."""
        ws_str = str(workspace_id)
        snap_repo = KnowledgeGraphSnapshotRepository(session)

        # 1. Resolve target snapshot record
        target_snapshot: Optional[KnowledgeGraphSnapshot] = None
        if snapshot_id:
            target_snapshot = snap_repo.get_snapshot_by_id(snapshot_id)
            if not target_snapshot or target_snapshot.workspace_id != workspace_id:
                return None, None
        else:
            target_snapshot = snap_repo.get_active_snapshot(workspace_id)
            if not target_snapshot:
                return None, None

        cache_key = (ws_str, str(target_snapshot.id))
        if cache_key in self._graph_cache:
            self._graph_cache.move_to_end(cache_key)
            return self._graph_cache[cache_key]

        # 2. Load from storage
        result = self.persistence.load_snapshot(
            workspace_id=ws_str,
            snapshot_id=str(target_snapshot.id),
            session=session,
        )

        if not result:
            return None, target_snapshot

        graph, loaded_snap = result

        # Cache management (LRU eviction)
        if len(self._graph_cache) >= self._CACHE_MAX_SIZE:
            self._graph_cache.popitem(last=False)
        self._graph_cache[cache_key] = (graph, loaded_snap)

        return graph, loaded_snap

    # -----------------------------------------------------------------------
    # Endpoint A: Graph Overview
    # -----------------------------------------------------------------------

    def get_graph_overview(
        self,
        workspace_id: uuid.UUID,
        snapshot_id: Optional[uuid.UUID],
        session: Session,
    ) -> KnowledgeGraphOverviewResponse:
        """Returns overview metadata, statistics, and capabilities for workspace graph."""
        graph, snapshot = self._get_or_load_graph(workspace_id, snapshot_id, session)

        if not snapshot:
            return KnowledgeGraphOverviewResponse(
                workspace_id=str(workspace_id),
                has_graph=False,
                snapshot=None,
                statistics=None,
                capabilities=GraphCapabilities(),
            )

        snap_summary = GraphSnapshotSummaryItem(
            id=str(snapshot.id),
            status=snapshot.status,
            is_active=snapshot.is_active,
            created_at=snapshot.created_at.isoformat() if snapshot.created_at else "",
            completed_at=snapshot.completed_at.isoformat() if snapshot.completed_at else None,
            node_count=snapshot.node_count,
            edge_count=snapshot.edge_count,
            concept_count=snapshot.concept_count,
            entity_count=snapshot.entity_count,
            component_count=snapshot.component_count,
            isolated_node_count=snapshot.isolated_node_count,
            extraction_run_id=str(snapshot.extraction_run_id) if snapshot.extraction_run_id else None,
            ontology_version=snapshot.ontology_version,
        )

        raw_stats = snapshot.graph_statistics or {}
        stats_summary = GraphStatisticsSummary(
            isolated_node_count=raw_stats.get("isolated_node_count", snapshot.isolated_node_count),
            connected_component_count=raw_stats.get("connected_components_count", snapshot.component_count),
            density=raw_stats.get("density", 0.0),
            self_loops_count=raw_stats.get("self_loops_count", 0),
            parallel_edges_count=raw_stats.get("parallel_edges_count", 0),
            predicate_distribution=raw_stats.get("predicate_distribution", {}),
            node_type_distribution=raw_stats.get("node_type_distribution", {}),
            node_kind_distribution=raw_stats.get("node_kind_distribution", {}),
        )

        return KnowledgeGraphOverviewResponse(
            workspace_id=str(workspace_id),
            has_graph=True,
            snapshot=snap_summary,
            statistics=stats_summary,
            capabilities=GraphCapabilities(),
        )

    # -----------------------------------------------------------------------
    # Endpoint B: Node Search and Browse
    # -----------------------------------------------------------------------

    def search_nodes(
        self,
        workspace_id: uuid.UUID,
        snapshot_id: Optional[uuid.UUID],
        search: Optional[str],
        node_kind: Optional[str],
        node_type: Optional[str],
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
        session: Session,
    ) -> PaginatedGraphNodesResponse:
        """Searches and browses nodes on the authorized graph snapshot."""
        graph, snapshot = self._get_or_load_graph(workspace_id, snapshot_id, session)
        if not graph or not snapshot:
            return PaginatedGraphNodesResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0,
            )

        search_term = search.strip().lower() if search else None
        node_kind_filter = node_kind.strip().lower() if node_kind else None
        node_type_filter = node_type.strip().lower() if node_type else None

        candidates: List[GraphNodeItem] = []
        snap_id_str = str(snapshot.id)

        masteries = {}
        if session:
            try:
                from backend.app.models.bkt import LearnerConceptMastery
                m_rows = session.query(LearnerConceptMastery.concept_id, LearnerConceptMastery.posterior_mastery_probability).filter(
                    LearnerConceptMastery.workspace_id == workspace_id
                ).all()
                for c_id, prob in m_rows:
                    if prob >= 0.85:
                        status_str = "learned"
                    elif prob >= 0.50:
                        status_str = "in_progress"
                    elif prob >= 0.35:
                        status_str = "needs_revision"
                    else:
                        status_str = "not_started"
                    masteries[str(c_id)] = status_str
            except Exception:
                pass

        for n_id, attrs in graph.nodes(data=True):
            n_label = attrs.get("label", n_id)
            n_norm = attrs.get("normalized_name", "")
            n_kind = attrs.get("node_kind", "concept")
            n_type = attrs.get("node_type")
            aliases = attrs.get("aliases", [])
            desc_text = attrs.get("description", "") or ""

            # Filter kind
            if node_kind_filter and n_kind.lower() != node_kind_filter:
                continue

            # Filter type/category
            if node_type_filter and (not n_type or n_type.lower() != node_type_filter):
                continue

            # Search text matching
            if search_term:
                match = (
                    search_term in n_label.lower()
                    or search_term in n_norm.lower()
                    or any(search_term in str(a).lower() for a in aliases)
                    or (search_term in desc_text.lower())
                )
                if not match:
                    continue

            in_deg = graph.in_degree(n_id)
            out_deg = graph.out_degree(n_id)
            deg = in_deg + out_deg

            candidates.append(
                GraphNodeItem(
                    id=n_id,
                    label=n_label,
                    normalized_name=n_norm,
                    node_kind=n_kind,
                    node_type=n_type,
                    description=desc_text if desc_text else None,
                    aliases=aliases,
                    in_degree=in_deg,
                    out_degree=out_deg,
                    degree=deg,
                    connected_relationship_count=deg,
                    snapshot_id=snap_id_str,
                    learning_status=masteries.get(n_id, "not_started"),
                )
            )

        # Sorting
        reverse = sort_order.lower() == "desc"
        if sort_by == "name" or sort_by == "label":
            candidates.sort(key=lambda n: n.label.lower(), reverse=reverse)
        else:
            candidates.sort(key=lambda n: (n.degree, n.label.lower()), reverse=reverse)

        total = len(candidates)
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        offset = (page - 1) * page_size
        items = candidates[offset : offset + page_size]

        return PaginatedGraphNodesResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # -----------------------------------------------------------------------
    # Endpoint C: Node Details
    # -----------------------------------------------------------------------

    def get_node_details(
        self,
        workspace_id: uuid.UUID,
        node_id: str,
        snapshot_id: Optional[uuid.UUID],
        session: Session,
    ) -> Optional[GraphNodeDetailResponse]:
        """Retrieves complete details for a single canonical node."""
        graph, snapshot = self._get_or_load_graph(workspace_id, snapshot_id, session)
        if not graph or not snapshot or not graph.has_node(node_id):
            return None

        attrs = graph.nodes[node_id]
        in_deg = graph.in_degree(node_id)
        out_deg = graph.out_degree(node_id)
        total_deg = in_deg + out_deg

        # Query mention count and document count from PostgreSQL
        node_uuid: Optional[uuid.UUID] = None
        try:
            node_uuid = uuid.UUID(node_id)
        except (ValueError, TypeError):
            # Check if canonical node exists by name in DB
            db_node = (
                session.query(KnowledgeNode)
                .filter(
                    KnowledgeNode.workspace_id == workspace_id,
                    KnowledgeNode.normalized_name == attrs.get("normalized_name", "").lower(),
                )
                .first()
            )
            if db_node:
                node_uuid = db_node.id

        mention_count = 0
        supporting_doc_count = 0

        if node_uuid:
            mention_count = (
                session.query(func.count(KnowledgeMention.id))
                .filter(
                    KnowledgeMention.workspace_id == workspace_id,
                    KnowledgeMention.node_id == node_uuid,
                )
                .scalar()
                or 0
            )

            supporting_doc_count = (
                session.query(func.count(func.distinct(DocumentChunk.document_id)))
                .join(KnowledgeMention, KnowledgeMention.chunk_id == DocumentChunk.id)
                .filter(
                    KnowledgeMention.workspace_id == workspace_id,
                    KnowledgeMention.node_id == node_uuid,
                )
                .scalar()
                or 0
            )

        status_str = "not_started"
        if session:
            try:
                from backend.app.models.bkt import LearnerConceptMastery
                m_row = session.query(LearnerConceptMastery.posterior_mastery_probability).filter(
                    LearnerConceptMastery.workspace_id == workspace_id,
                    LearnerConceptMastery.concept_id == node_uuid,
                ).first()
                if m_row:
                    prob = m_row[0]
                    if prob >= 0.85:
                        status_str = "learned"
                    elif prob >= 0.50:
                        status_str = "in_progress"
                    elif prob >= 0.35:
                        status_str = "needs_revision"
            except Exception:
                pass

        return GraphNodeDetailResponse(
            id=node_id,
            workspace_id=str(workspace_id),
            label=attrs.get("label", node_id),
            normalized_name=attrs.get("normalized_name", ""),
            node_kind=attrs.get("node_kind", "concept"),
            node_type=attrs.get("node_type"),
            description=attrs.get("description"),
            aliases=attrs.get("aliases", []),
            ontology_version=attrs.get("ontology_version", "1.0.0"),
            in_degree=in_deg,
            out_degree=out_deg,
            degree=total_deg,
            connected_relationship_count=total_deg,
            mention_count=mention_count,
            supporting_document_count=supporting_doc_count,
            snapshot_id=str(snapshot.id),
            learning_status=status_str,
        )

    # -----------------------------------------------------------------------
    # Endpoint D: Neighborhood Subgraph
    # -----------------------------------------------------------------------

    def get_neighborhood(
        self,
        workspace_id: uuid.UUID,
        node_id: str,
        snapshot_id: Optional[uuid.UUID],
        depth: int,
        direction: str,
        relationship_types: Optional[List[str]],
        node_types: Optional[List[str]],
        max_nodes: int,
        max_edges: int,
        session: Session,
    ) -> Optional[GraphNeighborhoodResponse]:
        """Performs bounded BFS neighborhood traversal around a focal node."""
        graph, snapshot = self._get_or_load_graph(workspace_id, snapshot_id, session)
        if not graph or not snapshot or not graph.has_node(node_id):
            return None

        # Validate bounds
        bounded_depth = min(max(depth, 1), 2)
        direction_val = direction.lower() if direction in {"outgoing", "incoming", "both"} else "both"
        rel_types_set = {r.strip().lower() for r in relationship_types} if relationship_types else None
        node_types_set = {t.strip().lower() for t in node_types} if node_types else None

        visited_nodes: Set[str] = {node_id}
        current_layer: Set[str] = {node_id}
        is_truncated = False

        for d in range(bounded_depth):
            next_layer: Set[str] = set()
            for current_node in current_layer:
                neighbors: Set[str] = set()

                if direction_val in {"outgoing", "both"}:
                    for _, target, edge_data in graph.out_edges(current_node, data=True):
                        pred = str(edge_data.get("predicate", "")).lower()
                        if rel_types_set and pred not in rel_types_set:
                            continue
                        target_type = str(graph.nodes[target].get("node_type", "")).lower()
                        if node_types_set and target_type not in node_types_set:
                            continue
                        neighbors.add(target)

                if direction_val in {"incoming", "both"}:
                    for source, _, edge_data in graph.in_edges(current_node, data=True):
                        pred = str(edge_data.get("predicate", "")).lower()
                        if rel_types_set and pred not in rel_types_set:
                            continue
                        source_type = str(graph.nodes[source].get("node_type", "")).lower()
                        if node_types_set and source_type not in node_types_set:
                            continue
                        neighbors.add(source)

                for nbr in neighbors:
                    if len(visited_nodes) >= max_nodes:
                        is_truncated = True
                        break
                    if nbr not in visited_nodes:
                        visited_nodes.add(nbr)
                        next_layer.add(nbr)

                if is_truncated:
                    break
            current_layer = next_layer
            if is_truncated or not current_layer:
                break

        # Collect nodes
        subgraph_nodes: List[GraphNodeItem] = []
        for n in visited_nodes:
            attrs = graph.nodes[n]
            in_deg = graph.in_degree(n)
            out_deg = graph.out_degree(n)
            subgraph_nodes.append(
                GraphNodeItem(
                    id=n,
                    label=attrs.get("label", n),
                    normalized_name=attrs.get("normalized_name", ""),
                    node_kind=attrs.get("node_kind", "concept"),
                    node_type=attrs.get("node_type"),
                    description=attrs.get("description"),
                    aliases=attrs.get("aliases", []),
                    in_degree=in_deg,
                    out_degree=out_deg,
                    degree=in_deg + out_deg,
                    connected_relationship_count=in_deg + out_deg,
                    snapshot_id=str(snapshot.id),
                )
            )

        # Collect all parallel edges induced by the visited nodes
        subgraph_edges: List[GraphEdgeItem] = []
        for u in visited_nodes:
            for v in graph.successors(u):
                if v in visited_nodes:
                    for k, edge_data in graph.get_edge_data(u, v).items():
                        pred = str(edge_data.get("predicate", ""))
                        if rel_types_set and pred.lower() not in rel_types_set:
                            continue
                        if len(subgraph_edges) >= max_edges:
                            is_truncated = True
                            break
                        edge_id = str(edge_data.get("relationship_id") or k)
                        subgraph_edges.append(
                            GraphEdgeItem(
                                id=edge_id,
                                source=u,
                                target=v,
                                predicate=pred,
                                inverse_predicate=edge_data.get("inverse_predicate"),
                                polarity=edge_data.get("polarity", "positive"),
                                is_negated=edge_data.get("is_negated", False),
                                modality=edge_data.get("modality", "certain"),
                                qualifiers=edge_data.get("qualifiers", {}),
                                confidence=edge_data.get("confidence", 1.0),
                                validation_status=edge_data.get("validation_status", "validated"),
                                evidence_count=len(edge_data.get("evidence_ids", [])),
                                source_label=graph.nodes[u].get("label", u),
                                target_label=graph.nodes[v].get("label", v),
                            )
                        )
                if is_truncated:
                    break
            if is_truncated:
                break

        total_neighbors = graph.degree(node_id)

        return GraphNeighborhoodResponse(
            root_node_id=node_id,
            depth=bounded_depth,
            direction=direction_val,
            nodes=subgraph_nodes,
            edges=subgraph_edges,
            total_nodes=len(subgraph_nodes),
            total_edges=len(subgraph_edges),
            is_truncated=is_truncated,
            available_neighbor_count=total_neighbors,
        )

    # -----------------------------------------------------------------------
    # Endpoint E: Relationships List
    # -----------------------------------------------------------------------

    def get_relationships(
        self,
        workspace_id: uuid.UUID,
        snapshot_id: Optional[uuid.UUID],
        source_node_id: Optional[str],
        target_node_id: Optional[str],
        predicate: Optional[str],
        polarity: Optional[str],
        page: int,
        page_size: int,
        session: Session,
    ) -> PaginatedGraphRelationshipsResponse:
        """Retrieves filtered validated relationships from the graph snapshot."""
        graph, snapshot = self._get_or_load_graph(workspace_id, snapshot_id, session)
        if not graph or not snapshot:
            return PaginatedGraphRelationshipsResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0,
            )

        pred_filter = predicate.strip().lower() if predicate else None
        pol_filter = polarity.strip().lower() if polarity else None

        edges: List[GraphEdgeItem] = []
        for u, v, k, data in graph.edges(data=True, keys=True):
            if source_node_id and u != source_node_id:
                continue
            if target_node_id and v != target_node_id:
                continue
            p = str(data.get("predicate", ""))
            if pred_filter and p.lower() != pred_filter:
                continue
            pol = str(data.get("polarity", "positive"))
            if pol_filter and pol.lower() != pol_filter:
                continue

            edge_id = str(data.get("relationship_id") or k)
            edges.append(
                GraphEdgeItem(
                    id=edge_id,
                    source=u,
                    target=v,
                    predicate=p,
                    inverse_predicate=data.get("inverse_predicate"),
                    polarity=pol,
                    is_negated=data.get("is_negated", False),
                    modality=data.get("modality", "certain"),
                    qualifiers=data.get("qualifiers", {}),
                    confidence=data.get("confidence", 1.0),
                    validation_status=data.get("validation_status", "validated"),
                    evidence_count=len(data.get("evidence_ids", [])),
                    source_label=graph.nodes[u].get("label", u),
                    target_label=graph.nodes[v].get("label", v),
                )
            )

        total = len(edges)
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        offset = (page - 1) * page_size
        items = edges[offset : offset + page_size]

        return PaginatedGraphRelationshipsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # -----------------------------------------------------------------------
    # Endpoint F: Relationship Details
    # -----------------------------------------------------------------------

    def get_relationship_details(
        self,
        workspace_id: uuid.UUID,
        relationship_id: str,
        snapshot_id: Optional[uuid.UUID],
        session: Session,
    ) -> Optional[GraphRelationshipDetailResponse]:
        """Retrieves complete details for a single relationship edge."""
        graph, snapshot = self._get_or_load_graph(workspace_id, snapshot_id, session)

        # 1. Search in in-memory graph
        if graph:
            for u, v, k, data in graph.edges(data=True, keys=True):
                r_id = str(data.get("relationship_id") or k)
                if r_id == relationship_id:
                    src_attrs = graph.nodes[u]
                    tgt_attrs = graph.nodes[v]
                    return GraphRelationshipDetailResponse(
                        id=r_id,
                        workspace_id=str(workspace_id),
                        source_node_id=u,
                        source_node_label=src_attrs.get("label", u),
                        source_node_kind=src_attrs.get("node_kind", "concept"),
                        target_node_id=v,
                        target_node_label=tgt_attrs.get("label", v),
                        target_node_kind=tgt_attrs.get("node_kind", "concept"),
                        predicate=data.get("predicate", ""),
                        inverse_predicate=data.get("inverse_predicate"),
                        polarity=data.get("polarity", "positive"),
                        is_negated=data.get("is_negated", False),
                        modality=data.get("modality", "certain"),
                        qualifiers=data.get("qualifiers", {}),
                        confidence=data.get("confidence", 1.0),
                        validation_status=data.get("validation_status", "validated"),
                        ontology_version="1.0.0",
                        extraction_run_id=data.get("extraction_run_id"),
                        evidence_count=(
                            len(data.get("evidence_ids", []))
                            if len(data.get("evidence_ids", [])) > 0
                            else (
                                session.query(func.count(RelationshipEvidence.id))
                                .filter(RelationshipEvidence.relationship_id == uuid.UUID(r_id))
                                .scalar()
                                if _is_valid_uuid(r_id)
                                else 0
                            )
                        ),
                    )

        # 2. Fallback to PostgreSQL
        try:
            rel_uuid = uuid.UUID(relationship_id)
        except (ValueError, TypeError):
            return None

        db_rel = (
            session.query(KnowledgeRelationship)
            .options(
                joinedload(KnowledgeRelationship.source_node),
                joinedload(KnowledgeRelationship.target_node),
                joinedload(KnowledgeRelationship.evidence_records),
            )
            .filter(
                KnowledgeRelationship.id == rel_uuid,
                KnowledgeRelationship.workspace_id == workspace_id,
            )
            .first()
        )

        if not db_rel:
            return None

        return GraphRelationshipDetailResponse(
            id=str(db_rel.id),
            workspace_id=str(workspace_id),
            source_node_id=str(db_rel.source_node_id),
            source_node_label=db_rel.source_node.name if db_rel.source_node else str(db_rel.source_node_id),
            source_node_kind=db_rel.source_node.node_type if db_rel.source_node else "concept",
            target_node_id=str(db_rel.target_node_id),
            target_node_label=db_rel.target_node.name if db_rel.target_node else str(db_rel.target_node_id),
            target_node_kind=db_rel.target_node.node_type if db_rel.target_node else "concept",
            predicate=db_rel.relation_type,
            inverse_predicate=db_rel.inverse_relation_type,
            polarity="negative" if db_rel.is_negated else "positive",
            is_negated=db_rel.is_negated,
            modality=db_rel.modality,
            qualifiers=db_rel.qualifiers or {},
            confidence=db_rel.confidence,
            validation_status=db_rel.validation_status,
            ontology_version="1.0.0",
            extraction_run_id=str(db_rel.extraction_run_id) if db_rel.extraction_run_id else None,
            evidence_count=len(db_rel.evidence_records),
            created_at=db_rel.created_at.isoformat() if db_rel.created_at else None,
        )

    # -----------------------------------------------------------------------
    # Endpoint G: Relationship Evidence Records
    # -----------------------------------------------------------------------

    def get_relationship_evidence(
        self,
        workspace_id: uuid.UUID,
        relationship_id: str,
        page: int,
        page_size: int,
        session: Session,
    ) -> PaginatedRelationshipEvidenceResponse:
        """Retrieves verified source evidence records supporting a relationship."""
        try:
            rel_uuid = uuid.UUID(relationship_id)
        except (ValueError, TypeError):
            return PaginatedRelationshipEvidenceResponse(
                relationship_id=relationship_id,
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0,
            )

        # Query evidence joined with chunk and document, strictly filtering by workspace
        stmt = (
            select(RelationshipEvidence, DocumentChunk, Document)
            .join(DocumentChunk, RelationshipEvidence.chunk_id == DocumentChunk.id, isouter=True)
            .join(Document, DocumentChunk.document_id == Document.id, isouter=True)
            .where(
                RelationshipEvidence.relationship_id == rel_uuid,
                RelationshipEvidence.workspace_id == workspace_id,
            )
            .order_by(RelationshipEvidence.created_at)
        )

        rows = session.execute(stmt).all()

        items: List[RelationshipEvidenceItem] = []
        for ev, chunk, doc in rows:
            is_available = True
            doc_title = "Source Document"
            doc_type = "application/pdf"

            if doc:
                raw_title = getattr(doc, "original_filename", None) or getattr(doc, "title", "Source Document")
                doc_type = getattr(doc, "media_type", None) or getattr(doc, "file_type", "application/pdf")
                status_val = getattr(doc, "processing_status", None) or getattr(doc, "status", "ready")
                is_del = getattr(doc, "is_deleted", False)
                if is_del or status_val not in {"ready", "completed"}:
                    is_available = False
                    doc_title = f"{raw_title} (Archived/Unavailable)"
                else:
                    doc_title = raw_title
            elif chunk:
                is_available = False

            items.append(
                RelationshipEvidenceItem(
                    id=str(ev.id),
                    relationship_id=str(ev.relationship_id),
                    chunk_id=str(ev.chunk_id) if ev.chunk_id else None,
                    document_id=str(chunk.document_id) if chunk else None,
                    document_title=doc_title,
                    source_type=doc_type,
                    evidence_text=ev.evidence_text,
                    start_offset=ev.start_offset,
                    end_offset=ev.end_offset,
                    confidence=ev.confidence,
                    page_start=chunk.page_start if chunk else None,
                    page_end=chunk.page_end if chunk else None,
                    slide_number=chunk.slide_number if chunk else None,
                    section_title=chunk.section_title if chunk else None,
                    validation_status="validated",
                    is_source_available=is_available,
                )
            )

        total = len(items)
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        offset = (page - 1) * page_size
        paginated_items = items[offset : offset + page_size]

        return PaginatedRelationshipEvidenceResponse(
            relationship_id=relationship_id,
            items=paginated_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # -----------------------------------------------------------------------
    # Endpoint H: Node Mentions Evidence
    # -----------------------------------------------------------------------

    def get_node_evidence(
        self,
        workspace_id: uuid.UUID,
        node_id: str,
        page: int,
        page_size: int,
        session: Session,
    ) -> PaginatedNodeMentionsResponse:
        """Retrieves surface text mentions supporting a concept or entity."""
        node_uuid: Optional[uuid.UUID] = None
        try:
            node_uuid = uuid.UUID(node_id)
        except (ValueError, TypeError):
            # Check by normalized name
            db_node = (
                session.query(KnowledgeNode)
                .filter(
                    KnowledgeNode.workspace_id == workspace_id,
                    KnowledgeNode.name.ilike(node_id),
                )
                .first()
            )
            if db_node:
                node_uuid = db_node.id

        if not node_uuid:
            return PaginatedNodeMentionsResponse(
                node_id=node_id,
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0,
            )

        stmt = (
            select(KnowledgeMention, DocumentChunk, Document)
            .join(DocumentChunk, KnowledgeMention.chunk_id == DocumentChunk.id, isouter=True)
            .join(Document, DocumentChunk.document_id == Document.id, isouter=True)
            .where(
                KnowledgeMention.node_id == node_uuid,
                KnowledgeMention.workspace_id == workspace_id,
            )
            .order_by(KnowledgeMention.created_at)
        )

        rows = session.execute(stmt).all()

        items: List[NodeMentionItem] = []
        for mention, chunk, doc in rows:
            is_available = True
            doc_title = "Source Document"
            doc_type = "application/pdf"
            excerpt = mention.surface_form

            if chunk and chunk.content:
                # Extract surrounding excerpt (up to 120 chars around mention)
                start = max(0, mention.start_offset - 40)
                end = min(len(chunk.content), mention.end_offset + 40)
                prefix = "..." if start > 0 else ""
                suffix = "..." if end < len(chunk.content) else ""
                excerpt = f"{prefix}{chunk.content[start:end]}{suffix}"

            if doc:
                raw_title = getattr(doc, "original_filename", None) or getattr(doc, "title", "Source Document")
                doc_type = getattr(doc, "media_type", None) or getattr(doc, "file_type", "application/pdf")
                status_val = getattr(doc, "processing_status", None) or getattr(doc, "status", "ready")
                is_del = getattr(doc, "is_deleted", False)
                if is_del or status_val not in {"ready", "completed"}:
                    is_available = False
                    doc_title = f"{raw_title} (Archived/Unavailable)"
                else:
                    doc_title = raw_title

            items.append(
                NodeMentionItem(
                    id=str(mention.id),
                    node_id=str(mention.node_id),
                    surface_form=mention.surface_form,
                    chunk_id=str(mention.chunk_id) if mention.chunk_id else None,
                    document_id=str(chunk.document_id) if chunk else None,
                    document_title=doc_title,
                    source_type=doc_type,
                    excerpt=excerpt,
                    start_offset=mention.start_offset,
                    end_offset=mention.end_offset,
                    confidence=mention.confidence,
                    extraction_method=mention.extraction_method,
                    page_start=chunk.page_start if chunk else None,
                    page_end=chunk.page_end if chunk else None,
                    slide_number=chunk.slide_number if chunk else None,
                    section_title=chunk.section_title if chunk else None,
                    is_source_available=is_available,
                )
            )

        total = len(items)
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        offset = (page - 1) * page_size
        paginated_items = items[offset : offset + page_size]

        return PaginatedNodeMentionsResponse(
            node_id=node_id,
            items=paginated_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # -----------------------------------------------------------------------
    # Endpoint I: Path Exploration
    # -----------------------------------------------------------------------

    def find_paths(
        self,
        workspace_id: uuid.UUID,
        source_node_id: str,
        target_node_id: str,
        snapshot_id: Optional[uuid.UUID],
        max_hops: int,
        max_paths: int,
        allowed_predicates: Optional[List[str]],
        session: Session,
    ) -> GraphPathsResponse:
        """Discovers source-backed connection paths between two canonical nodes."""
        graph, snapshot = self._get_or_load_graph(workspace_id, snapshot_id, session)
        if not graph or not snapshot:
            return GraphPathsResponse(
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                max_hops=max_hops,
                path_count=0,
                paths=[],
                no_path_found=True,
            )

        if not graph.has_node(source_node_id) or not graph.has_node(target_node_id):
            return GraphPathsResponse(
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                max_hops=max_hops,
                path_count=0,
                paths=[],
                no_path_found=True,
            )

        bounded_hops = min(max(max_hops, 1), 5)
        bounded_limit = min(max(max_paths, 1), 10)
        pred_filter = {p.strip().lower() for p in allowed_predicates} if allowed_predicates else None

        # Build filtered view of MultiDiGraph for path search
        filtered_graph = graph
        if pred_filter:
            filtered_graph = nx.MultiDiGraph()
            for n, d in graph.nodes(data=True):
                filtered_graph.add_node(n, **d)
            for u, v, k, d in graph.edges(data=True, keys=True):
                if str(d.get("predicate", "")).lower() in pred_filter:
                    filtered_graph.add_edge(u, v, key=k, **d)

        # Find simple paths using NetworkX
        paths_found: List[GraphPathItem] = []
        try:
            raw_paths = nx.all_simple_edge_paths(
                filtered_graph,
                source=source_node_id,
                target=target_node_id,
                cutoff=bounded_hops,
            )
            for idx, edge_seq in enumerate(raw_paths):
                if idx >= bounded_limit:
                    break

                path_nodes: List[GraphNodeItem] = []
                path_edges: List[GraphEdgeItem] = []
                path_steps: List[GraphPathStep] = []

                node_ids_in_path = [edge_seq[0][0]] + [e[1] for e in edge_seq]

                for n in node_ids_in_path:
                    attrs = graph.nodes[n]
                    path_nodes.append(
                        GraphNodeItem(
                            id=n,
                            label=attrs.get("label", n),
                            normalized_name=attrs.get("normalized_name", ""),
                            node_kind=attrs.get("node_kind", "concept"),
                            node_type=attrs.get("node_type"),
                            description=attrs.get("description"),
                            aliases=attrs.get("aliases", []),
                            in_degree=graph.in_degree(n),
                            out_degree=graph.out_degree(n),
                            degree=graph.degree(n),
                            connected_relationship_count=graph.degree(n),
                            snapshot_id=str(snapshot.id),
                        )
                    )

                for step_idx, (u, v, k) in enumerate(edge_seq):
                    edge_data = graph.get_edge_data(u, v, k) or {}
                    edge_item = GraphEdgeItem(
                        id=str(edge_data.get("relationship_id") or k),
                        source=u,
                        target=v,
                        predicate=str(edge_data.get("predicate", "")),
                        inverse_predicate=edge_data.get("inverse_predicate"),
                        polarity=edge_data.get("polarity", "positive"),
                        is_negated=edge_data.get("is_negated", False),
                        modality=edge_data.get("modality", "certain"),
                        qualifiers=edge_data.get("qualifiers", {}),
                        confidence=edge_data.get("confidence", 1.0),
                        validation_status=edge_data.get("validation_status", "validated"),
                        evidence_count=len(edge_data.get("evidence_ids", [])),
                        source_label=graph.nodes[u].get("label", u),
                        target_label=graph.nodes[v].get("label", v),
                    )
                    path_edges.append(edge_item)
                    path_steps.append(
                        GraphPathStep(
                            source_node=path_nodes[step_idx],
                            edge=edge_item,
                            target_node=path_nodes[step_idx + 1],
                        )
                    )

                paths_found.append(
                    GraphPathItem(
                        path_index=idx + 1,
                        hop_count=len(edge_seq),
                        nodes=path_nodes,
                        edges=path_edges,
                        steps=path_steps,
                    )
                )

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        return GraphPathsResponse(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            max_hops=bounded_hops,
            path_count=len(paths_found),
            paths=paths_found,
            no_path_found=(len(paths_found) == 0),
        )

    # -----------------------------------------------------------------------
    # Endpoint J: Snapshot History
    # -----------------------------------------------------------------------

    def list_snapshots(
        self,
        workspace_id: uuid.UUID,
        page: int,
        page_size: int,
        session: Session,
    ) -> PaginatedGraphSnapshotsResponse:
        """Returns paginated snapshot history for a workspace."""
        repo = KnowledgeGraphSnapshotRepository(session)
        total = (
            session.query(func.count(KnowledgeGraphSnapshot.id))
            .filter(KnowledgeGraphSnapshot.workspace_id == workspace_id)
            .scalar()
            or 0
        )

        offset = (page - 1) * page_size
        snapshots = repo.list_snapshots(workspace_id=workspace_id, limit=page_size, offset=offset)

        items = [
            GraphSnapshotSummaryItem(
                id=str(s.id),
                status=s.status,
                is_active=s.is_active,
                created_at=s.created_at.isoformat() if s.created_at else "",
                completed_at=s.completed_at.isoformat() if s.completed_at else None,
                node_count=s.node_count,
                edge_count=s.edge_count,
                concept_count=s.concept_count,
                entity_count=s.entity_count,
                component_count=s.component_count,
                isolated_node_count=s.isolated_node_count,
                extraction_run_id=str(s.extraction_run_id) if s.extraction_run_id else None,
                ontology_version=s.ontology_version,
            )
            for s in snapshots
        ]

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedGraphSnapshotsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
