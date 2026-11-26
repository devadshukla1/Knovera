"""Abstract Base Class for Embedding Providers in Knovera."""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Abstract interface decoupling embedding consumers from concrete ML model backends."""

    @abstractmethod
    def get_dimension(self) -> int:
        """Returns the dense vector dimensionality (e.g. 384 for all-MiniLM-L6-v2)."""
        pass

    @abstractmethod
    def get_model_id(self) -> str:
        """Returns the canonical model identifier."""
        pass

    @abstractmethod
    def get_model_revision(self) -> str:
        """Returns the resolved revision or commit hash of the model."""
        pass

    @abstractmethod
    def get_max_sequence_length(self) -> int:
        """Returns the maximum input token length supported by the model."""
        pass

    @abstractmethod
    def encode_documents(self, texts: List[str]) -> List[List[float]]:
        """Encodes a batch of document chunk texts into dense vectors.

        Guarantees:
            - Preserves input order (vector[i] corresponds to texts[i]).
            - Dimension is strictly validated for every vector.
            - All values are finite (no NaN, inf).
            - Vectors are L2-normalized if configured.
        """
        pass

    @abstractmethod
    def encode_query(self, text: str) -> List[float]:
        """Encodes a single user query into a dense vector using the same model revision."""
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """Returns True if the underlying model is loaded and ready for inference."""
        pass
