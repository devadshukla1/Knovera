"""Schemas and data models for Knovera ML Model Benchmarking (Phase 11 C11.4)."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ModelFamily(str, Enum):
    EMBEDDINGS = "embeddings"
    RERANKER = "reranker"
    INTENT = "intent"
    CLUSTERING = "clustering"
    BKT = "bkt"
    NLI = "nli"


@dataclass
class BenchmarkEnvironment:
    os_name: str
    python_version: str
    cpu_model: str
    cpu_cores: int
    total_ram_gb: float
    gpu_available: bool
    gpu_device: str
    pytorch_version: Optional[str] = None
    sklearn_version: Optional[str] = None
    transformers_version: Optional[str] = None
    sentence_transformers_version: Optional[str] = None


@dataclass
class BenchmarkRunRecord:
    benchmark_id: str
    model_family: str
    model_identifier: str
    model_revision: str
    dataset_name: str
    dataset_version: str
    data_split: str
    sample_count: int
    cold_start_ms: float
    warm_latency_median_ms: float
    warm_latency_p95_ms: float
    throughput_items_per_sec: float
    peak_process_memory_mb: float
    artifact_size_mb: float
    quality_metrics: Dict[str, float]
    status: str = "completed"
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AggregateMLBenchmarkReport:
    report_id: str
    environment: Dict[str, Any]
    total_models_benchmarked: int
    runs: List[Dict[str, Any]]
    family_summaries: Dict[str, Dict[str, Any]]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    execution_duration_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
