"""API endpoints for Knovera citation detail inspection (Phase 3 C3.8)."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.citations.exceptions import (
    CitationAccessDeniedError,
    CitationNotFoundError,
)
from backend.app.citations.repository import CitationRepository
from backend.app.citations.schemas import CitationDetail
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.models.user import User

logger = get_logger("knovera.api.citations")
router = APIRouter()


@router.get(
    "/{citation_id}",
    response_model=CitationDetail,
    summary="Get verified citation details and source provenance",
)
def get_citation_detail(
    citation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CitationDetail:
    """Retrieves authoritative citation metadata, location coordinates, and evidence text."""
    repo = CitationRepository()
    try:
        return repo.get_citation_detail(
            db=db,
            citation_id=citation_id,
            user_id=current_user.id,
        )
    except (CitationNotFoundError, CitationAccessDeniedError):
        # Security Rule: Never reveal existence of another user's citation
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation not found",
        )
