"""Data models and schemas for Knovera Embedding Services (Phase 3 C3.1)."""

from datetime import datetime, timezone
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class EmbeddingMetadata(BaseModel):
    """Metadata describing an embedding model configuration and versioning."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model_id: str
    model_revision: str
    dimension: int = Field(..., gt=0)
    normalize: bool = True
    max_sequence_length: int = Field(default=256, gt=0)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EmbeddingBatchResult(BaseModel):
    """Results and telemetry of an embedding generation execution."""

    model_config = ConfigDict(frozen=True)

    vectors: List[List[float]]
    count: int = Field(..., ge=0)
    dimension: int = Field(..., gt=0)
    model_id: str
    model_revision: str
    duration_ms: float = Field(..., ge=0)
