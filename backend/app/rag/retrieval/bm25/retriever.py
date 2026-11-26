"""BM25 Lexical Retrieval Service for Knovera (Phase 4 C4.1)."""

import time
from typing import List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.rag.retrieval.bm25.cache import BM25IndexCache
from backend.app.rag.retrieval.query_validator import QueryValidator
from backend.app.rag.retrieval.result_hydrator import ResultHydrator
from backend.app.rag.retrieval.schemas import (
    BM25SearchResponse,
    BM25SearchResult,
)

logger = get_logger("knovera.rag.retrieval.bm25")


class BM25Retriever:
    """Orchestrates query validation, BM25 inverted index search, and PostgreSQL chunk hydration."""

    def __init__(
        self,
        cache: Optional[BM25IndexCache] = None,
        query_validator: Optional[QueryValidator] = None,
        result_hydrator: Optional[ResultHydrator] = None,
    ) -> None:
        self.settings = get_settings()
        self.cache = cache or BM25IndexCache.get_instance()
        self.validator = query_validator or QueryValidator()
        self.hydrator = result_hydrator or ResultHydrator()

    def retrieve(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        query: str,
        document_ids: Optional[List[uuid.UUID]] = None,
        top_k: Optional[int] = None,
        k1: Optional[float] = None,
        b: Optional[float] = None,
    ) -> BM25SearchResponse:
        """Executes lexical BM25 Okapi search within workspace boundaries.

        Returns:
            BM25SearchResponse with ordered, PostgreSQL-hydrated evidence chunks.
        """
        start_total = time.perf_counter()
        metrics: dict[str, float] = {}

        # 1. Validate query text & document scope
        validated_query = self.validator.validate_query(query)
        validated_doc_ids = self.validator.validate_document_scope(
            db=db,
            workspace_id=workspace_id,
            document_ids=document_ids,
        )

        effective_top_k = min(
            top_k or self.settings.BM25_RETRIEVAL_TOP_K,
            self.settings.SEMANTIC_RETRIEVAL_MAX_TOP_K,
        )

        # 2. In-memory index fetch or build from PostgreSQL
        start_index = time.perf_counter()
        index = self.cache.get_index(db=db, workspace_id=workspace_id, k1=k1, b=b)
        metrics["index_access_ms"] = round((time.perf_counter() - start_index) * 1000, 2)

        # 3. Lexical BM25 search
        start_search = time.perf_counter()
        matched_chunks = index.search(
            query=validated_query,
            top_k=effective_top_k,
            document_ids=validated_doc_ids if validated_doc_ids else None,
        )
        metrics["bm25_search_ms"] = round((time.perf_counter() - start_search) * 1000, 2)

        # 4. Authoritative PostgreSQL hydration
        start_hydrate = time.perf_counter()
        results: List[BM25SearchResult] = self.hydrator.hydrate_bm25_results(
            db=db,
            workspace_id=workspace_id,
            matched_chunks=matched_chunks,
        )
        metrics["hydration_ms"] = round((time.perf_counter() - start_hydrate) * 1000, 2)
        metrics["total_duration_ms"] = round((time.perf_counter() - start_total) * 1000, 2)

        logger.info(
            "BM25 retrieval for workspace %s ('%s'): %d chunks matched in %.2fms",
            workspace_id,
            validated_query[:30],
            len(results),
            metrics["total_duration_ms"],
        )

        return BM25SearchResponse(
            workspace_id=workspace_id,
            query=validated_query,
            total_results=len(results),
            results=results,
            duration_metrics=metrics,
        )
