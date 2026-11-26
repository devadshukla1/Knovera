"""Search endpoints for Knovera Semantic Vector Retrieval (Phase 3 C3.3)."""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_user_workspace
from backend.app.core.logging import get_logger
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.rag.reranker import RerankerError
from backend.app.rag.retrieval.bm25.retriever import BM25Retriever
from backend.app.rag.retrieval.exceptions import (
    DocumentScopeException,
    InvalidQueryException,
    RetrievalException,
)
from backend.app.rag.retrieval.hybrid_retriever import HybridRetriever
from backend.app.rag.retrieval.schemas import (
    BM25SearchRequest,
    BM25SearchResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from backend.app.rag.retrieval.semantic_retriever import SemanticRetriever
from backend.app.rag.vector_store.exceptions import ChromaUnavailableError

logger = get_logger("knovera.api.search")
router = APIRouter()


@router.post(
    "/{workspace_id}/search/semantic",
    response_model=SemanticSearchResponse,
    summary="Perform semantic vector retrieval over workspace documents",
)
def semantic_search(
    workspace_id: uuid.UUID,
    search_req: SemanticSearchRequest,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SemanticSearchResponse:
    """Retrieves ranked document chunks matching the query using dense vector cosine search.

    Guarantees:
        - Workspace isolation: Searches only within the specified workspace.
        - Authoritative text: Content is hydrated from PostgreSQL, never from vector store copy.
        - Strict validation: Verifies user ownership and optional document filter scope.
    """
    # 2. Execute retrieval via SemanticRetriever
    retriever = SemanticRetriever()
    try:
        response = retriever.retrieve(
            db=db,
            workspace_id=workspace_id,
            query=search_req.query,
            document_ids=search_req.document_ids,
            top_k=search_req.top_k,
        )
        return response
    except DocumentScopeException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidQueryException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ChromaUnavailableError as exc:
        logger.error("ChromaDB vector store unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector retrieval service is temporarily unavailable",
        ) from exc
    except RetrievalException as exc:
        logger.error("Semantic retrieval failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic retrieval failed: {exc}",
        ) from exc


@router.post(
    "/{workspace_id}/search/bm25",
    response_model=BM25SearchResponse,
    summary="Perform lexical BM25 Okapi search over workspace documents",
)
def bm25_search(
    workspace_id: uuid.UUID,
    search_req: BM25SearchRequest,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BM25SearchResponse:
    """Retrieves ranked document chunks matching the query using lexical BM25 Okapi search.

    Guarantees:
        - Workspace isolation: Searches only within the specified workspace.
        - Authoritative text: Content is hydrated from PostgreSQL.
        - Strict validation: Verifies user ownership and optional document filter scope.
    """
    retriever = BM25Retriever()
    try:
        response = retriever.retrieve(
            db=db,
            workspace_id=workspace_id,
            query=search_req.query,
            document_ids=search_req.document_ids,
            top_k=search_req.top_k,
        )
        return response
    except DocumentScopeException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidQueryException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RetrievalException as exc:
        logger.error("BM25 retrieval failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"BM25 retrieval failed: {exc}",
        ) from exc


@router.post(
    "/{workspace_id}/search/hybrid",
    response_model=HybridSearchResponse,
    summary="Perform hybrid retrieval (dense + lexical BM25 + RRF) over workspace documents",
)
def hybrid_search(
    workspace_id: uuid.UUID,
    search_req: HybridSearchRequest,
    workspace: Workspace = Depends(get_user_workspace),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HybridSearchResponse:
    """Retrieves ranked document chunks combining dense semantic vectors and lexical BM25 via Reciprocal Rank Fusion.

    Guarantees:
        - Workspace isolation: Searches only within the specified workspace.
        - Authoritative text: Content is hydrated from PostgreSQL.
        - Soft-deleted documents (deleted_at IS NOT NULL) are excluded.
        - Strict validation: Verifies user ownership and optional document filter scope.
    """
    retriever = HybridRetriever()
    try:
        response = retriever.retrieve(
            db=db,
            workspace_id=workspace_id,
            query=search_req.query,
            document_ids=search_req.document_ids,
            top_k=search_req.top_k,
            mode=search_req.mode,
            rerank=search_req.rerank,
        )
        return response
    except DocumentScopeException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidQueryException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ChromaUnavailableError as exc:
        logger.error("ChromaDB vector store unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector retrieval service is temporarily unavailable",
        ) from exc
    except RerankerError as exc:
        logger.error("Reranking failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reranking failed: {exc}",
        ) from exc
    except RetrievalException as exc:
        logger.error("Hybrid retrieval failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hybrid retrieval failed: {exc}",
        ) from exc
