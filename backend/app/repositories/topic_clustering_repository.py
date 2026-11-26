"""Topic Clustering Repository for PostgreSQL persistence and queries (Phase 6 C6.6)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import String, asc, cast, desc, func, select, update
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.topic import Topic
from backend.app.models.topic_assignment import TopicAssignment
from backend.app.models.topic_clustering_run import TopicClusteringRun

if TYPE_CHECKING:
    from backend.app.ml.topic_clustering.schemas import TopicLabelMetadata

logger = get_logger("knovera.repositories.topic_clustering")


class TopicClusteringRepository:
    """Handles database transactions, queries, and active run lifecycle for Topic Discovery."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_clustering_run(
        self,
        workspace_id: uuid.UUID,
        snapshot_id: str,
        model_version: str,
        embedding_model_id: str,
        embedding_dimension: int,
        k: int,
        corpus_snapshot_hash: str,
        configuration: Optional[Dict[str, Any]] = None,
        evaluation_metrics: Optional[Dict[str, Any]] = None,
        selection_metadata: Optional[Dict[str, Any]] = None,
        model_artifact_path: Optional[str] = None,
        created_by_user_id: Optional[uuid.UUID] = None,
        status: str = "running",
    ) -> TopicClusteringRun:
        """Creates a new TopicClusteringRun record."""
        now = datetime.now(timezone.utc)
        run = TopicClusteringRun(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            snapshot_id=snapshot_id,
            status=status,
            algorithm="kmeans",
            model_version=model_version,
            embedding_model_id=embedding_model_id,
            embedding_dimension=embedding_dimension,
            k=k,
            configuration=configuration or {},
            evaluation_metrics=evaluation_metrics or {},
            selection_metadata=selection_metadata or {},
            model_artifact_path=model_artifact_path,
            corpus_snapshot_hash=corpus_snapshot_hash,
            created_by_user_id=created_by_user_id,
            created_at=now,
            started_at=now,
            is_active=False,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def get_clustering_run(
        self,
        run_id: uuid.UUID,
        workspace_id: Optional[uuid.UUID] = None,
    ) -> Optional[TopicClusteringRun]:
        """Fetches a clustering run by ID, enforcing workspace scope if provided."""
        stmt = select(TopicClusteringRun).where(TopicClusteringRun.id == run_id)
        if workspace_id is not None:
            stmt = stmt.where(TopicClusteringRun.workspace_id == workspace_id)
        return self.session.execute(stmt).scalars().first()

    def get_active_run(self, workspace_id: uuid.UUID) -> Optional[TopicClusteringRun]:
        """Retrieves the currently active completed clustering run for a workspace."""
        stmt = (
            select(TopicClusteringRun)
            .where(
                TopicClusteringRun.workspace_id == workspace_id,
                TopicClusteringRun.is_active == True,  # noqa: E712
                TopicClusteringRun.status == "completed",
            )
            .order_by(desc(TopicClusteringRun.completed_at))
        )
        return self.session.execute(stmt).scalars().first()

    def list_runs(
        self,
        workspace_id: uuid.UUID,
        limit: int = 50,
    ) -> List[TopicClusteringRun]:
        """Lists historical clustering runs for a workspace ordered by created_at descending."""
        stmt = (
            select(TopicClusteringRun)
            .where(TopicClusteringRun.workspace_id == workspace_id)
            .order_by(desc(TopicClusteringRun.created_at))
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def create_topics(
        self,
        run_id: uuid.UUID,
        workspace_id: uuid.UUID,
        topic_metas: List[TopicLabelMetadata],
    ) -> List[Topic]:
        """Persists topics associated with a clustering run."""
        topics: List[Topic] = []
        for tm in topic_metas:
            t = Topic(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                clustering_run_id=run_id,
                cluster_key=tm.cluster_key,
                label=tm.label,
                description=tm.description,
                label_source=tm.label_source,
                label_status=tm.label_status,
                keywords=[kw.model_dump() for kw in tm.keywords],
                representative_chunk_ids=tm.representative_chunk_ids,
                cluster_statistics=tm.cluster_statistics,
            )
            topics.append(t)
            self.session.add(t)

        self.session.flush()
        return topics

    def bulk_insert_assignments(
        self,
        assignments: List[TopicAssignment],
    ) -> int:
        """Bulk inserts topic assignments in the current transaction."""
        if not assignments:
            return 0
        self.session.add_all(assignments)
        self.session.flush()
        return len(assignments)

    def activate_run(
        self,
        run_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> None:
        """Transactionally deactivates old active runs and marks this run as active and completed."""
        now = datetime.now(timezone.utc)
        # Deactivate any currently active run in this workspace
        deactivate_stmt = (
            update(TopicClusteringRun)
            .where(
                TopicClusteringRun.workspace_id == workspace_id,
                TopicClusteringRun.is_active == True,  # noqa: E712
            )
            .values(is_active=False)
        )
        self.session.execute(deactivate_stmt)

        # Activate target run
        activate_stmt = (
            update(TopicClusteringRun)
            .where(
                TopicClusteringRun.id == run_id,
                TopicClusteringRun.workspace_id == workspace_id,
            )
            .values(
                is_active=True,
                status="completed",
                completed_at=now,
            )
        )
        self.session.execute(activate_stmt)
        self.session.flush()
        logger.info("Activated clustering run %s for workspace %s", run_id, workspace_id)

    def get_active_topics(self, workspace_id: uuid.UUID) -> List[Topic]:
        """Fetches topics belonging to the currently active clustering run for workspace."""
        active_run = self.get_active_run(workspace_id)
        if not active_run:
            return []

        stmt = (
            select(Topic)
            .where(
                Topic.clustering_run_id == active_run.id,
                Topic.workspace_id == workspace_id,
            )
            .order_by(Topic.cluster_key)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_topic_chunks(
        self,
        workspace_id: uuid.UUID,
        topic_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Tuple[TopicAssignment, DocumentChunk]], int]:
        """Fetches paginated authorized chunks assigned to a topic, excluding soft-deleted documents."""
        base_stmt = (
            select(TopicAssignment, DocumentChunk)
            .join(DocumentChunk, TopicAssignment.chunk_id == DocumentChunk.id)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                TopicAssignment.topic_id == topic_id,
                TopicAssignment.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .order_by(TopicAssignment.distance_to_centroid.asc().nulls_last())
        )

        # Count total
        count_stmt = (
            select(func.count(TopicAssignment.id))
            .join(DocumentChunk, TopicAssignment.chunk_id == DocumentChunk.id)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                TopicAssignment.topic_id == topic_id,
                TopicAssignment.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
        )
        total = self.session.execute(count_stmt).scalar() or 0

        # Paginate
        offset = max(0, (page - 1) * page_size)
        paginated_stmt = base_stmt.offset(offset).limit(page_size)
        results = self.session.execute(paginated_stmt).all()

        return [(row[0], row[1]) for row in results], total

    def list_runs_paginated(
        self,
        workspace_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Lists historical clustering runs with topic and assignment counts, paginated and optimized without N+1."""
        count_stmt = select(func.count(TopicClusteringRun.id)).where(
            TopicClusteringRun.workspace_id == workspace_id
        )
        total = self.session.execute(count_stmt).scalar() or 0

        offset = max(0, (page - 1) * page_size)
        runs_stmt = (
            select(TopicClusteringRun)
            .where(TopicClusteringRun.workspace_id == workspace_id)
            .order_by(desc(TopicClusteringRun.created_at))
            .offset(offset)
            .limit(page_size)
        )
        runs = list(self.session.execute(runs_stmt).scalars().all())
        if not runs:
            return [], total

        run_ids = [r.id for r in runs]

        # Aggregate counts in bulk to eliminate N+1 queries
        topic_counts = dict(
            self.session.execute(
                select(Topic.clustering_run_id, func.count(Topic.id))
                .where(Topic.clustering_run_id.in_(run_ids))
                .group_by(Topic.clustering_run_id)
            ).all()
        )

        assign_counts = dict(
            self.session.execute(
                select(TopicAssignment.clustering_run_id, func.count(TopicAssignment.id))
                .where(TopicAssignment.clustering_run_id.in_(run_ids))
                .group_by(TopicAssignment.clustering_run_id)
            ).all()
        )

        items = []
        for r in runs:
            items.append(
                {
                    "id": str(r.id),
                    "workspace_id": str(r.workspace_id),
                    "snapshot_id": r.snapshot_id,
                    "status": r.status,
                    "k": r.k,
                    "model_version": r.model_version,
                    "is_active": r.is_active,
                    "created_at": r.created_at.isoformat(),
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "topic_count": topic_counts.get(r.id, 0),
                    "total_assignments": assign_counts.get(r.id, 0),
                }
            )

        return items, total

    def get_run_detail(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves comprehensive metadata and summary metrics for an individual clustering run."""
        run = self.get_clustering_run(run_id=run_id, workspace_id=workspace_id)
        if not run:
            return None

        topic_count = (
            self.session.execute(
                select(func.count(Topic.id)).where(Topic.clustering_run_id == run.id)
            ).scalar()
            or 0
        )
        total_assignments = (
            self.session.execute(
                select(func.count(TopicAssignment.id)).where(
                    TopicAssignment.clustering_run_id == run.id
                )
            ).scalar()
            or 0
        )

        return {
            "id": str(run.id),
            "workspace_id": str(run.workspace_id),
            "snapshot_id": run.snapshot_id,
            "status": run.status,
            "algorithm": run.algorithm,
            "model_version": run.model_version,
            "embedding_model_id": run.embedding_model_id,
            "embedding_dimension": run.embedding_dimension,
            "k": run.k,
            "configuration": run.configuration or {},
            "evaluation_metrics": run.evaluation_metrics or {},
            "selection_metadata": run.selection_metadata or {},
            "corpus_snapshot_hash": run.corpus_snapshot_hash,
            "created_by_user_id": str(run.created_by_user_id) if run.created_by_user_id else None,
            "created_at": run.created_at.isoformat(),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "is_active": run.is_active,
            "topic_count": topic_count,
            "total_assignments": total_assignments,
        }

    def get_topics_for_run(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        search: Optional[str] = None,
        sort_by: str = "chunk_count",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fetches paginated topics belonging to a run with active chunk and document counts, supporting search and sorting."""
        stats_subq = (
            select(
                TopicAssignment.topic_id,
                func.count(TopicAssignment.id).label("chunk_count"),
                func.count(func.distinct(TopicAssignment.document_id)).label("document_count"),
            )
            .join(Document, TopicAssignment.document_id == Document.id)
            .where(
                TopicAssignment.workspace_id == workspace_id,
                TopicAssignment.clustering_run_id == run_id,
                Document.deleted_at.is_(None),
            )
            .group_by(TopicAssignment.topic_id)
            .subquery()
        )

        base_stmt = (
            select(
                Topic,
                func.coalesce(stats_subq.c.chunk_count, 0).label("chunk_count"),
                func.coalesce(stats_subq.c.document_count, 0).label("document_count"),
            )
            .outerjoin(stats_subq, Topic.id == stats_subq.c.topic_id)
            .where(
                Topic.workspace_id == workspace_id,
                Topic.clustering_run_id == run_id,
            )
        )

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            search_cond = (
                func.lower(Topic.label).like(term)
                | func.lower(func.coalesce(Topic.description, "")).like(term)
                | func.lower(Topic.cluster_key).like(term)
                | func.lower(cast(Topic.keywords, String)).like(term)
            )
            base_stmt = base_stmt.where(search_cond)

        # Count total matching topics
        count_stmt = select(func.count(Topic.id)).where(
            Topic.workspace_id == workspace_id,
            Topic.clustering_run_id == run_id,
        )
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            count_stmt = count_stmt.where(
                func.lower(Topic.label).like(term)
                | func.lower(func.coalesce(Topic.description, "")).like(term)
                | func.lower(Topic.cluster_key).like(term)
                | func.lower(cast(Topic.keywords, String)).like(term)
            )
        total = self.session.execute(count_stmt).scalar() or 0

        # Sorting logic
        is_desc = sort_order.lower() == "desc"
        if sort_by == "label":
            order_col = desc(Topic.label) if is_desc else asc(Topic.label)
        elif sort_by == "document_count":
            order_col = (
                desc(func.coalesce(stats_subq.c.document_count, 0))
                if is_desc
                else asc(func.coalesce(stats_subq.c.document_count, 0))
            )
        elif sort_by == "cluster_key":
            order_col = desc(Topic.cluster_key) if is_desc else asc(Topic.cluster_key)
        else:  # default "chunk_count"
            order_col = (
                desc(func.coalesce(stats_subq.c.chunk_count, 0))
                if is_desc
                else asc(func.coalesce(stats_subq.c.chunk_count, 0))
            )

        paginated_stmt = (
            base_stmt.order_by(order_col, asc(Topic.cluster_key))
            .offset(max(0, (page - 1) * page_size))
            .limit(page_size)
        )

        rows = self.session.execute(paginated_stmt).all()
        items = []
        for topic_obj, chunk_count, doc_count in rows:
            items.append(
                {
                    "id": str(topic_obj.id),
                    "workspace_id": str(topic_obj.workspace_id),
                    "clustering_run_id": str(topic_obj.clustering_run_id),
                    "cluster_key": topic_obj.cluster_key,
                    "label": topic_obj.label,
                    "description": topic_obj.description,
                    "label_source": topic_obj.label_source,
                    "label_status": topic_obj.label_status,
                    "keywords": topic_obj.keywords or [],
                    "chunk_count": int(chunk_count),
                    "document_count": int(doc_count),
                    "representative_chunk_ids": topic_obj.representative_chunk_ids or [],
                    "created_at": topic_obj.created_at.isoformat(),
                    "updated_at": topic_obj.updated_at.isoformat(),
                }
            )

        return items, total

    def get_topic_detail(
        self,
        workspace_id: uuid.UUID,
        topic_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves comprehensive details for an individual topic including active counts and parent run summary."""
        topic_obj = (
            self.session.execute(
                select(Topic).where(
                    Topic.id == topic_id,
                    Topic.workspace_id == workspace_id,
                )
            )
            .scalars()
            .first()
        )
        if not topic_obj:
            return None

        # Count active chunks and distinct documents
        stats_row = self.session.execute(
            select(
                func.count(TopicAssignment.id).label("chunk_count"),
                func.count(func.distinct(TopicAssignment.document_id)).label("document_count"),
            )
            .join(Document, TopicAssignment.document_id == Document.id)
            .where(
                TopicAssignment.topic_id == topic_obj.id,
                TopicAssignment.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
        ).one()

        chunk_count = stats_row.chunk_count or 0
        doc_count = stats_row.document_count or 0

        # Run summary
        run = self.get_clustering_run(run_id=topic_obj.clustering_run_id, workspace_id=workspace_id)
        run_summary = None
        if run:
            run_summary = {
                "id": str(run.id),
                "workspace_id": str(run.workspace_id),
                "snapshot_id": run.snapshot_id,
                "status": run.status,
                "k": run.k,
                "model_version": run.model_version,
                "is_active": run.is_active,
                "created_at": run.created_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }

        return {
            "id": str(topic_obj.id),
            "workspace_id": str(topic_obj.workspace_id),
            "clustering_run_id": str(topic_obj.clustering_run_id),
            "cluster_key": topic_obj.cluster_key,
            "label": topic_obj.label,
            "description": topic_obj.description,
            "label_source": topic_obj.label_source,
            "label_status": topic_obj.label_status,
            "keywords": topic_obj.keywords or [],
            "chunk_count": int(chunk_count),
            "document_count": int(doc_count),
            "representative_chunk_ids": topic_obj.representative_chunk_ids or [],
            "cluster_statistics": topic_obj.cluster_statistics or {},
            "created_at": topic_obj.created_at.isoformat(),
            "updated_at": topic_obj.updated_at.isoformat(),
            "run_summary": run_summary,
        }

    def get_topic_chunks_detail(
        self,
        workspace_id: uuid.UUID,
        topic_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        representative_only: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fetches paginated authorized chunks assigned to a topic with parent document context."""
        base_stmt = (
            select(TopicAssignment, DocumentChunk, Document)
            .join(DocumentChunk, TopicAssignment.chunk_id == DocumentChunk.id)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                TopicAssignment.topic_id == topic_id,
                TopicAssignment.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
        )

        if representative_only:
            base_stmt = base_stmt.where(TopicAssignment.is_representative == True)  # noqa: E712

        count_stmt = (
            select(func.count(TopicAssignment.id))
            .join(DocumentChunk, TopicAssignment.chunk_id == DocumentChunk.id)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                TopicAssignment.topic_id == topic_id,
                TopicAssignment.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
        )
        if representative_only:
            count_stmt = count_stmt.where(TopicAssignment.is_representative == True)  # noqa: E712

        total = self.session.execute(count_stmt).scalar() or 0

        paginated_stmt = (
            base_stmt.order_by(
                TopicAssignment.distance_to_centroid.asc().nulls_last(),
                DocumentChunk.chunk_index.asc(),
            )
            .offset(max(0, (page - 1) * page_size))
            .limit(page_size)
        )

        rows = self.session.execute(paginated_stmt).all()
        items = []
        for assign, chunk, doc in rows:
            content_str = chunk.content or ""
            preview = (
                content_str[:250].strip() + ("..." if len(content_str) > 250 else "")
            )
            items.append(
                {
                    "assignment_id": str(assign.id),
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "document_title": doc.original_filename,
                    "chunk_index": chunk.chunk_index,
                    "distance_to_centroid": assign.distance_to_centroid,
                    "is_representative": assign.is_representative,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "slide_number": chunk.slide_number,
                    "section_title": chunk.section_title,
                    "content_preview": preview,
                    "source_type": doc.media_type or doc.file_extension,
                }
            )

        return items, total
