"""Authenticated FastAPI Endpoints for Knowledge Graph (Phase 7 C7.7).

Provides workspace-scoped access to graph overview, node search, neighborhood traversal,
relationships, source evidence records, and path exploration.
"""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_user_workspace
from backend.app.db.session import get_db
from backend.app.ml.knowledge_graph.orchestrator import KnowledgeExtractionOrchestrator
from backend.app.models.bkt import LearnerConceptMastery
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.knowledge_graph import (
    GraphNeighborhoodResponse,
    GraphNodeDetailResponse,
    GraphPathsResponse,
    GraphRelationshipDetailResponse,
    KnowledgeGraphOverviewResponse,
    MindMapNodeItem,
    MindMapStatusUpdateRequest,
    MindMapTreeResponse,
    NodeStatusUpdateRequest,
    PaginatedGraphNodesResponse,
    PaginatedGraphRelationshipsResponse,
    PaginatedGraphSnapshotsResponse,
    PaginatedNodeMentionsResponse,
    PaginatedRelationshipEvidenceResponse,
)
from backend.app.services.knowledge_graph_service import KnowledgeGraphService
from backend.app.services.mind_map_service import MindMapService

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoint A: Graph Overview
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/knowledge-graph",
    response_model=KnowledgeGraphOverviewResponse,
    summary="Get knowledge graph overview",
)
def get_graph_overview(
    workspace_id: uuid.UUID,
    snapshot_id: Optional[uuid.UUID] = Query(
        default=None,
        description="Optional historical snapshot ID; defaults to active snapshot",
    ),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> KnowledgeGraphOverviewResponse:
    """Returns metadata, summary statistics, and capabilities for workspace knowledge graph."""
    service = KnowledgeGraphService()
    # If snapshot_id is explicitly requested, verify it exists in workspace
    if snapshot_id:
        graph, snap = service._get_or_load_graph(workspace_id, snapshot_id, db)
        if not snap or snap.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Graph snapshot not found in workspace",
            )

    return service.get_graph_overview(workspace_id=workspace_id, snapshot_id=snapshot_id, session=db)


# ---------------------------------------------------------------------------
# Endpoint B: Graph Nodes Search and Browse
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/knowledge-graph/nodes",
    response_model=PaginatedGraphNodesResponse,
    summary="Search and browse graph nodes",
)
def search_graph_nodes(
    workspace_id: uuid.UUID,
    snapshot_id: Optional[uuid.UUID] = Query(default=None),
    search: Optional[str] = Query(default=None, description="Search term for label, alias, or description"),
    node_kind: Optional[str] = Query(default=None, description="Filter by 'concept' or 'entity'"),
    node_type: Optional[str] = Query(default=None, description="Filter by ontology category"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="degree", description="Field to sort by: 'degree' or 'name'"),
    sort_order: str = Query(default="desc", description="Sort order: 'asc' or 'desc'"),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> PaginatedGraphNodesResponse:
    """Searches and browses canonical concepts and entities."""
    service = KnowledgeGraphService()
    return service.search_nodes(
        workspace_id=workspace_id,
        snapshot_id=snapshot_id,
        search=search,
        node_kind=node_kind,
        node_type=node_type,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        session=db,
    )


# ---------------------------------------------------------------------------
# Endpoint C: Node Details
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/knowledge-graph/nodes/{node_id}",
    response_model=GraphNodeDetailResponse,
    summary="Get single node details",
)
def get_node_details(
    workspace_id: uuid.UUID,
    node_id: str,
    snapshot_id: Optional[uuid.UUID] = Query(default=None),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> GraphNodeDetailResponse:
    """Retrieves full details and provenance for a single knowledge node."""
    service = KnowledgeGraphService()
    node = service.get_node_details(
        workspace_id=workspace_id,
        node_id=node_id,
        snapshot_id=snapshot_id,
        session=db,
    )
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found in graph snapshot",
        )
    return node


