"""Model Artifact Serialization and Manifest Management for Query Intent (Phase 5 C5.5 / C5.6).

Safely serializes and deserializes fitted scikit-learn pipelines with SHA256 checksums,
environment metadata, and taxonomy version checks.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Tuple
import joblib
import sklearn

from backend.app.ml.query_intent.preprocessing import PREPROCESSING_VERSION
from backend.app.ml.query_intent.taxonomy import TAXONOMY_VERSION, TaxonomyRegistry

DEFAULT_MODELS_ROOT: Path = Path("models/query_intent")


def compute_file_sha256(filepath: Path) -> str:
    """Computes SHA256 hex digest of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def save_model_artifact(
    pipeline: Any,
    model_id: str,
    model_type: str,
    hyperparameters: Dict[str, Any],
    metrics: Dict[str, Any],
    artifact_dir: Path,
    feature_stats: Optional[Dict[str, Any]] = None,
    dataset_version: str = "1.0.0",
) -> Path:
    """Serializes a fitted model pipeline and generates an artifact manifest.json.

    Args:
        pipeline: Fitted scikit-learn Pipeline (including vectorizers and classifier).
        model_id: Stable identifier string (e.g. "logistic_regression_baseline").
        model_type: "logistic_regression" or "linear_svm".
        hyperparameters: Dictionary of training hyperparameters.
        metrics: Dictionary of evaluation metrics.
        artifact_dir: Target directory path where model.joblib and manifest.json will be saved.
        feature_stats: Dictionary of vocabulary and sparsity stats.
        dataset_version: Dataset semantic version.

    Returns:
        Path to the saved model.joblib file.
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "model.joblib"
    manifest_path = artifact_dir / "manifest.json"

    # 1. Serialize complete pipeline
    joblib.dump(pipeline, model_path, compress=3)

    # 2. Compute checksum
    checksum = compute_file_sha256(model_path)
    file_size_bytes = model_path.stat().st_size

    # 3. Assemble manifest
    manifest: Dict[str, Any] = {
        "model_id": model_id,
        "model_type": model_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "taxonomy_version": TAXONOMY_VERSION,
        "preprocessing_version": PREPROCESSING_VERSION,
        "dataset_version": dataset_version,
        "python_version": sys.version.split()[0],
        "sklearn_version": sklearn.__version__,
        "classes": sorted(TaxonomyRegistry.list_category_ids()),
        "hyperparameters": hyperparameters,
        "feature_stats": feature_stats or {},
        "metrics": metrics,
        "artifact": {
            "file_name": "model.joblib",
            "sha256": checksum,
            "size_bytes": file_size_bytes,
            "size_kb": round(file_size_bytes / 1024.0, 2),
        },
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return model_path


def load_model_artifact(artifact_dir: Path) -> Tuple[Any, Dict[str, Any]]:
    """Loads a serialized pipeline and verifies its manifest and taxonomy version.

    Args:
        artifact_dir: Directory containing model.joblib and manifest.json.

    Returns:
        Tuple of (fitted_pipeline, manifest_dict).

    Raises:
        FileNotFoundError: If model or manifest file is missing.
        ValueError: If manifest taxonomy version is incompatible or checksum mismatch occurs.
    """
    model_path = artifact_dir / "model.joblib"
    manifest_path = artifact_dir / "manifest.json"

    if not model_path.exists():
        raise FileNotFoundError(f"Model artifact not found at {model_path}")
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Validate taxonomy version compatibility
    tax_ver = manifest.get("taxonomy_version")
    if tax_ver != TAXONOMY_VERSION:
        raise ValueError(
            f"Taxonomy version mismatch: artifact requires '{tax_ver}', "
            f"current system is '{TAXONOMY_VERSION}'."
        )

    # Verify integrity checksum
    expected_checksum = manifest.get("artifact", {}).get("sha256")
    if expected_checksum:
        actual_checksum = compute_file_sha256(model_path)
        if actual_checksum != expected_checksum:
            raise ValueError(
                f"Artifact checksum verification failed for {model_path}. "
                f"Expected {expected_checksum}, got {actual_checksum}."
            )

    pipeline = joblib.load(model_path)
    return pipeline, manifest
