"""Workspace management API endpoints for Knovera."""

from datetime import datetime, timezone
from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.models.document import Document
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from backend.app.storage import StorageService, get_storage_service

logger = get_logger("knovera.api.workspaces")
router = APIRouter()


@router.get(
    "",
    response_model=List[WorkspaceResponse],
    summary="List all workspaces",
)
def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[WorkspaceResponse]:
    """Lists all workspaces in the local platform."""
    workspaces = (
        db.query(Workspace)
        .order_by(Workspace.updated_at.desc())
        .all()
    )
    result = []
    for ws in workspaces:
        doc_count = (
            db.query(Document)
            .filter(Document.workspace_id == ws.id, Document.deleted_at.is_(None))
            .count()
        )
        resp = WorkspaceResponse.model_validate(ws)
        resp.document_count = doc_count
        result.append(resp)
    return result


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    """Creates a new workspace belonging to the resolved local owner."""
    now_utc = datetime.now(timezone.utc)
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    resp = WorkspaceResponse.model_validate(ws)
    resp.document_count = 0
    return resp


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get workspace details by ID",
)
def get_workspace(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    """Retrieves workspace details by ID."""
    ws = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id)
        .first()
    )
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    doc_count = (
        db.query(Document)
        .filter(Document.workspace_id == ws.id, Document.deleted_at.is_(None))
        .count()
    )
    resp = WorkspaceResponse.model_validate(ws)
    resp.document_count = doc_count
    return resp


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update workspace name or description",
)
def update_workspace(
    workspace_id: uuid.UUID,
    payload: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    """Updates workspace metadata."""
    ws = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id)
        .first()
    )
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    if payload.name is not None:
        ws.name = payload.name
    if payload.description is not None:
        ws.description = payload.description
    ws.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ws)
    resp = WorkspaceResponse.model_validate(ws)
    return resp


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace",
)
def delete_workspace(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> None:
    """Deletes workspace, physical documents, cache, and vector embeddings."""
    ws = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id)
        .first()
    )
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # 1. Purge physical files for all documents in this workspace
    try:
        docs = db.query(Document).filter(Document.workspace_id == workspace_id).all()
        for doc in docs:
            if doc.storage_key:
                try:
                    storage.delete_file(doc.storage_key)
                except Exception as file_err:
                    logger.warning("Failed to delete storage file %s for doc %s: %s", doc.storage_key, doc.id, file_err)
    except Exception as exc:
        logger.warning("Failed querying documents for storage cleanup in workspace %s: %s", workspace_id, exc)

    # 2. Invalidate BM25 cache
    try:
        from backend.app.rag.retrieval.bm25.cache import BM25IndexCache
        BM25IndexCache.get_instance().invalidate(workspace_id)
    except Exception as exc:
        logger.warning("Failed to invalidate BM25 cache for workspace %s: %s", workspace_id, exc)

    # 3. Purge vectors belonging to this workspace from ChromaDB
    try:
        from backend.app.rag.vector_store.chroma_repository import ChromaVectorRepository
        repo = ChromaVectorRepository()
        repo.delete_by_workspace(workspace_id=workspace_id)
    except Exception as exc:
        logger.warning("Failed to purge vectors for workspace %s from Chroma: %s", workspace_id, exc)

    # 4. Atomically delete workspace and cascade across all tables
    try:
        from sqlalchemy import text
        db.execute(text("DELETE FROM workspaces WHERE id = :id"), {"id": workspace_id})
        db.commit()
        logger.info("Successfully deleted workspace %s", workspace_id)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to delete workspace %s: %s", workspace_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete workspace: {str(exc)}",
        )
