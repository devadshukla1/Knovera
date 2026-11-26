"""Thread-Safe In-Memory BM25 Workspace Index Cache with LRU Eviction (Phase 4 C4.1)."""

from collections import OrderedDict
import threading
from typing import Dict, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.rag.retrieval.bm25.index import BM25ChunkDocument, BM25WorkspaceIndex

logger = get_logger("knovera.rag.retrieval.bm25.cache")


class BM25IndexCache:
    """Thread-safe bounded in-memory cache for workspace BM25 inverted indexes."""

    _instance: Optional["BM25IndexCache"] = None
    _singleton_lock = threading.Lock()

    def __init__(self, max_workspaces: Optional[int] = None) -> None:
        settings = get_settings()
        self.max_workspaces = max_workspaces or settings.BM25_INDEX_CACHE_MAX_WORKSPACES
        self._cache: OrderedDict[uuid.UUID, BM25WorkspaceIndex] = OrderedDict()
        self._global_lock = threading.Lock()
        self._workspace_locks: Dict[uuid.UUID, threading.Lock] = {}
        self._ws_locks_guard = threading.Lock()

    @classmethod
    def get_instance(cls) -> "BM25IndexCache":
        """Singleton accessor for global BM25 workspace cache."""
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _get_workspace_lock(self, workspace_id: uuid.UUID) -> threading.Lock:
        """Retrieves or creates a dedicated build lock for a given workspace."""
        with self._ws_locks_guard:
            if workspace_id not in self._workspace_locks:
                self._workspace_locks[workspace_id] = threading.Lock()
            return self._workspace_locks[workspace_id]

    def has_index(self, workspace_id: uuid.UUID) -> bool:
        """Checks if a workspace index is currently cached."""
        with self._global_lock:
            return workspace_id in self._cache

    @property
    def cached_workspace_count(self) -> int:
        """Returns total number of currently cached workspace indexes."""
        with self._global_lock:
            return len(self._cache)

    def _set_index(self, workspace_id: uuid.UUID, index: BM25WorkspaceIndex) -> None:
        """Directly inserts an index into cache with LRU eviction enforcement (used for testing)."""
        with self._global_lock:
            self._cache[workspace_id] = index
            self._cache.move_to_end(workspace_id)
            while len(self._cache) > self.max_workspaces:
                evicted_id, _ = self._cache.popitem(last=False)
                logger.debug("Evicted BM25 index for workspace %s from cache", evicted_id)

    def get_index(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        k1: Optional[float] = None,
        b: Optional[float] = None,
    ) -> BM25WorkspaceIndex:
        """Retrieves cached workspace index or builds it from PostgreSQL chunks.

        Guarantees:
            - Thread-safe double-checked build locking per workspace.
            - Relational source of truth: Chunks queried directly from PostgreSQL.
            - Exclusion of soft-deleted documents (deleted_at IS NOT NULL).
            - LRU cache eviction when cache capacity is reached.
        """
        # 1. Fast path: check cache under global lock
        with self._global_lock:
            if workspace_id in self._cache:
                self._cache.move_to_end(workspace_id)
                return self._cache[workspace_id]

        # 2. Slow path: acquire workspace-specific lock to build
        ws_lock = self._get_workspace_lock(workspace_id)
        with ws_lock:
            # Double check cache
            with self._global_lock:
                if workspace_id in self._cache:
                    self._cache.move_to_end(workspace_id)
                    return self._cache[workspace_id]

            # 3. Query authoritative PostgreSQL document_chunks
            settings = get_settings()
            effective_k1 = k1 if k1 is not None else settings.BM25_K1
            effective_b = b if b is not None else settings.BM25_B

            records = (
                db.query(
                    DocumentChunk.id,
                    DocumentChunk.document_id,
                    DocumentChunk.workspace_id,
                    DocumentChunk.content,
                )
                .join(Document, Document.id == DocumentChunk.document_id)
                .filter(
                    DocumentChunk.workspace_id == workspace_id,
                    Document.workspace_id == workspace_id,
                    Document.deleted_at.is_(None),
                )
                .all()
            )

            chunks = [
                BM25ChunkDocument(
                    chunk_id=r[0],
                    document_id=r[1],
                    workspace_id=r[2],
                    content=r[3],
                )
                for r in records
            ]

            logger.info(
                "Building BM25 index for workspace %s from %d active PostgreSQL chunk(s)",
                workspace_id,
                len(chunks),
            )
            index = BM25WorkspaceIndex(
                workspace_id=workspace_id,
                chunks=chunks,
                k1=effective_k1,
                b=effective_b,
            )

            # 4. Store in cache under global lock with LRU eviction
            with self._global_lock:
                self._cache[workspace_id] = index
                self._cache.move_to_end(workspace_id)
                while len(self._cache) > self.max_workspaces:
                    evicted_id, _ = self._cache.popitem(last=False)
                    logger.debug("Evicted BM25 index for workspace %s from cache", evicted_id)

            return index

    def invalidate(self, workspace_id: uuid.UUID) -> bool:
        """Evicts a workspace index from cache upon document indexing, deletion, or reprocessing."""
        with self._global_lock:
            if workspace_id in self._cache:
                del self._cache[workspace_id]
                logger.info("Invalidated BM25 index cache for workspace %s", workspace_id)
                return True
            return False

    def clear(self) -> None:
        """Clears all cached workspace indexes."""
        with self._global_lock:
            self._cache.clear()
            logger.info("Cleared entire BM25 index cache")
