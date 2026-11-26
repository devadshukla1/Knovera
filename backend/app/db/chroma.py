"""ChromaDB vector store HTTP client wrapper and health checks.

Provides resilient, lazy initialization of chromadb.HttpClient with exception shielding
to ensure the application starts even when ChromaDB is offline.
"""

import time
from typing import Any, Optional, Tuple
import chromadb

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger

logger = get_logger("knovera.chroma")
settings = get_settings()

_chroma_client: Optional[Any] = None


def set_chroma_client(client: Optional[Any]) -> None:
    """Sets or resets the cached Chroma client (useful for testing)."""
    global _chroma_client
    _chroma_client = client


def get_chroma_client() -> Optional[Any]:
    """Returns lazily-initialized ChromaDB HttpClient instance.

    Catches connection exceptions (e.g. ValueError, ConnectError) if ChromaDB
    server is unreachable and returns None instead of crashing.
    """
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    if settings.CHROMA_HOST == "in-memory":
        from backend.app.rag.vector_store.fake_client import InMemoryChromaClient
        _chroma_client = InMemoryChromaClient()
        return _chroma_client

    try:
        # chromadb.HttpClient attempts an eager connection check during init
        client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
        )
        _chroma_client = client
        return _chroma_client
    except Exception as exc:
        logger.warning(
            "Failed to initialize ChromaDB client at %s:%s: %s",
            settings.CHROMA_HOST,
            settings.CHROMA_PORT,
            type(exc).__name__,
        )
        return None


def check_chroma_connectivity() -> Tuple[bool, Optional[float], Optional[str]]:
    """Checks ChromaDB connectivity by querying the server heartbeat.

    Returns:
        Tuple of (is_connected, latency_ms, error_message).
        When connected: (True, latency_ms, None)
        When disconnected: (False, None, "Vector store service unavailable")
    """
    global _chroma_client
    start_time = time.perf_counter()

    try:
        client = get_chroma_client()
        if client is None:
            return False, None, "Vector store service unavailable"

        heartbeat = client.heartbeat()
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if isinstance(heartbeat, (int, float)) and heartbeat > 0:
            return True, round(latency_ms, 2), None
        return False, None, "Vector store service unavailable"
    except Exception as exc:
        # Reset cached client on error so subsequent requests attempt fresh connection
        _chroma_client = None
        logger.warning("ChromaDB connectivity check failed: %s", type(exc).__name__)
        return False, None, "Vector store service unavailable"
