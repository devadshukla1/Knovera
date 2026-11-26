"""Clustering Dataset Management and Validation for Knovera (Phase 6 C6.2).

Responsible for:
1. Creating deterministic, reproducible unsupervised dataset snapshots.
2. Saving and loading binary embeddings (embeddings.npy), structured records (records.jsonl),
   and cryptographic manifests (manifest.json).
3. Rigorous validation of dataset integrity, row alignment, non-leakage, and normalization.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid
import numpy as np

from backend.app.core.logging import get_logger
from backend.app.ml.topic_clustering.schemas import ClusteringChunkRecord, DatasetManifest

logger = get_logger("knovera.ml.topic_clustering.dataset")


class ClusteringDatasetValidationError(ValueError):
    """Raised when clustering dataset integrity checks fail."""
    pass


class ClusteringDatasetValidator:
    """Validator enforcing dataset structural alignment, normalization, and integrity."""

    @staticmethod
    def compute_corpus_hash(records: List[ClusteringChunkRecord]) -> str:
        """Computes deterministic SHA-256 hash across sorted chunk content hashes."""
        sorted_hashes = sorted(r.content_hash for r in records)
        hasher = hashlib.sha256()
        for ch in sorted_hashes:
            hasher.update(ch.encode("utf-8"))
        return hasher.hexdigest()

    def validate(
        self,
        records: List[ClusteringChunkRecord],
        embeddings: np.ndarray,
        manifest: Optional[DatasetManifest] = None,
        expected_dimension: int = 384,
    ) -> None:
        """Validates alignment, shapes, values, normalization, and manifest consistency."""
        num_records = len(records)
        if embeddings.ndim != 2:
            raise ClusteringDatasetValidationError(
                f"Embedding array must be 2-dimensional, got {embeddings.ndim}D with shape {embeddings.shape}"
            )

        if embeddings.shape[0] != num_records:
            raise ClusteringDatasetValidationError(
                f"Row mismatch: records count ({num_records}) != embedding rows ({embeddings.shape[0]})"
            )

        if embeddings.shape[1] != expected_dimension:
            raise ClusteringDatasetValidationError(
                f"Dimension mismatch: expected {expected_dimension}, got {embeddings.shape[1]}"
            )

        # Unique chunk IDs check
        chunk_ids = [r.chunk_id for r in records]
        if len(set(chunk_ids)) != num_records:
            raise ClusteringDatasetValidationError(
                f"Duplicate chunk IDs found in records ({len(chunk_ids)} total vs {len(set(chunk_ids))} unique)"
            )

        if num_records > 0:
            # Workspace isolation check: every record must belong to the exact same workspace
            target_workspace = records[0].workspace_id
            for r in records:
                if r.workspace_id != target_workspace:
                    raise ClusteringDatasetValidationError(
                        f"Workspace contamination: record {r.chunk_id} belongs to {r.workspace_id}, expected {target_workspace}"
                    )

            # Check finiteness
            if not np.all(np.isfinite(embeddings)):
                raise ClusteringDatasetValidationError(
                    "Embeddings contain NaN or infinite values"
                )

            # Check L2 normalization: norms must be 1.0 +/- 1e-3
            norms = np.linalg.norm(embeddings, axis=1)
            if not np.allclose(norms, 1.0, atol=1e-3):
                raise ClusteringDatasetValidationError(
                    f"Embeddings are not L2 unit-normalized (norm range: [{np.min(norms):.4f}, {np.max(norms):.4f}])"
                )

        # Manifest checks if provided
        if manifest is not None:
            if manifest.chunk_count != num_records:
                raise ClusteringDatasetValidationError(
                    f"Manifest chunk_count ({manifest.chunk_count}) != actual records ({num_records})"
                )
            if manifest.embedding_dimension != embeddings.shape[1]:
                raise ClusteringDatasetValidationError(
                    f"Manifest dimension ({manifest.embedding_dimension}) != embedding dim ({embeddings.shape[1]})"
                )
            if num_records > 0 and manifest.workspace_id != records[0].workspace_id:
                raise ClusteringDatasetValidationError(
                    f"Manifest workspace_id ({manifest.workspace_id}) != records workspace ({records[0].workspace_id})"
                )
            recomputed_hash = self.compute_corpus_hash(records)
            if manifest.corpus_hash != recomputed_hash:
                raise ClusteringDatasetValidationError(
                    f"Manifest corpus_hash mismatch: expected {manifest.corpus_hash}, recomputed {recomputed_hash}"
                )


class ClusteringDatasetManager:
    """Manager for creating, storing, loading, and listing clustering dataset snapshots."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or Path("data/topic_clustering/snapshots")
        self.validator = ClusteringDatasetValidator()

    def generate_snapshot_id(self, workspace_id: uuid.UUID) -> str:
        """Generates a structured timestamped snapshot identifier."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        short_ws = str(workspace_id).replace("-", "")[:8]
        return f"snap_{short_ws}_{ts}"

    def create_snapshot(
        self,
        workspace_id: uuid.UUID,
        records: List[ClusteringChunkRecord],
        embeddings: np.ndarray,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        snapshot_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Serializes records, embeddings, and manifest to disk in structured snapshot directory."""
        if snapshot_id is None:
            snapshot_id = self.generate_snapshot_id(workspace_id)

        dim = embeddings.shape[1] if embeddings.ndim == 2 and embeddings.shape[0] > 0 else 384
        corpus_hash = self.validator.compute_corpus_hash(records)

        manifest = DatasetManifest(
            snapshot_id=snapshot_id,
            workspace_id=str(workspace_id),
            chunk_count=len(records),
            embedding_model=embedding_model,
            embedding_dimension=dim,
            normalization="l2",
            corpus_hash=corpus_hash,
            metadata=metadata or {},
        )

        # Validate before writing
        self.validator.validate(records, embeddings, manifest=manifest, expected_dimension=dim)

        snapshot_dir = self.base_dir / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # 1. Save embeddings.npy
        embeddings_path = snapshot_dir / "embeddings.npy"
        np.save(embeddings_path, embeddings.astype(np.float32))

        # 2. Save records.jsonl
        records_path = snapshot_dir / "records.jsonl"
        with open(records_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(r.model_dump_json() + "\n")

        # 3. Save manifest.json
        manifest_path = snapshot_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(indent=2) + "\n")

        logger.info(
            "Created clustering dataset snapshot '%s' with %d chunks at %s",
            snapshot_id,
            len(records),
            snapshot_dir,
        )
        return snapshot_dir

    def load_snapshot(
        self,
        snapshot_dir: Path,
        validate: bool = True,
    ) -> Tuple[DatasetManifest, List[ClusteringChunkRecord], np.ndarray]:
        """Loads and parses a clustering dataset snapshot from disk."""
        snapshot_dir = Path(snapshot_dir)
        manifest_path = snapshot_dir / "manifest.json"
        records_path = snapshot_dir / "records.jsonl"
        embeddings_path = snapshot_dir / "embeddings.npy"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing manifest.json in {snapshot_dir}")
        if not records_path.exists():
            raise FileNotFoundError(f"Missing records.jsonl in {snapshot_dir}")
        if not embeddings_path.exists():
            raise FileNotFoundError(f"Missing embeddings.npy in {snapshot_dir}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        manifest = DatasetManifest(**manifest_data)

        records: List[ClusteringChunkRecord] = []
        with open(records_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    records.append(ClusteringChunkRecord(**json.loads(line_str)))

        embeddings = np.load(embeddings_path)

        if validate:
            self.validator.validate(
                records=records,
                embeddings=embeddings,
                manifest=manifest,
                expected_dimension=manifest.embedding_dimension,
            )

        logger.info(
            "Loaded clustering snapshot '%s' (%d chunks, shape %s)",
            manifest.snapshot_id,
            len(records),
            embeddings.shape,
        )
        return manifest, records, embeddings