# ---------------------------------------------------------------------------
# Endpoint D: Neighborhood Subgraph
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/knowledge-graph/neighborhood",
    response_model=GraphNeighborhoodResponse,
    summary="Get bounded neighborhood subgraph",
)
def get_graph_neighborhood(
    workspace_id: uuid.UUID,
    node_id: str = Query(..., description="Root/focal node ID"),
    snapshot_id: Optional[uuid.UUID] = Query(default=None),
    depth: int = Query(default=1, ge=1, le=2, description="Traversal depth (1 or 2)"),
    direction: str = Query(default="both", description="'outgoing', 'incoming', or 'both'"),
    relationship_types: Optional[List[str]] = Query(default=None, description="Allowed predicates"),
    node_types: Optional[List[str]] = Query(default=None, description="Allowed node categories"),
    max_nodes: int = Query(default=100, ge=1, le=250),
    max_edges: int = Query(default=200, ge=1, le=500),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> GraphNeighborhoodResponse:
    """Retrieves a bounded subgraph around a focal node."""
    service = KnowledgeGraphService()
    result = service.get_neighborhood(
        workspace_id=workspace_id,
        node_id=node_id,
        snapshot_id=snapshot_id,
        depth=depth,
        direction=direction,
        relationship_types=relationship_types,
        node_types=node_types,
        max_nodes=max_nodes,
        max_edges=max_edges,
        session=db,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found in graph snapshot",
        )
    return result


# ---------------------------------------------------------------------------
# Endpoint E: Relationships List
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/knowledge-graph/relationships",
    response_model=PaginatedGraphRelationshipsResponse,
    summary="List filtered graph relationships",
)
def list_graph_relationships(
    workspace_id: uuid.UUID,
    snapshot_id: Optional[uuid.UUID] = Query(default=None),
    source_node_id: Optional[str] = Query(default=None),
    target_node_id: Optional[str] = Query(default=None),
    predicate: Optional[str] = Query(default=None),
    polarity: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> PaginatedGraphRelationshipsResponse:
    """Retrieves relationships connecting nodes in the snapshot."""
    service = KnowledgeGraphService()
    return service.get_relationships(
        workspace_id=workspace_id,
        snapshot_id=snapshot_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        predicate=predicate,
        polarity=polarity,
        page=page,
        page_size=page_size,
        session=db,
    )


# ---------------------------------------------------------------------------
# Endpoint F: Relationship Details
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/knowledge-graph/relationships/{relationship_id}",
    response_model=GraphRelationshipDetailResponse,
    summary="Get single relationship details",
)
def get_relationship_details(
    workspace_id: uuid.UUID,
    relationship_id: str,
    snapshot_id: Optional[uuid.UUID] = Query(default=None),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> GraphRelationshipDetailResponse:
    """Retrieves full details and provenance for a single relationship."""
    service = KnowledgeGraphService()
    rel = service.get_relationship_details(
        workspace_id=workspace_id,
        relationship_id=relationship_id,
        snapshot_id=snapshot_id,
        session=db,
    )
    if not rel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found in graph snapshot",
        )
    return rel


# ---------------------------------------------------------------------------
# Endpoint G: Relationship Supporting Evidence
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/knowledge-graph/relationships/{relationship_id}/evidence",
    response_model=PaginatedRelationshipEvidenceResponse,
    summary="Get relationship supporting evidence records",
)
def get_relationship_evidence(
    workspace_id: uuid.UUID,
    relationship_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> PaginatedRelationshipEvidenceResponse:
    """Retrieves verified source document passages supporting a relationship."""
    service = KnowledgeGraphService()
    return service.get_relationship_evidence(
        workspace_id=workspace_id,
        relationship_id=relationship_id,
        page=page,
        page_size=page_size,
        session=db,
    )


# ---------------------------------------------------------------------------
# Endpoint H: Node Mentions Evidence
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/knowledge-graph/nodes/{node_id}/evidence",
    response_model=PaginatedNodeMentionsResponse,
    summary="Get node mentions and source excerpts",
)
def get_node_evidence(
    workspace_id: uuid.UUID,
    node_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> PaginatedNodeMentionsResponse:
    """Retrieves verified surface mentions in source documents for a concept or entity."""
    service = KnowledgeGraphService()
    return service.get_node_evidence(
        workspace_id=workspace_id,
        node_id=node_id,
        page=page,
        page_size=page_size,
        session=db,
    )


# ---------------------------------------------------------------------------
# Endpoint I: Path Exploration
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/knowledge-graph/paths",
    response_model=GraphPathsResponse,
    summary="Explore connection paths between two nodes",
)
def explore_graph_paths(
    workspace_id: uuid.UUID,
    source_node_id: str = Query(..., description="Starting node ID"),
    target_node_id: str = Query(..., description="Destination node ID"),
    snapshot_id: Optional[uuid.UUID] = Query(default=None),
    max_hops: int = Query(default=4, ge=1, le=5, description="Maximum path depth/hops"),
    max_paths: int = Query(default=5, ge=1, le=10, description="Maximum paths to return"),
    allowed_predicates: Optional[List[str]] = Query(default=None, description="Optional allowed predicates"),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> GraphPathsResponse:
    """Finds source-backed relationship paths between two canonical nodes."""
    service = KnowledgeGraphService()
    return service.find_paths(
        workspace_id=workspace_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        snapshot_id=snapshot_id,
        max_hops=max_hops,
        max_paths=max_paths,
        allowed_predicates=allowed_predicates,
        session=db,
    )


# ---------------------------------------------------------------------------
# Endpoint J: Snapshot History
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/knowledge-graph/snapshots",
    response_model=PaginatedGraphSnapshotsResponse,
    summary="List historical graph snapshots",
)
def list_graph_snapshots(
    workspace_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> PaginatedGraphSnapshotsResponse:
    """Retrieves paginated history of completed graph snapshots for the workspace."""
    service = KnowledgeGraphService()
    return service.list_snapshots(
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        session=db,
    )


# ---------------------------------------------------------------------------
# Endpoint K: Build / Regenerate Knowledge Graph Roadmap
# ---------------------------------------------------------------------------

@router.post(
    "/workspaces/{workspace_id}/knowledge-graph/build",
    response_model=KnowledgeGraphOverviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Build or regenerate knowledge graph roadmap for workspace",
)
def build_knowledge_graph(
    workspace_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeGraphOverviewResponse:
    """Extracts concepts, identifies relationships, and persists active roadmap graph."""
    chunks = (
        db.query(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .filter(
            Document.workspace_id == workspace_id,
            Document.deleted_at.is_(None),
        )
        .all()
    )
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No document chunks found in this workspace. Upload and index documents first.",
        )

    chunk_payloads = [
        {
            "id": str(c.id),
            "content": c.content,
            "content_hash": getattr(c, "content_hash", ""),
            "workspace_id": str(workspace_id),
        }
        for c in chunks
    ]

    orchestrator = KnowledgeExtractionOrchestrator()
    orchestrator.run_pipeline(
        workspace_id=str(workspace_id),
        chunks=chunk_payloads,
        session=db,
        created_by_user_id=str(current_user.id),
        persist_graph_snapshot=True,
    )

    service = KnowledgeGraphService()
    return service.get_graph_overview(workspace_id=workspace_id, snapshot_id=None, session=db)


# ---------------------------------------------------------------------------
# Endpoint L: Update Node Learning Status
# ---------------------------------------------------------------------------

@router.patch(
    "/workspaces/{workspace_id}/knowledge-graph/nodes/{node_id}/status",
    response_model=GraphNodeDetailResponse,
    summary="Update persistent learning status for a concept node",
)
def update_node_learning_status(
    workspace_id: uuid.UUID,
    node_id: uuid.UUID,
    payload: NodeStatusUpdateRequest,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GraphNodeDetailResponse:
    """Updates persistent learning status ('not_started', 'in_progress', 'learned', 'needs_revision')."""
    valid_statuses = {"not_started", "in_progress", "learned", "needs_revision"}
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status '{payload.status}'. Must be one of: {valid_statuses}",
        )

    node = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.id == node_id, KnowledgeNode.workspace_id == workspace_id)
        .first()
    )
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concept node not found in this workspace",
        )

    mastery_prob_map = {
        "not_started": 0.20,
        "in_progress": 0.55,
        "needs_revision": 0.40,
        "learned": 0.95,
    }

    mastery = (
        db.query(LearnerConceptMastery)
        .filter(
            LearnerConceptMastery.workspace_id == workspace_id,
            LearnerConceptMastery.concept_id == node_id,
            LearnerConceptMastery.user_id == current_user.id,
        )
        .first()
    )
    prob = mastery_prob_map.get(payload.status, 0.20)
    if not mastery:
        mastery = LearnerConceptMastery(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=current_user.id,
            concept_id=node_id,
            posterior_mastery_probability=prob,
            predicted_next_mastery_probability=prob,
            observation_count=1,
        )
        db.add(mastery)
    else:
        mastery.posterior_mastery_probability = prob
        mastery.predicted_next_mastery_probability = prob
        mastery.observation_count += 1
    db.commit()

    service = KnowledgeGraphService()
    detail = service.get_node_details(workspace_id=workspace_id, node_id=str(node_id), snapshot_id=None, session=db)
    if detail:
        detail.learning_status = payload.status
        return detail

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node details not found")


