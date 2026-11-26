"""Hybrid Retrieval Service combining Dense Vector Search and BM25 via Reciprocal Rank Fusion (Phase 4 C4.2)."""

import time
from typing import List, Optional, Tuple
import uuid
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.rag.reranker import CrossEncoderReranker
from backend.app.rag.retrieval.bm25.retriever import BM25Retriever
from backend.app.rag.retrieval.query_validator import QueryValidator
from backend.app.rag.retrieval.result_hydrator import ResultHydrator
from backend.app.rag.retrieval.rrf import ReciprocalRankFusion
from backend.app.rag.retrieval.schemas import (
    HybridSearchResponse,
    HybridSearchResult,
)
from backend.app.rag.retrieval.semantic_retriever import SemanticRetriever

logger = get_logger("knovera.rag.retrieval.hybrid")


class HybridRetriever:
    """Orchestrates multi-modal evidence retrieval across dense semantic vectors, lexical BM25, and Cross-Encoder reranking."""

    def __init__(
        self,
        semantic_retriever: Optional[SemanticRetriever] = None,
        bm25_retriever: Optional[BM25Retriever] = None,
        rrf: Optional[ReciprocalRankFusion] = None,
        query_validator: Optional[QueryValidator] = None,
        result_hydrator: Optional[ResultHydrator] = None,
        reranker: Optional[CrossEncoderReranker] = None,
    ) -> None:
        self.settings = get_settings()
        self.semantic_retriever = semantic_retriever or SemanticRetriever()
        self.bm25_retriever = bm25_retriever or BM25Retriever()
        self.rrf = rrf or ReciprocalRankFusion(k=self.settings.RRF_K)
        self.validator = query_validator or QueryValidator()
        self.hydrator = result_hydrator or ResultHydrator()
        self.reranker = reranker or CrossEncoderReranker(settings=self.settings)

    def retrieve(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        query: str,
        document_ids: Optional[List[uuid.UUID]] = None,
        top_k: Optional[int] = None,
        mode: Optional[str] = None,
        rerank: Optional[bool] = None,
        dense_top_k: Optional[int] = None,
        bm25_top_k: Optional[int] = None,
        rrf_k: Optional[int] = None,
        reranker_candidate_k: Optional[int] = None,
        bm25_k1: Optional[float] = None,
        bm25_b: Optional[float] = None,
    ) -> HybridSearchResponse:
        """Executes hybrid retrieval combining dense and lexical candidate lists via RRF.

        Modes:
            - "hybrid" (default): Dense ChromaDB + BM25 Okapi -> Reciprocal Rank Fusion -> PostgreSQL hydration.
            - "semantic": Pure dense vector similarity search.
            - "bm25": Pure lexical BM25 Okapi keyword search.

        Guarantees:
            - Strict workspace isolation: Never searches across workspace boundaries.
            - Relational authority: All content and provenance hydrated directly from PostgreSQL.
            - Soft-deleted documents (deleted_at IS NOT NULL) are strictly excluded.
            - Deterministic rank sorting with chunk_id tie-breaking.
        """
        start_total = time.perf_counter()
        metrics: dict[str, float] = {}

        # 1. Validate query & document scope
        validated_query = self.validator.validate_query(query)
        validated_doc_ids = self.validator.validate_document_scope(
            db=db,
            workspace_id=workspace_id,
            document_ids=document_ids,
        )

        effective_mode = (mode or self.settings.RETRIEVAL_MODE).lower()
        effective_top_k = min(
            top_k or self.settings.HYBRID_RETRIEVAL_TOP_K,
            self.settings.SEMANTIC_RETRIEVAL_MAX_TOP_K,
        )

        # Mode A: Pure Semantic Vector Search
        if effective_mode == "semantic":
            sem_res = self.semantic_retriever.retrieve(
                db=db,
                workspace_id=workspace_id,
                query=validated_query,
                document_ids=validated_doc_ids,
                top_k=effective_top_k,
            )
            hybrid_results = [
                HybridSearchResult(
                    chunk_id=r.chunk_id,
                    document_id=r.document_id,
                    workspace_id=r.workspace_id,
                    document_filename=r.document_filename,
                    content=r.content,
                    page_start=r.page_start,
                    page_end=r.page_end,
                    slide_number=r.slide_number,
                    section_title=r.section_title,
                    source_segments=r.source_segments,
                    rrf_score=1.0 / (self.settings.RRF_K + r.rank),
                    rank=r.rank,
                    dense_rank=r.rank,
                    bm25_rank=None,
                    vector_distance=r.distance,
                    bm25_score=None,
                    retrieval_sources=["semantic"],
                    distance=r.distance,
                    embedding_model=r.embedding_model,
                    embedding_revision=r.embedding_revision,
                )
                for r in sem_res.results
            ]
            metrics.update(sem_res.duration_metrics)
            metrics["total_duration_ms"] = round((time.perf_counter() - start_total) * 1000, 2)
            return HybridSearchResponse(
                workspace_id=workspace_id,
                query=validated_query,
                mode="semantic",
                total_results=len(hybrid_results),
                results=hybrid_results,
                duration_metrics=metrics,
            )

        # Mode B: Pure Lexical BM25 Search
        if effective_mode == "bm25":
            bm25_res = self.bm25_retriever.retrieve(
                db=db,
                workspace_id=workspace_id,
                query=validated_query,
                document_ids=validated_doc_ids,
                top_k=effective_top_k,
            )
            hybrid_results = [
                HybridSearchResult(
                    chunk_id=r.chunk_id,
                    document_id=r.document_id,
                    workspace_id=r.workspace_id,
                    document_filename=r.document_filename,
                    content=r.content,
                    page_start=r.page_start,
                    page_end=r.page_end,
                    slide_number=r.slide_number,
                    section_title=r.section_title,
                    source_segments=r.source_segments,
                    rrf_score=1.0 / (self.settings.RRF_K + r.rank),
                    rank=r.rank,
                    dense_rank=None,
                    bm25_rank=r.rank,
                    vector_distance=None,
                    bm25_score=r.bm25_score,
                    retrieval_sources=["bm25"],
                    distance=0.0,
                    embedding_model="bm25_okapi",
                    embedding_revision="v1",
                )
                for r in bm25_res.results
            ]
            metrics.update(bm25_res.duration_metrics)
            metrics["total_duration_ms"] = round((time.perf_counter() - start_total) * 1000, 2)
            return HybridSearchResponse(
                workspace_id=workspace_id,
                query=validated_query,
                mode="bm25",
                total_results=len(hybrid_results),
                results=hybrid_results,
                duration_metrics=metrics,
            )

        # Mode C: Full Hybrid Retrieval (Dense + BM25 + RRF + Cross-Encoder Reranking)
        effective_dense_k = dense_top_k or self.settings.DENSE_RETRIEVAL_TOP_K
        effective_bm25_k = bm25_top_k or self.settings.BM25_RETRIEVAL_TOP_K

        # 2. Dense Semantic Vector Search in ChromaDB
        start_dense = time.perf_counter()
        query_vector = self.semantic_retriever.provider.encode_query(validated_query)
        matched_vectors = self.semantic_retriever.vector_repo.query_nearest(
            query_vector=query_vector,
            workspace_id=workspace_id,
            document_ids=validated_doc_ids if validated_doc_ids else None,
            top_k=effective_dense_k,
        )
        dense_pairs: List[Tuple[uuid.UUID, float]] = []
        for cid_str, dist in matched_vectors:
            try:
                dense_pairs.append((uuid.UUID(cid_str), float(dist)))
            except (ValueError, TypeError):
                continue
        metrics["dense_search_ms"] = round((time.perf_counter() - start_dense) * 1000, 2)

        # 3. BM25 Lexical Inverted Index Search
        start_bm25 = time.perf_counter()
        bm25_index = self.bm25_retriever.cache.get_index(
            db=db,
            workspace_id=workspace_id,
            k1=bm25_k1,
            b=bm25_b,
        )
        matched_bm25 = bm25_index.search(
            query=validated_query,
            top_k=effective_bm25_k,
            document_ids=validated_doc_ids if validated_doc_ids else None,
        )
        metrics["bm25_search_ms"] = round((time.perf_counter() - start_bm25) * 1000, 2)

        # 4. Reciprocal Rank Fusion (RRF)
        should_rerank = self.settings.RERANKER_ENABLED if rerank is None else rerank
        effective_pool_k = reranker_candidate_k or self.settings.RERANKER_CANDIDATE_K
        candidate_k = max(effective_top_k, effective_pool_k) if should_rerank else effective_top_k

        start_fusion = time.perf_counter()
        rrf_engine = self.rrf if rrf_k is None or rrf_k == self.settings.RRF_K else ReciprocalRankFusion(k=rrf_k)
        fused_candidates = rrf_engine.fuse(
            ranked_lists={
                "semantic": dense_pairs,
                "bm25": matched_bm25,
            },
            top_k=candidate_k,
        )
        metrics["rrf_fusion_ms"] = round((time.perf_counter() - start_fusion) * 1000, 2)

        # 5. Authoritative PostgreSQL Hydration preserving fused ranking
        start_hydrate = time.perf_counter()
        hydrated_results: List[HybridSearchResult] = self.hydrator.hydrate_hybrid_results(
            db=db,
            workspace_id=workspace_id,
            fused_candidates=fused_candidates,
        )
        metrics["hydration_ms"] = round((time.perf_counter() - start_hydrate) * 1000, 2)

        # 6. Candidate Selection and Cross-Encoder Reranking (Phase 4 C4.4–C4.5)
        was_reranked = False
        if should_rerank and hydrated_results:
            start_rerank = time.perf_counter()
            reranked_tuples, was_reranked = self.reranker.rerank_candidates(
                query=validated_query,
                candidates=hydrated_results,
                get_content=lambda r: r.content,
                get_section_title=lambda r: r.section_title,
                get_rrf_rank=lambda r: r.rank,
                get_chunk_id=lambda r: r.chunk_id,
                top_k=effective_top_k,
            )
            metrics["reranking_ms"] = round((time.perf_counter() - start_rerank) * 1000, 2)
            results: List[HybridSearchResult] = []
            for cand, score, new_rank in reranked_tuples:
                cand.reranker_score = score if was_reranked else None
                cand.reranker_rank = new_rank if was_reranked else None
                cand.rank = new_rank
                results.append(cand)
        else:
            results = hydrated_results[:effective_top_k]

        metrics["total_duration_ms"] = round((time.perf_counter() - start_total) * 1000, 2)

        logger.info(
            "Hybrid retrieval for workspace %s ('%s'): %d dense, %d bm25 -> %d fused -> %d hydrated -> %d final (reranked=%s) in %.2fms",
            workspace_id,
            validated_query[:30],
            len(dense_pairs),
            len(matched_bm25),
            len(fused_candidates),
            len(hydrated_results),
            len(results),
            was_reranked,
            metrics["total_duration_ms"],
        )

        return HybridSearchResponse(
            workspace_id=workspace_id,
            query=validated_query,
            mode="hybrid",
            reranked=was_reranked,
            total_results=len(results),
            results=results,
            candidate_results=hydrated_results if was_reranked else None,
            duration_metrics=metrics,
        )
