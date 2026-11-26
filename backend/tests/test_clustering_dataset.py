"""Unit tests for ClusteringDatasetManager and ClusteringDatasetValidator (Phase 6 C6.2)."""

import uuid
import numpy as np
import pytest
from pathlib import Path

from backend.app.ml.topic_clustering.dataset import (
    ClusteringDatasetManager,
    ClusteringDatasetValidationError,
    ClusteringDatasetValidator,
)
from backend.app.ml.topic_clustering.schemas import ClusteringChunkRecord, DatasetManifest


@pytest.fixture
def sample_dataset():
    ws_id = str(uuid.uuid4())
    records = []
    for i in range(15):
        records.append(
            ClusteringChunkRecord(
                chunk_id=str(uuid.uuid4()),
                document_id=str(uuid.uuid4()),
                workspace_id=ws_id,
                chunk_index=i,
                page_number=1,
                token_count=120,
                content_hash=f"{i:064x}",
                text_preview=f"Sample text for chunk index {i}",
            )
        )
    # Generate random L2-normalized float32 vectors
    rng = np.random.RandomState(42)
    raw = rng.randn(15, 384).astype(np.float32)
    embeddings = raw / np.linalg.norm(raw, axis=1, keepdims=True)
    return ws_id, records, embeddings.astype(np.float32)


def test_validator_success(sample_dataset):
    ws_id, records, embeddings = sample_dataset
    validator = ClusteringDatasetValidator()
    # Should not raise
    validator.validate(records, embeddings, expected_dimension=384)


def test_validator_dimension_mismatch(sample_dataset):
    ws_id, records, embeddings = sample_dataset
    validator = ClusteringDatasetValidator()
    with pytest.raises(ClusteringDatasetValidationError, match="Dimension mismatch"):
        validator.validate(records, embeddings, expected_dimension=768)


def test_validator_row_count_mismatch(sample_dataset):
    ws_id, records, embeddings = sample_dataset
    validator = ClusteringDatasetValidator()
    with pytest.raises(ClusteringDatasetValidationError, match="Row mismatch"):
        validator.validate(records[:-1], embeddings, expected_dimension=384)


def test_validator_duplicate_chunk_ids(sample_dataset):
    ws_id, records, embeddings = sample_dataset
    dup_records = list(records)
    dup_records[1] = dup_records[0]  # duplicate chunk_id
    validator = ClusteringDatasetValidator()
    with pytest.raises(ClusteringDatasetValidationError, match="Duplicate chunk IDs"):
        validator.validate(dup_records, embeddings, expected_dimension=384)


def test_validator_workspace_contamination(sample_dataset):
    ws_id, records, embeddings = sample_dataset
    contaminated = list(records)
    contaminated[2] = ClusteringChunkRecord(
        chunk_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        workspace_id=str(uuid.uuid4()),  # different workspace
        chunk_index=2,
        page_number=1,
        token_count=100,
        content_hash="f" * 64,
        text_preview="Foreign chunk",
    )
    validator = ClusteringDatasetValidator()
    with pytest.raises(ClusteringDatasetValidationError, match="Workspace contamination"):
        validator.validate(contaminated, embeddings, expected_dimension=384)


def test_validator_non_normalized_vectors(sample_dataset):
    ws_id, records, embeddings = sample_dataset
    non_norm = embeddings.copy()
    non_norm[0] = non_norm[0] * 5.0  # norm is 5.0 != 1.0
    validator = ClusteringDatasetValidator()
    with pytest.raises(ClusteringDatasetValidationError, match="not L2 unit-normalized"):
        validator.validate(records, non_norm, expected_dimension=384)


def test_validator_corpus_hash_mismatch(sample_dataset):
    ws_id, records, embeddings = sample_dataset
    validator = ClusteringDatasetValidator()
    manifest = DatasetManifest(
        snapshot_id="snap_test",
        workspace_id=ws_id,
        chunk_count=len(records),
        embedding_model="test-model",
        embedding_dimension=384,
        normalization="l2",
        corpus_hash="tampered_hash_value" + "0" * 45,
    )
    with pytest.raises(ClusteringDatasetValidationError, match="corpus_hash mismatch"):
        validator.validate(records, embeddings, manifest=manifest, expected_dimension=384)


def test_dataset_manager_create_and_load_roundtrip(tmp_path, sample_dataset):
    ws_id, records, embeddings = sample_dataset
    manager = ClusteringDatasetManager(base_dir=tmp_path)

    snapshot_dir = manager.create_snapshot(
        workspace_id=uuid.UUID(ws_id),
        records=records,
        embeddings=embeddings,
        embedding_model="all-MiniLM-L6-v2",
        snapshot_id="snap_roundtrip_test",
    )

    assert (snapshot_dir / "embeddings.npy").exists()
    assert (snapshot_dir / "records.jsonl").exists()
    assert (snapshot_dir / "manifest.json").exists()

    loaded_manifest, loaded_records, loaded_embeddings = manager.load_snapshot(
        snapshot_dir, validate=True
    )

    assert loaded_manifest.snapshot_id == "snap_roundtrip_test"
    assert loaded_manifest.workspace_id == ws_id
    assert loaded_manifest.chunk_count == len(records)
    assert len(loaded_records) == len(records)
    assert loaded_embeddings.shape == embeddings.shape
    assert np.allclose(loaded_embeddings, embeddings)
    assert loaded_records[0].chunk_id == records[0].chunk_id
