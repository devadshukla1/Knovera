"""Semantic Vector Retriever orchestrating query encoding, vector search, and PostgreSQL hydration (Phase 3 C3.3)."""

import time
from typing import List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.rag.embeddings.base import EmbeddingProvider
from backend.app.rag.embeddings.model_manager import EmbeddingModelManager
from backend.app.rag.retrieval.query_validator import QueryValidator
from backend.app.rag.retrieval.result_hydrator import ResultHydrator
from backend.app.rag.retrieval.schemas import (
    SemanticSearchResponse,
    SemanticSearchResult,
)
from backend.app.rag.vector_store.chroma_repository import ChromaVectorRepository

logger = get_logger("knovera.rag.retrieval.semantic")


class SemanticRetriever:
    """End-to-end semantic search engine for workspace-scoped evidence retrieval."""

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_repository: Optional[ChromaVectorRepository] = None,
        query_validator: Optional[QueryValidator] = None,
        result_hydrator: Optional[ResultHydrator] = None,
    ) -> None:
        self.settings = get_settings()
        self.provider = embedding_provider or EmbeddingModelManager.get_instance().get_provider()
        self.vector_repo = vector_repository or ChromaVectorRepository(embedding_provider=self.provider)
        self.validator = query_validator or QueryValidator()
        self.hydrator = result_hydrator or ResultHydrator()

    def retrieve(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        query: str,
        document_ids: Optional[List[uuid.UUID]] = None,
        top_k: Optional[int] = None,
    ) -> SemanticSearchResponse:
        """Executes full semantic similarity search within workspace boundaries.

        Returns:
            SemanticSearchResponse with ordered, PostgreSQL-hydrated evidence chunks.
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
            top_k or self.settings.SEMANTIC_RETRIEVAL_TOP_K,
            self.settings.SEMANTIC_RETRIEVAL_MAX_TOP_K,
        )

        # 2. Query Encoding
        start_encode = time.perf_counter()
        query_vector = self.provider.encode_query(validated_query)
        metrics["query_encoding_ms"] = round((time.perf_counter() - start_encode) * 1000, 2)

        # 3. Vector Similarity Search in ChromaDB
        start_search = time.perf_counter()
        matched_vectors = self.vector_repo.query_nearest(
            query_vector=query_vector,
            workspace_id=workspace_id,
            document_ids=validated_doc_ids if validated_doc_ids else None,
            top_k=effective_top_k,
        )
        metrics["vector_search_ms"] = round((time.perf_counter() - start_search) * 1000, 2)

        # 4. PostgreSQL Result Hydration & Provenance Mapping
        start_hydrate = time.perf_counter()
        results: List[SemanticSearchResult] = self.hydrator.hydrate_results(
            db=db,
            workspace_id=workspace_id,
            matched_vectors=matched_vectors,
            model_id=self.provider.get_model_id(),
            model_revision=self.provider.get_model_revision(),
        )
        metrics["hydration_ms"] = round((time.perf_counter() - start_hydrate) * 1000, 2)
        metrics["total_duration_ms"] = round((time.perf_counter() - start_total) * 1000, 2)

        logger.info(
            "Semantic retrieval for workspace %s ('%s'): %d chunks matched in %.2fms",
            workspace_id,
            validated_query[:30],
            len(results),
            metrics["total_duration_ms"],
        )

        return SemanticSearchResponse(
            workspace_id=workspace_id,
            query=validated_query,
            total_results=len(results),
            results=results,
            duration_metrics=metrics,
        )
