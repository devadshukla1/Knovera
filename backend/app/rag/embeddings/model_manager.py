"""Embedding model manager and singleton lifecycle provider for Knovera (Phase 3 C3.1)."""

import threading
from typing import Any, Dict, Optional, Tuple

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.rag.embeddings.base import EmbeddingProvider
from backend.app.rag.embeddings.fake_provider import DeterministicFakeEmbeddingProvider
from backend.app.rag.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingProvider,
)

logger = get_logger("knovera.rag.embeddings.manager")


class EmbeddingModelManager:
    """Thread-safe manager providing single-instance embedding model lifecycle."""

    _instance: Optional["EmbeddingModelManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.settings = get_settings()
        self._provider: Optional[EmbeddingProvider] = None
        self._provider_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "EmbeddingModelManager":
        """Returns process-wide singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_provider(self) -> EmbeddingProvider:
        """Retrieves or lazily initializes the configured embedding provider."""
        if self._provider is None:
            with self._provider_lock:
                if self._provider is None:
                    provider_type = self.settings.EMBEDDING_PROVIDER.lower()
                    if provider_type in ("sentence_transformers", "sentence-transformers"):
                        logger.info("Initializing SentenceTransformerEmbeddingProvider singleton")
                        self._provider = SentenceTransformerEmbeddingProvider()
                    elif provider_type in ("deterministic_fake", "fake", "mock", "test"):
                        logger.info("Initializing DeterministicFakeEmbeddingProvider for testing/offline")
                        self._provider = DeterministicFakeEmbeddingProvider()
                    else:
                        raise ValueError(f"Unsupported EMBEDDING_PROVIDER '{provider_type}'")
        return self._provider

    def set_provider(self, provider: Optional[EmbeddingProvider]) -> None:
        """Explicitly sets or resets the provider (used in testing)."""
        with self._provider_lock:
            self._provider = provider

    def check_readiness(self) -> Tuple[bool, Dict[str, Any]]:
        """Verifies model loading state and readiness for health checks."""
        try:
            provider = self.get_provider()
            is_ready = provider.is_ready()
            return is_ready, {
                "ready": is_ready,
                "provider": provider.__class__.__name__,
                "model_id": provider.get_model_id(),
                "model_revision": provider.get_model_revision(),
                "dimension": provider.get_dimension(),
                "max_sequence_length": provider.get_max_sequence_length(),
            }
        except Exception as exc:
            logger.warning("Embedding model readiness check failed: %s", exc)
            return False, {
                "ready": False,
                "error": str(exc),
            }
