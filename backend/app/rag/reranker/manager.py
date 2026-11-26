"""Cross-Encoder model manager and singleton lifecycle provider (Phase 4 C4.4)."""

import os
import threading
from typing import Any, Dict, List, Optional, Protocol, Tuple

from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import get_logger
from backend.app.rag.reranker.exceptions import ModelLoadError

logger = get_logger("knovera.rag.reranker.manager")


class CrossEncoderProtocol(Protocol):
    """Protocol defining the interface expected from a Cross-Encoder model."""

    def predict(
        self,
        sentences: List[List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        **kwargs: Any,
    ) -> Any:
        ...


class CrossEncoderModelManager:
    """Thread-safe singleton managing Cross-Encoder model lifecycle and device placement."""

    _instance: Optional["CrossEncoderModelManager"] = None
    _lock = threading.Lock()

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._model: Optional[CrossEncoderProtocol] = None
        self._model_lock = threading.Lock()
        self._resolved_device: Optional[str] = None

    @classmethod
    def get_instance(cls, settings: Optional[Settings] = None) -> "CrossEncoderModelManager":
        """Returns process-wide singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(settings=settings)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Resets the singleton instance (primarily for test isolation)."""
        with cls._lock:
            if cls._instance is not None:
                with cls._instance._model_lock:
                    cls._instance._model = None
            cls._instance = None

    def resolve_device(self) -> str:
        """Determines target hardware device based on configuration and availability."""
        if self._resolved_device is not None:
            return self._resolved_device

        configured = (self.settings.CROSS_ENCODER_DEVICE or "cpu").lower().strip()
        if configured == "auto":
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        elif configured in ("cuda", "gpu"):
            try:
                import torch

                if torch.cuda.is_available():
                    device = "cuda"
                else:
                    logger.warning("CUDA requested for Cross-Encoder but unavailable; falling back to CPU")
                    device = "cpu"
            except ImportError:
                device = "cpu"
        else:
            device = "cpu"

        self._resolved_device = device
        return device

    def get_model(self) -> CrossEncoderProtocol:
        """Retrieves or lazily initializes the configured CrossEncoder model singleton."""
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    model_id = self.settings.CROSS_ENCODER_MODEL_ID
                    device = self.resolve_device()
                    max_length = self.settings.CROSS_ENCODER_MAX_LENGTH
                    logger.info(
                        "Initializing CrossEncoder singleton '%s' on %s (max_length=%d)",
                        model_id,
                        device,
                        max_length,
                    )
                    try:
                        from sentence_transformers import CrossEncoder

                        self._model = CrossEncoder(
                            model_name=model_id,
                            max_length=max_length,
                            device=device,
                        )
                    except Exception as exc:
                        logger.error("Failed to load CrossEncoder model '%s': %s", model_id, exc)
                        raise ModelLoadError(
                            f"Failed to load Cross-Encoder model '{model_id}': {exc}"
                        ) from exc
        return self._model

    def set_model(self, model: Optional[CrossEncoderProtocol]) -> None:
        """Explicitly sets or overrides the model instance (used for mocks and testing)."""
        with self._model_lock:
            self._model = model

    def check_readiness(self) -> Tuple[bool, Dict[str, Any]]:
        """Verifies model loading state and hardware configuration for health checks."""
        try:
            device = self.resolve_device()
            model = self.get_model()
            return True, {
                "ready": True,
                "model_id": self.settings.CROSS_ENCODER_MODEL_ID,
                "device": device,
                "max_length": self.settings.CROSS_ENCODER_MAX_LENGTH,
                "batch_size": self.settings.CROSS_ENCODER_BATCH_SIZE,
                "model_class": model.__class__.__name__,
            }
        except Exception as exc:
            logger.warning("Cross-Encoder readiness check failed: %s", exc)
            return False, {
                "ready": False,
                "error": str(exc),
                "model_id": self.settings.CROSS_ENCODER_MODEL_ID,
            }
