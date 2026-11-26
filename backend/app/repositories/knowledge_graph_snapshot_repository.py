"""Knowledge Graph Snapshot Repository for PostgreSQL persistence (Phase 7 C7.6)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import desc, select, update
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.knowledge_graph_snapshot import KnowledgeGraphSnapshot

logger = get_logger("knovera.repositories.knowledge_graph_snapshot")


class KnowledgeGraphSnapshotRepository:
    """Handles database transactions and queries for Knowledge Graph Snapshots."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_snapshot(
        self,
        workspace_id: uuid.UUID,
        extraction_run_id: Optional[uuid.UUID] = None,
        node_count: int = 0,
        concept_count: int = 0,
        entity_count: int = 0,
        edge_count: int = 0,
        isolated_node_count: int = 0,
        component_count: int = 0,
        graph_statistics: Optional[Dict[str, Any]] = None,
        artifact_uri: Optional[str] = None,
        artifact_checksum: Optional[str] = None,
        serialization_format: str = "json_node_link",
        configuration: Optional[Dict[str, Any]] = None,
        source_snapshot_hash: Optional[str] = None,
        created_by_user_id: Optional[uuid.UUID] = None,
        status: str = "completed",
        is_active: bool = False,
    ) -> KnowledgeGraphSnapshot:
        """Creates a new KnowledgeGraphSnapshot record."""
        now = datetime.now(timezone.utc)
        snapshot = KnowledgeGraphSnapshot(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            extraction_run_id=extraction_run_id,
            status=status,
            graph_schema_version="1.0.0",
            ontology_version="1.0.0",
            relationship_ontology_version="1.0.0",
            builder_version="1.0.0",
            source_snapshot_hash=source_snapshot_hash,
            node_count=node_count,
            concept_count=concept_count,
            entity_count=entity_count,
            edge_count=edge_count,
            isolated_node_count=isolated_node_count,
            component_count=component_count,
            graph_statistics=graph_statistics or {},
            artifact_uri=artifact_uri,
            artifact_checksum=artifact_checksum,
            serialization_format=serialization_format,
            configuration=configuration or {},
            is_active=is_active,
            created_at=now,
            completed_at=now if status in {"completed", "completed_with_warnings"} else None,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(snapshot)
        self.session.flush()

        if is_active:
            self.activate_snapshot(workspace_id=workspace_id, snapshot_id=snapshot.id)

        return snapshot

    def get_active_snapshot(self, workspace_id: uuid.UUID) -> Optional[KnowledgeGraphSnapshot]:
        """Returns the currently active snapshot for a workspace."""
        stmt = (
            select(KnowledgeGraphSnapshot)
            .where(
                KnowledgeGraphSnapshot.workspace_id == workspace_id,
                KnowledgeGraphSnapshot.is_active.is_(True),
            )
            .order_by(desc(KnowledgeGraphSnapshot.created_at))
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_snapshot_by_id(self, snapshot_id: uuid.UUID) -> Optional[KnowledgeGraphSnapshot]:
        """Retrieves a specific snapshot by ID."""
        stmt = select(KnowledgeGraphSnapshot).where(KnowledgeGraphSnapshot.id == snapshot_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_snapshots(
        self,
        workspace_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[KnowledgeGraphSnapshot]:
        """Retrieves historical snapshots for a workspace."""
        stmt = (
            select(KnowledgeGraphSnapshot)
            .where(KnowledgeGraphSnapshot.workspace_id == workspace_id)
            .order_by(desc(KnowledgeGraphSnapshot.created_at))
            .limit(limit)
            .offset(offset)
        )
        return self.session.execute(stmt).scalars().all()

    def activate_snapshot(
        self,
        workspace_id: uuid.UUID,
        snapshot_id: uuid.UUID,
    ) -> Optional[KnowledgeGraphSnapshot]:
        """Atomically switches the active snapshot for a workspace."""
        # Deactivate all other snapshots for this workspace
        deactivate_stmt = (
            update(KnowledgeGraphSnapshot)
            .where(
                KnowledgeGraphSnapshot.workspace_id == workspace_id,
                KnowledgeGraphSnapshot.id != snapshot_id,
            )
            .values(is_active=False)
        )
        self.session.execute(deactivate_stmt)

        # Activate target snapshot
        activate_stmt = (
            update(KnowledgeGraphSnapshot)
            .where(
                KnowledgeGraphSnapshot.workspace_id == workspace_id,
                KnowledgeGraphSnapshot.id == snapshot_id,
            )
            .values(is_active=True)
        )
        self.session.execute(activate_stmt)
        self.session.flush()

        return self.get_snapshot_by_id(snapshot_id)

    def mark_failed(
        self,
        snapshot_id: uuid.UUID,
        failure_code: str,
        error_message: str,
    ) -> Optional[KnowledgeGraphSnapshot]:
        """Marks a snapshot as failed with diagnostic reason."""
        stmt = (
            update(KnowledgeGraphSnapshot)
            .where(KnowledgeGraphSnapshot.id == snapshot_id)
            .values(
                status="failed",
                is_active=False,
                failure_reason_code=failure_code,
                error_message=error_message,
                completed_at=datetime.now(timezone.utc),
            )
        )
        self.session.execute(stmt)
        self.session.flush()
        return self.get_snapshot_by_id(snapshot_id)
