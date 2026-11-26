"""Chunk Embedding Service for Knovera Topic Discovery (Phase 6 C6.1).

Responsible for:
1. Extracting canonical active document chunks from PostgreSQL for a workspace.
2. Checking ChromaDB to reuse precomputed embeddings where available.
3. Generating embeddings for any missing or unindexed chunks via EmbeddingProvider.
4. Validating dimensionality, finiteness, zero-norm handling, and enforcing L2 normalization.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.db.chroma import get_chroma_client
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.ml.topic_clustering.schemas import ClusteringChunkRecord
from backend.app.rag.embeddings.base import EmbeddingProvider
from backend.app.rag.embeddings.model_manager import EmbeddingModelManager
from backend.app.rag.vector_store.collection_manager import ChromaCollectionManager

logger = get_logger("knovera.ml.topic_clustering.embedding_service")


class ChunkEmbeddingService:
    """Service for extracting canonical chunks and producing validated, L2-normalized embeddings."""

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        chroma_client: Optional[Any] = None,
    ) -> None:
        self.embedding_provider = (
            embedding_provider or EmbeddingModelManager.get_instance().get_provider()
        )
        self.chroma_client = (
            chroma_client if chroma_client is not None else get_chroma_client()
        )
        self.collection_manager = (
            ChromaCollectionManager(self.chroma_client) if self.chroma_client else None
        )

    def extract_workspace_chunks(
        self,
        session: Session,
        workspace_id: uuid.UUID,
    ) -> List[DocumentChunk]:
        """Queries PostgreSQL for all non-deleted, active document chunks in workspace.

        Strictly enforces multi-tenant workspace isolation and excludes chunks from
        soft-deleted documents.
        """
        stmt = (
            select(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
        results = session.execute(stmt).scalars().all()
        logger.info(
            "Extracted %d active chunks for workspace %s", len(results), workspace_id
        )
        return list(results)

    def _fetch_embeddings_from_chroma(
        self,
        chunk_ids: List[str],
    ) -> Dict[str, np.ndarray]:
        """Attempts to retrieve cached vector embeddings from ChromaDB for the given chunk IDs."""
        if not self.chroma_client or not self.collection_manager:
            return {}

        expected_dim = self.embedding_provider.get_dimension()
        collection_name = self.collection_manager.generate_collection_name(
            model_id=self.embedding_provider.get_model_id(),
            model_revision=self.embedding_provider.get_model_revision(),
            dimension=expected_dim,
        )

        try:
            collection = self.chroma_client.get_collection(name=collection_name)
        except Exception:
            logger.debug(
                "Chroma collection '%s' not found or inaccessible; will generate embeddings.",
                collection_name,
            )
            return {}

        found_embeddings: Dict[str, np.ndarray] = {}
        # Fetch in batches if chunk_ids is large
        batch_size = 500
        for i in range(0, len(chunk_ids), batch_size):
            batch = chunk_ids[i : i + batch_size]
            try:
                res = collection.get(ids=batch, include=["embeddings"])
                ids_returned = res.get("ids", [])
                vectors = res.get("embeddings", [])
                for cid, vec in zip(ids_returned, vectors):
                    if vec is not None and len(vec) == expected_dim:
                        arr = np.asarray(vec, dtype=np.float32)
                        if np.all(np.isfinite(arr)):
                            found_embeddings[cid] = arr
            except Exception as exc:
                logger.warning("Error fetching batch from ChromaDB: %s", exc)

        logger.info(
            "Reused %d / %d embeddings from ChromaDB collection '%s'",
            len(found_embeddings),
            len(chunk_ids),
            collection_name,
        )
        return found_embeddings

    def normalize_and_validate(
        self,
        raw_embeddings: np.ndarray,
        expected_dim: int,
    ) -> np.ndarray:
        """Validates dimensionality, finiteness, guards against zero-norm, and applies L2 normalization."""
        if raw_embeddings.ndim != 2:
            raise ValueError(
                f"Embedding array must be 2D, got shape {raw_embeddings.shape}"
            )
        if raw_embeddings.shape[1] != expected_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {expected_dim}, got {raw_embeddings.shape[1]}"
            )

        if not np.all(np.isfinite(raw_embeddings)):
            raise ValueError("Embedding array contains NaN or Infinite values")

        # Zero-norm detection & handling
        norms = np.linalg.norm(raw_embeddings, axis=1, keepdims=True)
        zero_norm_mask = (norms < 1e-12).squeeze()

        embeddings_clean = raw_embeddings.copy()
        if np.any(zero_norm_mask):
            logger.warning(
                "Detected %d zero-norm embeddings; adding small epsilon perturbation.",
                int(np.sum(zero_norm_mask)),
            )
            # Add uniform tiny epsilon to avoid division by zero
            epsilon_vec = np.full(
                (embeddings_clean.shape[1],), 1e-6, dtype=np.float32
            )
            if zero_norm_mask.ndim == 0:  # single row
                embeddings_clean[0] = epsilon_vec
            else:
                embeddings_clean[zero_norm_mask] = epsilon_vec
            norms = np.linalg.norm(embeddings_clean, axis=1, keepdims=True)

        # L2 Unit Normalization: x / ||x||_2
        normalized = embeddings_clean / norms

        # Final sanity check: all norms must be 1.0 +/- 1e-4
        new_norms = np.linalg.norm(normalized, axis=1)
        if not np.allclose(new_norms, 1.0, atol=1e-4):
            raise ValueError("L2 normalization failed to produce unit vectors")

        return normalized.astype(np.float32)

    def generate_chunk_embeddings(
        self,
        chunks: List[DocumentChunk],
        reuse_chroma: bool = True,
        force_regenerate: bool = False,
    ) -> Tuple[List[ClusteringChunkRecord], np.ndarray]:
        """Generates or retrieves embeddings for the given list of chunks.

        Returns:
            Tuple of:
            - List of ClusteringChunkRecord
            - np.ndarray of shape (N, dimension), dtype float32, L2-normalized.
        """
        if not chunks:
            expected_dim = self.embedding_provider.get_dimension()
            return [], np.empty((0, expected_dim), dtype=np.float32)

        chunk_ids = [str(c.id) for c in chunks]
        expected_dim = self.embedding_provider.get_dimension()

        # Step 1: Check ChromaDB for existing embeddings if reuse_chroma and not force_regenerate
        chroma_cache: Dict[str, np.ndarray] = {}
        if reuse_chroma and not force_regenerate:
            chroma_cache = self._fetch_embeddings_from_chroma(chunk_ids)

        # Step 2: Identify missing chunks
        missing_indices = [
            i for i, cid in enumerate(chunk_ids) if cid not in chroma_cache
        ]
        missing_texts = [chunks[i].content for i in missing_indices]

        # Step 3: Compute missing embeddings
        new_embeddings: List[List[float]] = []
        if missing_texts:
            logger.info("Computing embeddings for %d chunks...", len(missing_texts))
            if hasattr(self.embedding_provider, "encode_documents"):
                new_embeddings = self.embedding_provider.encode_documents(missing_texts)
            elif hasattr(self.embedding_provider, "embed_documents"):
                new_embeddings = self.embedding_provider.embed_documents(missing_texts)
            else:
                raise AttributeError(
                    f"Embedding provider {type(self.embedding_provider).__name__} lacks encode_documents method"
                )

        # Step 4: Assemble assembled raw embedding matrix in exact chunk order
        raw_matrix = np.zeros((len(chunks), expected_dim), dtype=np.float32)
        new_iter = iter(new_embeddings)

        for i, cid in enumerate(chunk_ids):
            if cid in chroma_cache:
                raw_matrix[i] = chroma_cache[cid]
            else:
                raw_matrix[i] = np.asarray(next(new_iter), dtype=np.float32)

        # Step 5: Normalize and validate
        normalized_matrix = self.normalize_and_validate(raw_matrix, expected_dim)

        # Step 6: Build aligned ClusteringChunkRecord objects
        records: List[ClusteringChunkRecord] = []
        for c in chunks:
            text_preview = (
                (c.content[:197] + "...") if len(c.content) > 200 else c.content
            )
            record = ClusteringChunkRecord(
                chunk_id=str(c.id),
                document_id=str(c.document_id),
                workspace_id=str(c.workspace_id),
                chunk_index=c.chunk_index,
                page_number=c.page_start,
                token_count=c.token_count,
                content_hash=c.content_hash,
                text_preview=text_preview,
            )
            records.append(record)

        return records, normalized_matrix
