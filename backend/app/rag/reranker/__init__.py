"""Cross-Encoder reranking package for Knovera retrieval pipeline (Phase 4 C4.4–C4.5)."""

from backend.app.rag.reranker.exceptions import (
    InferenceError,
    InvalidScoreError,
    ModelLoadError,
    RerankerError,
)
from backend.app.rag.reranker.fake_reranker import FakeCrossEncoder
from backend.app.rag.reranker.manager import (
    CrossEncoderModelManager,
    CrossEncoderProtocol,
)
from backend.app.rag.reranker.reranker import (
    CrossEncoderReranker,
    format_query_passage_pair,
)

__all__ = [
    "CrossEncoderModelManager",
    "CrossEncoderProtocol",
    "CrossEncoderReranker",
    "FakeCrossEncoder",
    "RerankerError",
    "ModelLoadError",
    "InferenceError",
    "InvalidScoreError",
    "format_query_passage_pair",
]
