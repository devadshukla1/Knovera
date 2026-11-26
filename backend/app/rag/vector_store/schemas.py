"""Schemas and data models for Knovera Vector Store and ChromaDB (Phase 3 C3.2)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class VectorRecord(BaseModel):
    """Normalized vector record prepared for ChromaDB upsert."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Stable chunk UUID string matching PostgreSQL document_chunks.id")
    embedding: List[float] = Field(..., description="Dense vector embedding")
    metadata: Dict[str, Any] = Field(..., description="Flat scalar metadata filters (workspace_id, doc_id, etc.)")
    document_text: Optional[str] = Field(None, description="Optional raw chunk snippet for inspection")


class CollectionInfo(BaseModel):
    """Metadata describing a ChromaDB collection configuration."""

    model_config = ConfigDict(frozen=True)

    name: str
    dimension: int
    distance_metric: str
    model_id: str
    model_revision: str
    count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReconciliationReport(BaseModel):
    """Diagnostic report comparing PostgreSQL authoritative chunks against ChromaDB vector index."""

    workspace_id: uuid.UUID
    collection_name: str
    total_pg_chunks: int = 0
    total_chroma_vectors: int = 0
    missing_vector_chunk_ids: List[str] = Field(default_factory=list)
    orphan_chroma_ids: List[str] = Field(default_factory=list)
    is_synchronized: bool = False
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
