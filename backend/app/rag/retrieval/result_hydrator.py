"""PostgreSQL Chunk Hydration and Provenance Enrichment (Phase 3 C3.3)."""

from typing import Any, List, Tuple
import uuid
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.rag.retrieval.schemas import (
    BM25SearchResult,
    HybridSearchResult,
    SemanticSearchResult,
)

logger = get_logger("knovera.rag.retrieval.hydrator")


class ResultHydrator:
    """Hydrates authoritative chunk content and source provenance from PostgreSQL."""

    def hydrate_results(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        matched_vectors: List[Tuple[str, float]],
        model_id: str,
        model_revision: str,
    ) -> List[SemanticSearchResult]:
        """Maps Chroma vector matches to PostgreSQL chunks, preserving order and distance.

        Guarantees:
            - Results strictly filtered to the authenticated workspace_id.
            - Soft-deleted documents (deleted_at IS NOT NULL) are excluded.
            - Stale Chroma IDs not in PostgreSQL are excluded safely.
            - Ranking order is strictly preserved.
        """
        if not matched_vectors:
            return []

        # Convert chunk UUID strings to UUID objects
        valid_uuid_pairs = []
        for chunk_id_str, dist in matched_vectors:
            try:
                valid_uuid_pairs.append((uuid.UUID(chunk_id_str), dist))
            except (ValueError, TypeError):
                logger.warning("Ignoring invalid UUID string from vector store: %s", chunk_id_str)

        if not valid_uuid_pairs:
            return []

        chunk_ids = [c[0] for c in valid_uuid_pairs]
        distance_map = {c[0]: c[1] for c in valid_uuid_pairs}

        # Query PostgreSQL authoritative records
        records = (
            db.query(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .filter(
                DocumentChunk.id.in_(chunk_ids),
                DocumentChunk.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .all()
        )

        # Build lookup table: chunk_id -> (chunk, document)
        lookup = {chunk.id: (chunk, doc) for chunk, doc in records}

        # Preserve the original vector ranking order
        hydrated_results: List[SemanticSearchResult] = []
        rank = 1

        for chunk_id, dist in valid_uuid_pairs:
            if chunk_id in lookup:
                chunk, doc = lookup[chunk_id]
                hydrated_results.append(
                    SemanticSearchResult(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        workspace_id=chunk.workspace_id,
                        document_filename=doc.original_filename,
                        content=chunk.content,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        slide_number=chunk.slide_number,
                        section_title=chunk.section_title,
                        source_segments=chunk.source_segments or [],
                        distance=float(dist),
                        rank=rank,
                        embedding_model=model_id,
                        embedding_revision=model_revision,
                    )
                )
                rank += 1

        return hydrated_results

    def hydrate_bm25_results(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        matched_chunks: List[Tuple[uuid.UUID, float]],
    ) -> List[BM25SearchResult]:
        """Maps BM25 chunk matches to PostgreSQL chunks, preserving order and BM25 score."""
        if not matched_chunks:
            return []

        chunk_ids = [c[0] for c in matched_chunks]
        score_map = {c[0]: c[1] for c in matched_chunks}

        records = (
            db.query(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .filter(
                DocumentChunk.id.in_(chunk_ids),
                DocumentChunk.workspace_id == workspace_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .all()
        )

        lookup = {chunk.id: (chunk, doc) for chunk, doc in records}
        results: List[BM25SearchResult] = []
        rank = 1

        for chunk_id, score in matched_chunks:
            if chunk_id in lookup:
                chunk, doc = lookup[chunk_id]
                results.append(
                    BM25SearchResult(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        workspace_id=chunk.workspace_id,
                        document_filename=doc.original_filename,
                        content=chunk.content,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        slide_number=chunk.slide_number,
                        section_title=chunk.section_title,
                        source_segments=chunk.source_segments or [],
                        bm25_score=float(score),
                        rank=rank,
                    )
                )
                rank += 1

        return results

    def hydrate_hybrid_results(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        fused_candidates: List[Any],
    ) -> List[HybridSearchResult]:
        """Maps fused RRF candidates to PostgreSQL records, preserving fused ranking order."""
        if not fused_candidates:
            return []

        chunk_ids = [fc.chunk_id for fc in fused_candidates]

        records = (
            db.query(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .filter(
                DocumentChunk.id.in_(chunk_ids),
                DocumentChunk.workspace_id == workspace_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .all()
        )

        lookup = {chunk.id: (chunk, doc) for chunk, doc in records}
        results: List[HybridSearchResult] = []
        rank = 1

        for fc in fused_candidates:
            if fc.chunk_id in lookup:
                chunk, doc = lookup[fc.chunk_id]
                results.append(
                    HybridSearchResult(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        workspace_id=chunk.workspace_id,
                        document_filename=doc.original_filename,
                        content=chunk.content,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        slide_number=chunk.slide_number,
                        section_title=chunk.section_title,
                        source_segments=chunk.source_segments or [],
                        rrf_score=float(fc.rrf_score),
                        rank=rank,
                        dense_rank=fc.dense_rank,
                        bm25_rank=fc.bm25_rank,
                        vector_distance=fc.vector_distance,
                        bm25_score=fc.bm25_score,
                        retrieval_sources=list(fc.retrieval_sources),
                    )
                )
                rank += 1

        return results
