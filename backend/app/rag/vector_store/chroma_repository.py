"""ChromaDB Vector Repository for batched upserts, querying, deletion, and reconciliation (Phase 3 C3.2)."""

from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.db.chroma import get_chroma_client
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.rag.embeddings.base import EmbeddingProvider
from backend.app.rag.embeddings.model_manager import EmbeddingModelManager
from backend.app.rag.vector_store.collection_manager import ChromaCollectionManager
from backend.app.rag.vector_store.exceptions import (
    ChromaUnavailableError,
    UpsertFailedError,
)
from backend.app.rag.vector_store.schemas import (
    ReconciliationReport,
    VectorRecord,
)

logger = get_logger("knovera.rag.vector_store.repository")


class ChromaVectorRepository:
    """Repository handling all CRUD and search interactions with ChromaDB vector indices."""

    def __init__(
        self,
        chroma_client: Optional[Any] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        self.settings = get_settings()
        self.client = chroma_client if chroma_client is not None else get_chroma_client()
        self._provider = embedding_provider
        self.collection_manager = ChromaCollectionManager(self.client) if self.client else None

    @property
    def provider(self) -> EmbeddingProvider:
        """Lazily resolves embedding provider singleton when needed."""
        if self._provider is None:
            self._provider = EmbeddingModelManager.get_instance().get_provider()
        return self._provider

    def get_active_collection(self) -> Any:
        """Retrieves or creates the collection corresponding to the active embedding provider."""
        if self.client is None or self.collection_manager is None:
            raise ChromaUnavailableError("Chroma client is not initialized or server is unreachable.")

        return self.collection_manager.get_or_create_collection(
            model_id=self.provider.get_model_id(),
            model_revision=self.provider.get_model_revision(),
            dimension=self.provider.get_dimension(),
        )

    def upsert_records(
        self,
        records: List[VectorRecord],
        collection: Optional[Any] = None,
        batch_size: Optional[int] = None,
    ) -> int:
        """Idempotently batch-upserts vector records into ChromaDB.

        Returns:
            Number of successfully upserted vector records.
        """
        if not records:
            return 0

        target_collection = collection or self.get_active_collection()
        effective_batch = batch_size or self.settings.CHROMA_INSERT_BATCH_SIZE
        total_upserted = 0

        for i in range(0, len(records), effective_batch):
            batch = records[i : i + effective_batch]
            ids = [r.id for r in batch]
            embeddings = [r.embedding for r in batch]
            metadatas = [r.metadata for r in batch]
            documents = [r.document_text or "" for r in batch]

            try:
                target_collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents,
                )
                total_upserted += len(batch)
            except Exception as exc:
                logger.exception("Failed to upsert vector batch of size %d into Chroma: %s", len(batch), exc)
                raise UpsertFailedError(f"ChromaDB batch upsert failed: {exc}") from exc

        logger.info("Successfully upserted %d vector records to collection '%s'", total_upserted, target_collection.name)
        return total_upserted

    def query_nearest(
        self,
        query_vector: List[float],
        workspace_id: uuid.UUID,
        document_ids: Optional[List[uuid.UUID]] = None,
        top_k: Optional[int] = None,
        collection: Optional[Any] = None,
    ) -> List[Tuple[str, float]]:
        """Queries ChromaDB for the nearest vectors within the authorized workspace scope.

        Returns:
            List of (chunk_id_str, distance_float) ordered by ascending distance.
        """
        target_collection = collection or self.get_active_collection()
        effective_top_k = top_k or self.settings.SEMANTIC_RETRIEVAL_TOP_K
        ws_id_str = str(workspace_id)

        # Construct server-controlled workspace metadata filter
        if document_ids:
            if len(document_ids) == 1:
                where_filter: Dict[str, Any] = {
                    "$and": [
                        {"workspace_id": ws_id_str},
                        {"document_id": str(document_ids[0])},
                    ]
                }
            else:
                where_filter = {
                    "$and": [
                        {"workspace_id": ws_id_str},
                        {"document_id": {"$in": [str(d) for d in document_ids]}},
                    ]
                }
        else:
            where_filter = {"workspace_id": ws_id_str}

        try:
            results = target_collection.query(
                query_embeddings=[query_vector],
                n_results=effective_top_k,
                where=where_filter,
                include=["distances", "metadatas"],
            )
        except Exception as exc:
            logger.exception("Chroma vector query failed for workspace %s: %s", workspace_id, exc)
            raise ChromaUnavailableError(f"Vector query failed: {exc}") from exc

        matched_ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]

        return list(zip(matched_ids, distances))

    def delete_by_document(
        self,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
        collection: Optional[Any] = None,
    ) -> None:
        """Deletes all indexed vectors belonging to a specific document."""
        target_collection = collection or self.get_active_collection()
        where_filter = {
            "$and": [
                {"workspace_id": str(workspace_id)},
                {"document_id": str(document_id)},
            ]
        }
        try:
            target_collection.delete(where=where_filter)
            logger.info("Deleted vectors for document %s in workspace %s", document_id, workspace_id)
        except Exception as exc:
            logger.warning("Failed to delete vectors for document %s: %s", document_id, exc)
            raise ChromaUnavailableError(f"Failed to delete document vectors: {exc}") from exc

    def delete_by_workspace(
        self,
        workspace_id: uuid.UUID,
        collection: Optional[Any] = None,
    ) -> None:
        """Deletes all indexed vectors belonging to a workspace across active and existing collections."""
        if self.client is None:
            logger.warning("Chroma client unavailable; skipping vector deletion for workspace %s", workspace_id)
            return

        where_filter = {"workspace_id": str(workspace_id)}
        if collection is not None:
            target_collections = [collection]
        else:
            try:
                target_collections = self.client.list_collections()
            except Exception as exc:
                logger.warning("Could not list collections from Chroma: %s. Falling back to active collection.", exc)
                try:
                    target_collections = [self.get_active_collection()]
                except Exception:
                    target_collections = []

        for col in target_collections:
            try:
                col.delete(where=where_filter)
                logger.info("Deleted vectors for workspace %s from collection %s", workspace_id, getattr(col, 'name', str(col)))
            except Exception as exc:
                logger.warning("Failed to delete vectors for workspace %s in collection %s: %s", workspace_id, getattr(col, 'name', str(col)), exc)

    def reconcile_workspace(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        collection: Optional[Any] = None,
    ) -> ReconciliationReport:
        """Identifies discrepancies between PostgreSQL authoritative chunks and Chroma vectors."""
        target_collection = collection or self.get_active_collection()

        # 1. Fetch active chunks from PostgreSQL
        pg_chunks = (
            db.query(DocumentChunk.id)
            .join(Document, Document.id == DocumentChunk.document_id)
            .filter(
                DocumentChunk.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .all()
        )
        pg_chunk_ids = {str(c[0]) for c in pg_chunks}

        # 2. Fetch Chroma vector IDs for workspace
        chroma_res = target_collection.get(
            where={"workspace_id": str(workspace_id)},
            include=[],
        )
        chroma_ids = set(chroma_res.get("ids", []))

        missing_in_chroma = list(pg_chunk_ids - chroma_ids)
        orphan_in_chroma = list(chroma_ids - pg_chunk_ids)

        return ReconciliationReport(
            workspace_id=workspace_id,
            collection_name=target_collection.name,
            total_pg_chunks=len(pg_chunk_ids),
            total_chroma_vectors=len(chroma_ids),
            missing_vector_chunk_ids=missing_in_chroma,
            orphan_chroma_ids=orphan_in_chroma,
            is_synchronized=(len(missing_in_chroma) == 0 and len(orphan_in_chroma) == 0),
        )
