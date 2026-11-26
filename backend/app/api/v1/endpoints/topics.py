"""Authenticated REST API Endpoints for Topic Discovery & Explorer (Phase 6 C6.7)."""

import math
from typing import Any, Dict, List, Optional, Union
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_user_workspace
from backend.app.db.session import get_db
from backend.app.models.topic import Topic
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.topic import (
    PaginatedTopicChunksResponse,
    PaginatedTopicRunsResponse,
    PaginatedTopicsResponse,
    TopicChunkItem,
    TopicDetailResponse,
    TopicKeyword,
    TopicRunDetailResponse,
    TopicRunSummary,
    TopicSummaryItem,
)
from backend.app.repositories.topic_clustering_repository import TopicClusteringRepository

router = APIRouter()


@router.get(
    "/workspaces/{workspace_id}/topics",
    response_model=Union[PaginatedTopicsResponse, List[TopicSummaryItem]],
    summary="Get topics for workspace",
)
def get_workspace_topics(
    workspace_id: uuid.UUID,
    run_id: Optional[uuid.UUID] = Query(
        default=None,
        description="Optional specific clustering run ID; defaults to active run",
    ),
    search: Optional[str] = Query(
        default=None,
        description="Search term matching label, description, or keywords",
    ),
    sort_by: str = Query(
        default="chunk_count",
        description="Field to sort by: chunk_count, document_count, label, cluster_key",
    ),
    sort_order: str = Query(
        default="desc",
        description="Sort order: asc, desc",
    ),
    page: Optional[int] = Query(
        default=None,
        ge=1,
        description="Page number (1-based)",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Items per page",
    ),
    paginate: Optional[bool] = Query(
        default=None,
        description="Force paginated envelope response",
    ),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> Union[PaginatedTopicsResponse, List[TopicSummaryItem]]:
    """Retrieves discovered topics for a workspace with search, filtering, and sorting."""
    repo = TopicClusteringRepository(db)

    # Resolve target clustering run
    target_run = None
    if run_id is not None:
        target_run = repo.get_clustering_run(run_id=run_id, workspace_id=workspace.id)
        if not target_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clustering run not found in workspace",
            )
    else:
        target_run = repo.get_active_run(workspace.id)

    # If no run exists for workspace
    if not target_run:
        if page is not None or paginate is True:
            return PaginatedTopicsResponse(
                workspace_id=str(workspace.id),
                run=None,
                items=[],
                total=0,
                page=page or 1,
                page_size=page_size,
                total_pages=0,
            )
        return []

    # Fetch topics for the run
    current_page = page or 1
    fetch_size = page_size if (page is not None or paginate is True) else 1000

    raw_items, total = repo.get_topics_for_run(
        workspace_id=workspace.id,
        run_id=target_run.id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=current_page,
        page_size=fetch_size,
    )

    items = [
        TopicSummaryItem(
            id=item["id"],
            workspace_id=item["workspace_id"],
            clustering_run_id=item["clustering_run_id"],
            cluster_key=item["cluster_key"],
            label=item["label"],
            description=item["description"],
            label_source=item["label_source"],
            label_status=item["label_status"],
            keywords=[TopicKeyword(**kw) for kw in item["keywords"]],
            chunk_count=item["chunk_count"],
            document_count=item["document_count"],
            representative_chunk_ids=item["representative_chunk_ids"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )
        for item in raw_items
    ]

    if page is not None or paginate is True:
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        run_summary = TopicRunSummary(
            id=str(target_run.id),
            workspace_id=str(target_run.workspace_id),
            snapshot_id=target_run.snapshot_id,
            status=target_run.status,
            k=target_run.k,
            model_version=target_run.model_version,
            is_active=target_run.is_active,
            created_at=target_run.created_at.isoformat(),
            completed_at=target_run.completed_at.isoformat() if target_run.completed_at else None,
        )
        return PaginatedTopicsResponse(
            workspace_id=str(workspace.id),
            run=run_summary,
            items=items,
            total=total,
            page=current_page,
            page_size=page_size,
            total_pages=total_pages,
        )

    return items


@router.get(
    "/workspaces/{workspace_id}/topic-runs",
    response_model=Union[PaginatedTopicRunsResponse, List[TopicRunSummary]],
    summary="List clustering run history",
)
def list_workspace_topic_runs(
    workspace_id: uuid.UUID,
    page: Optional[int] = Query(default=None, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    limit: Optional[int] = Query(default=None, ge=1, le=100, description="Limit for unpaginated list"),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> Union[PaginatedTopicRunsResponse, List[TopicRunSummary]]:
    """Lists historical topic clustering runs for the authorized workspace."""
    repo = TopicClusteringRepository(db)

    if page is not None:
        items, total = repo.list_runs_paginated(
            workspace_id=workspace.id,
            page=page,
            page_size=page_size,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return PaginatedTopicRunsResponse(
            items=[TopicRunSummary(**item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # Unpaginated backward-compatible list
    runs = repo.list_runs(workspace.id, limit=limit or page_size)
    return [
        TopicRunSummary(
            id=str(r.id),
            workspace_id=str(r.workspace_id),
            snapshot_id=r.snapshot_id,
            status=r.status,
            k=r.k,
            model_version=r.model_version,
            is_active=r.is_active,
            created_at=r.created_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in runs
    ]


@router.get(
    "/workspaces/{workspace_id}/topic-runs/{run_id}",
    response_model=TopicRunDetailResponse,
    summary="Get clustering run detail",
)
def get_workspace_topic_run(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> TopicRunDetailResponse:
    """Retrieves full details and metrics of an individual clustering run."""
    repo = TopicClusteringRepository(db)
    detail = repo.get_run_detail(workspace_id=workspace.id, run_id=run_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clustering run not found in workspace",
        )
    return TopicRunDetailResponse(**detail)


@router.get(
    "/workspaces/{workspace_id}/topics/{topic_id}",
    response_model=TopicDetailResponse,
    summary="Get topic detail",
)
def get_topic_detail(
    workspace_id: uuid.UUID,
    topic_id: uuid.UUID,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> TopicDetailResponse:
    """Retrieves comprehensive details of a specific topic."""
    repo = TopicClusteringRepository(db)
    detail = repo.get_topic_detail(workspace_id=workspace.id, topic_id=topic_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found in workspace",
        )
    kw_items = [TopicKeyword(**kw) for kw in detail["keywords"]]
    detail["keywords"] = kw_items
    if detail["run_summary"]:
        detail["run_summary"] = TopicRunSummary(**detail["run_summary"])
    return TopicDetailResponse(**detail)


@router.get(
    "/workspaces/{workspace_id}/topics/{topic_id}/chunks",
    response_model=PaginatedTopicChunksResponse,
    summary="Get paginated chunks for a topic",
)
def get_topic_chunks(
    workspace_id: uuid.UUID,
    topic_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    representative_only: bool = Query(
        default=False,
        description="Filter for centroid representative chunks only",
    ),
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
) -> PaginatedTopicChunksResponse:
    """Retrieves paginated document chunks assigned to a specific topic with document title and provenance."""
    repo = TopicClusteringRepository(db)
    topic = (
        db.query(Topic)
        .filter(
            Topic.id == topic_id,
            Topic.workspace_id == workspace.id,
        )
        .first()
    )

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found in workspace",
        )

    raw_items, total = repo.get_topic_chunks_detail(
        workspace_id=workspace.id,
        topic_id=topic.id,
        page=page,
        page_size=page_size,
        representative_only=representative_only,
    )

    items = [TopicChunkItem(**item) for item in raw_items]
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedTopicChunksResponse(
        topic_id=str(topic.id),
        topic_label=topic.label,
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
