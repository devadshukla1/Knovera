"""Deterministic Fake Embedding Provider for Unit Testing and Fast CI (Phase 3 C3.1)."""

import hashlib
from typing import List
import numpy as np

from backend.app.rag.embeddings.base import EmbeddingProvider
from backend.app.rag.embeddings.exceptions import EmptyInputError


class DeterministicFakeEmbeddingProvider(EmbeddingProvider):
    """Produces deterministic, L2-normalized dense embeddings without external dependencies.

    Ideal for fast unit tests, offline operation, and automated CI pipelines.
    """

    def __init__(
        self,
        dimension: int = 384,
        model_id: str = "sentence-transformers/all-MiniLM-L6-v2",
        model_revision: str = "mock-deterministic-v1",
        max_sequence_length: int = 256,
    ) -> None:
        self.dimension = dimension
        self.model_id = model_id
        self.model_revision = model_revision
        self.max_seq_length = max_sequence_length

    def get_dimension(self) -> int:
        return self.dimension

    def get_model_id(self) -> str:
        return self.model_id

    def get_model_revision(self) -> str:
        return self.model_revision

    def get_max_sequence_length(self) -> int:
        return self.max_seq_length

    def _generate_vector(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise EmptyInputError()

        # Seed NumPy PRNG deterministically using SHA-256 digest of input text
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self.dimension)

        # L2-normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def encode_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return [self._generate_vector(t) for t in texts]

    def encode_query(self, text: str) -> List[float]:
        return self._generate_vector(text)

    def is_ready(self) -> bool:
        return True