# ---------------------------------------------------------------------------
# Endpoint M: Knovera Interactive Mind Map
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/knowledge-graph/mind-map",
    response_model=MindMapTreeResponse,
    summary="Get Knovera hierarchical mind map for workspace",
)
def get_mind_map(
    workspace_id: uuid.UUID,
    force_rebuild: bool = Query(default=False, description="Whether to force regenerate the tree"),
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MindMapTreeResponse:
    """Returns the 4-tier hierarchical mind map (Root -> Primary -> Secondary -> Leaf)."""
    service = MindMapService()
    try:
        return service.get_mind_map(
            workspace_id=workspace_id,
            session=db,
            user_id=current_user.id,
            force_rebuild=force_rebuild,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate mind map: {str(e)}",
        )


@router.post(
    "/workspaces/{workspace_id}/knowledge-graph/mind-map/build",
    response_model=MindMapTreeResponse,
    summary="Rebuild Knovera hierarchical mind map from documents",
)
def build_mind_map(
    workspace_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MindMapTreeResponse:
    """Forces end-to-end extraction and assembly of the 4-tier mind map tree."""
    service = MindMapService()
    try:
        return service.build_mind_map(
            workspace_id=workspace_id,
            session=db,
            user_id=current_user.id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rebuild mind map: {str(e)}",
        )


@router.patch(
    "/workspaces/{workspace_id}/knowledge-graph/mind-map/nodes/{node_id}/status",
    response_model=MindMapNodeItem,
    summary="Update learning status for a mind map node",
)
def update_mind_map_node_status(
    workspace_id: uuid.UUID,
    node_id: str,
    payload: MindMapStatusUpdateRequest,
    workspace: Workspace = Depends(get_user_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MindMapNodeItem:
    """Updates learning status of a mind map node with BKT persistence."""
    service = MindMapService()
    try:
        return service.update_node_status(
            workspace_id=workspace_id,
            node_id=node_id,
            status=payload.status,
            session=db,
            user_id=current_user.id,
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update node status: {str(e)}",
        )


