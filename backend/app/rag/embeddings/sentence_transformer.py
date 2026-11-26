"""Sentence Transformers embedding provider for Knovera RAG (Phase 3 C3.1)."""

import os
from typing import List, Optional
import numpy as np

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.rag.embeddings.base import EmbeddingProvider
from backend.app.rag.embeddings.exceptions import (
    DimensionMismatchError,
    EmptyInputError,
    ModelLoadError,
)

logger = get_logger("knovera.rag.embeddings")


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Local, open-source Sentence Transformers embedding model provider."""

    def __init__(
        self,
        model_id: Optional[str] = None,
        model_revision: Optional[str] = None,
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
        batch_size: Optional[int] = None,
        normalize: Optional[bool] = None,
        max_sequence_length: Optional[int] = None,
    ) -> None:
        self.settings = get_settings()
        self.model_id = model_id or self.settings.EMBEDDING_MODEL_ID
        self.model_revision = model_revision or self.settings.EMBEDDING_MODEL_REVISION
        self.device = device or self.settings.EMBEDDING_DEVICE
        self.cache_dir = cache_dir or self.settings.EMBEDDING_CACHE_DIR
        self.batch_size = batch_size or self.settings.EMBEDDING_BATCH_SIZE
        self.normalize = normalize if normalize is not None else self.settings.EMBEDDING_NORMALIZE
        self.configured_max_seq = max_sequence_length or self.settings.EMBEDDING_MAX_SEQUENCE_LENGTH

        self._model = None
        self._dimension = None
        self._actual_max_seq = None

        self._load_model()

    def _load_model(self) -> None:
        """Loads the SentenceTransformer model into memory."""
        try:
            from sentence_transformers import SentenceTransformer

            # Ensure cache dir exists
            os.makedirs(self.cache_dir, exist_ok=True)

            logger.info(
                "Loading SentenceTransformer '%s' (revision=%s, device=%s)",
                self.model_id,
                self.model_revision,
                self.device,
            )
            # Load with pinned revision and local cache directory
            self._model = SentenceTransformer(
                model_name_or_path=self.model_id,
                revision=self.model_revision,
                device=self.device,
                cache_folder=self.cache_dir,
            )

            # Read embedding dimension dynamically from model
            self._dimension = int(self._model.get_sentence_embedding_dimension())

            # Read max sequence length supported by tokenizer
            if hasattr(self._model, "max_seq_length"):
                self._actual_max_seq = int(self._model.max_seq_length)
                # Cap to configured if lower
                if self.configured_max_seq:
                    self._model.max_seq_length = min(self.configured_max_seq, self._actual_max_seq)
            else:
                self._actual_max_seq = self.configured_max_seq or 256

            logger.info(
                "Loaded embedding model '%s': dimension=%d, max_seq_length=%d",
                self.model_id,
                self._dimension,
                self._model.max_seq_length if hasattr(self._model, "max_seq_length") else self._actual_max_seq,
            )

        except Exception as exc:
            logger.exception("Failed to load SentenceTransformer model '%s': %s", self.model_id, exc)
            raise ModelLoadError(
                f"Failed to load embedding model '{self.model_id}': {exc}"
            ) from exc

    def get_dimension(self) -> int:
        if self._dimension is None:
            raise ModelLoadError("Embedding model is not loaded.")
        return self._dimension

    def get_model_id(self) -> str:
        return self.model_id

    def get_model_revision(self) -> str:
        return self.model_revision

    def get_max_sequence_length(self) -> int:
        return self._actual_max_seq or 256

    def encode_documents(self, texts: List[str]) -> List[List[float]]:
        """Encodes a list of document chunk texts into dense vectors."""
        if not texts:
            return []

        # Validate non-empty
        cleaned_texts: List[str] = []
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise EmptyInputError(f"Document text at index {i} is empty.")
            cleaned_texts.append(text)

        embeddings_np = self._model.encode(
            sentences=cleaned_texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            normalize_embeddings=self.normalize,
            convert_to_numpy=True,
        )

        # Validate finite values
        if not np.all(np.isfinite(embeddings_np)):
            raise DimensionMismatchError("Generated embeddings contain NaN or infinite values.")

        # Validate dimensions
        expected_dim = self.get_dimension()
        if embeddings_np.shape[1] != expected_dim:
            raise DimensionMismatchError(
                f"Embedding dimension mismatch: expected {expected_dim}, got {embeddings_np.shape[1]}"
            )

        return embeddings_np.tolist()

    def encode_query(self, text: str) -> List[float]:
        """Encodes a single user query into a dense vector."""
        if not text or not text.strip():
            raise EmptyInputError("Search query cannot be empty.")

        query_embedding_np = self._model.encode(
            sentences=text,
            show_progress_bar=False,
            normalize_embeddings=self.normalize,
            convert_to_numpy=True,
        )

        if not np.all(np.isfinite(query_embedding_np)):
            raise DimensionMismatchError("Generated query embedding contains NaN or infinite values.")

        expected_dim = self.get_dimension()
        if len(query_embedding_np) != expected_dim:
            raise DimensionMismatchError(
                f"Query embedding dimension mismatch: expected {expected_dim}, got {len(query_embedding_np)}"
            )

        return query_embedding_np.tolist()

    def is_ready(self) -> bool:
        return self._model is not None and self._dimension is not None
