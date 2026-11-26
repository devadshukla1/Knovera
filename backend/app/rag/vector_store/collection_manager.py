"""ChromaDB collection management and deterministic naming (Phase 3 C3.2)."""

import re
from typing import Any, Dict, Optional
import chromadb

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.rag.vector_store.exceptions import (
    ChromaUnavailableError,
    CollectionDimensionMismatchError,
)
from backend.app.rag.vector_store.schemas import CollectionInfo

logger = get_logger("knovera.rag.vector_store.collections")


def sanitize_collection_name(raw_name: str) -> str:
    """Sanitizes model names into compliant Chroma collection names ([a-zA-Z0-9_-], 3-63 chars)."""
    # Replace non-alphanumeric chars with underscore
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_-")
    if len(cleaned) < 3:
        cleaned = f"col_{cleaned}"
    if len(cleaned) > 63:
        cleaned = cleaned[:63].rstrip("_-")
    return cleaned


class ChromaCollectionManager:
    """Manages version-specific Chroma collections and metadata integrity."""

    def __init__(self, chroma_client: Any) -> None:
        self.client = chroma_client
        self.settings = get_settings()

    def generate_collection_name(
        self,
        model_id: str,
        model_revision: str,
        dimension: int,
    ) -> str:
        """Deterministically generates version-specific collection name."""
        prefix = self.settings.CHROMA_COLLECTION_PREFIX
        # Extract short model tag, e.g. 'all-MiniLM-L6-v2' -> 'all_minilm_l6_v2'
        model_part = model_id.split("/")[-1]
        raw_name = f"{prefix}_{model_part}_{dimension}"
        return sanitize_collection_name(raw_name)

    def get_or_create_collection(
        self,
        model_id: str,
        model_revision: str,
        dimension: int,
        distance_metric: Optional[str] = None,
    ) -> Any:
        """Retrieves or creates a version-specific Chroma collection with cosine distance."""
        if self.client is None:
            raise ChromaUnavailableError()

        collection_name = self.generate_collection_name(
            model_id=model_id,
            model_revision=model_revision,
            dimension=dimension,
        )
        metric = distance_metric or self.settings.CHROMA_DISTANCE_METRIC

        metadata: Dict[str, Any] = {
            "hnsw:space": metric,
            "embedding_dimension": dimension,
            "embedding_model": model_id,
            "embedding_revision": model_revision,
            "project": "knovera",
        }

        try:
            collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata=metadata,
            )
            # Verify dimension if collection already existed
            coll_meta = collection.metadata or {}
            existing_dim = coll_meta.get("embedding_dimension")
            if existing_dim is not None and int(existing_dim) != dimension:
                raise CollectionDimensionMismatchError(expected=dimension, actual=int(existing_dim))

            logger.info("Retrieved or created Chroma collection '%s' (metric=%s)", collection_name, metric)
            return collection

        except Exception as exc:
            if isinstance(exc, CollectionDimensionMismatchError):
                raise
            logger.exception("Failed to get/create Chroma collection '%s': %s", collection_name, exc)
            raise ChromaUnavailableError(f"Error accessing collection '{collection_name}': {exc}") from exc

    def get_collection_info(self, collection: Any) -> CollectionInfo:
        """Extracts structured metadata and record count for a collection."""
        metadata = collection.metadata or {}
        return CollectionInfo(
            name=collection.name,
            dimension=int(metadata.get("embedding_dimension", 384)),
            distance_metric=str(metadata.get("hnsw:space", "cosine")),
            model_id=str(metadata.get("embedding_model", "unknown")),
            model_revision=str(metadata.get("embedding_revision", "unknown")),
            count=collection.count(),
        )
