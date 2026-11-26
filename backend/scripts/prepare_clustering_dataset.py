"""CLI script to extract workspace document chunks and prepare an unsupervised clustering dataset snapshot."""

import argparse
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.core.logging import get_logger
from backend.app.db.session import SessionLocal
from backend.app.ml.topic_clustering import (
    ChunkEmbeddingService,
    ClusteringDatasetManager,
)

logger = get_logger("knovera.scripts.prepare_clustering_dataset")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a clustering dataset snapshot for a Knovera workspace."
    )
    parser.add_argument(
        "--workspace-id",
        type=str,
        required=True,
        help="UUID string of workspace to cluster.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/topic_clustering/snapshots",
        help="Base directory for snapshot output.",
    )
    parser.add_argument(
        "--snapshot-id",
        type=str,
        default=None,
        help="Optional custom snapshot identifier.",
    )
    parser.add_argument(
        "--no-reuse-chroma",
        action="store_true",
        help="Do not check ChromaDB for existing embeddings.",
    )
    parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="Force recomputation of all embeddings even if present in ChromaDB.",
    )

    args = parser.parse_args()

    try:
        ws_id = uuid.UUID(args.workspace_id)
    except ValueError:
        print(f"Error: Invalid workspace UUID '{args.workspace_id}'", file=sys.stderr)
        return 1

    session = SessionLocal()
    try:
        service = ChunkEmbeddingService()
        print(f"Extracting active chunks from database for workspace {ws_id}...")
        chunks = service.extract_workspace_chunks(session, ws_id)

        if not chunks:
            print(f"No active document chunks found in workspace {ws_id}.", file=sys.stderr)
            return 1

        print(f"Found {len(chunks)} chunks. Generating/validating embeddings...")
        records, embeddings = service.generate_chunk_embeddings(
            chunks=chunks,
            reuse_chroma=not args.no_reuse_chroma,
            force_regenerate=args.force_regenerate,
        )

        manager = ClusteringDatasetManager(base_dir=Path(args.output_dir))
        snapshot_dir = manager.create_snapshot(
            workspace_id=ws_id,
            records=records,
            embeddings=embeddings,
            snapshot_id=args.snapshot_id,
        )

        print("\n=== Clustering Dataset Snapshot Created ===")
        print(f"Snapshot Directory : {snapshot_dir}")
        print(f"Chunk Count        : {len(records)}")
        print(f"Embedding Shape    : {embeddings.shape}")
        print(f"Normalization      : L2 (unit norm)")
        return 0

    except Exception as exc:
        print(f"Error preparing clustering dataset: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
