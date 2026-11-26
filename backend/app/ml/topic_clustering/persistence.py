"""Topic Persistence Service orchestrating database storage and run activation (Phase 6 C6.6)."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.topic import Topic
from backend.app.models.topic_assignment import TopicAssignment
from backend.app.models.topic_clustering_run import TopicClusteringRun
from backend.app.ml.topic_clustering.dataset import ClusteringDatasetManager
from backend.app.ml.topic_clustering.kmeans import KMeansTopicClusterer
from backend.app.ml.topic_clustering.labeling import ClusterLabelingService
from backend.app.ml.topic_clustering.schemas import (
    ClusterAssignment,
    ClusterStats,
    TopicLabelMetadata,
)
from backend.app.repositories.topic_clustering_repository import TopicClusteringRepository

logger = get_logger("knovera.ml.topic_clustering.persistence")


class TopicPersistenceError(ValueError):
    """Raised when persistence validation or database operations fail."""
    pass


class TopicPersistenceService:
    """Service validating and transactionally persisting clustering runs, topics, and assignments."""

    def __init__(
        self,
        dataset_manager: Optional[ClusteringDatasetManager] = None,
        labeling_service: Optional[ClusterLabelingService] = None,
    ) -> None:
        self.dataset_manager = dataset_manager or ClusteringDatasetManager()
        self.labeling_service = labeling_service or ClusterLabelingService()

    def persist_clustering_results(
        self,
        session: Session,
        workspace_id: uuid.UUID,
        snapshot_dir: Path,
        model_dir: Path,
        created_by_user_id: Optional[uuid.UUID] = None,
        activate: bool = True,
    ) -> TopicClusteringRun:
        """Transactionally persists a completed K-Means topic clustering model and assignments."""
        repo = TopicClusteringRepository(session)

        # 1. Load dataset snapshot
        manifest, records, embeddings = self.dataset_manager.load_snapshot(
            snapshot_dir, validate=True
        )
        if manifest.workspace_id != str(workspace_id):
            raise TopicPersistenceError(
                f"Workspace mismatch: snapshot workspace is {manifest.workspace_id}, but requested is {workspace_id}"
            )

        # 2. Load model artifacts
        model, model_manifest, centroids, stats_map, assignments = (
            KMeansTopicClusterer.load_model(model_dir)
        )
        if model_manifest.snapshot_id != manifest.snapshot_id:
            raise TopicPersistenceError(
                f"Model snapshot mismatch: model was trained on {model_manifest.snapshot_id}, but snapshot is {manifest.snapshot_id}"
            )

        # 3. Check for existing duplicate run to maintain idempotency
        existing_run = session.query(TopicClusteringRun).filter(
            TopicClusteringRun.workspace_id == workspace_id,
            TopicClusteringRun.snapshot_id == manifest.snapshot_id,
            TopicClusteringRun.model_version == model_manifest.model_version,
            TopicClusteringRun.status == "completed",
        ).first()

        if existing_run is not None:
            logger.info(
                "Idempotency: Reusing existing completed TopicClusteringRun %s for model %s",
                existing_run.id,
                model_manifest.model_version,
            )
            if activate and not existing_run.is_active:
                repo.activate_run(existing_run.id, workspace_id)
                session.commit()
            return existing_run

        # 4. Canonical chunk text hydration and validation
        all_chunk_ids = [a.chunk_id for a in assignments]
        chunk_map = self.labeling_service.hydrate_canonical_chunks(
            session=session,
            workspace_id=workspace_id,
            chunk_ids=all_chunk_ids,
        )

        missing_chunks = [cid for cid in all_chunk_ids if cid not in chunk_map]
        if missing_chunks:
            raise TopicPersistenceError(
                f"Validation error: {len(missing_chunks)} assigned chunks missing or deleted from database: {missing_chunks[:3]}"
            )

        # 5. Generate grounded topic labels
        topic_labels = self.labeling_service.label_clusters(
            session=session,
            workspace_id=workspace_id,
            assignments=assignments,
            cluster_stats=stats_map,
        )

        # 6. Database Transaction
        try:
            # Create Run record
            run = repo.create_clustering_run(
                workspace_id=workspace_id,
                snapshot_id=manifest.snapshot_id,
                model_version=model_manifest.model_version,
                embedding_model_id=manifest.embedding_model,
                embedding_dimension=manifest.embedding_dimension,
                k=model_manifest.k,
                corpus_snapshot_hash=manifest.corpus_hash,
                configuration={
                    "random_state": model_manifest.random_state,
                    "n_init": model_manifest.n_init,
                    "max_iter": model_manifest.max_iter,
                    "algorithm": model_manifest.algorithm,
                },
                evaluation_metrics=model_manifest.metrics.model_dump(),
                selection_metadata=model_manifest.metadata,
                model_artifact_path=str(model_dir),
                created_by_user_id=created_by_user_id,
                status="running",
            )

            # Create Topic records
            topic_metas_list = [topic_labels[c] for c in sorted(topic_labels.keys())]
            persisted_topics = repo.create_topics(
                run_id=run.id,
                workspace_id=workspace_id,
                topic_metas=topic_metas_list,
            )
            topic_key_to_id = {t.cluster_key: t.id for t in persisted_topics}

            # Create Assignment records
            now = datetime.now(timezone.utc)
            db_assignments: List[TopicAssignment] = []
            for a in assignments:
                cluster_key = f"cluster_{a.cluster_id}"
                topic_id = topic_key_to_id.get(cluster_key)
                if not topic_id:
                    raise TopicPersistenceError(f"Topic for cluster key {cluster_key} not created")

                chunk = chunk_map[a.chunk_id]
                db_assignments.append(
                    TopicAssignment(
                        id=uuid.uuid4(),
                        workspace_id=workspace_id,
                        clustering_run_id=run.id,
                        topic_id=topic_id,
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        distance_to_centroid=a.distance_to_centroid,
                        is_representative=a.is_representative,
                        assigned_at=now,
                    )
                )

            # Bulk insert assignments
            repo.bulk_insert_assignments(db_assignments)

            # Activate if requested
            if activate:
                repo.activate_run(run.id, workspace_id)
            else:
                run.status = "completed"
                run.completed_at = now

            session.commit()
            logger.info(
                "Successfully persisted TopicClusteringRun %s (%d topics, %d assignments)",
                run.id,
                len(persisted_topics),
                len(db_assignments),
            )
            return run

        except Exception as exc:
            session.rollback()
            logger.error("Failed to persist topic clustering results: %s", exc)
            raise TopicPersistenceError(f"Persistence transaction failed: {exc}") from exc
