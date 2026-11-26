"""Graph Persistence Service for Knovera Knowledge Graph (Phase 7 C7.6).

Manages atomic file persistence, manifest generation, cryptographic verification,
active/historical snapshot registration in PostgreSQL, and canonical reconstruction.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple
import uuid
import networkx as nx
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.ml.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from backend.app.ml.knowledge_graph.graph_loader import GraphLoader
from backend.app.ml.knowledge_graph.graph_serializer import GraphSerializer
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedRelationship,
    GraphSnapshotManifest,
    GraphStatistics,
    NormalizedNode,
    RelationshipEvidenceRecord,
)
from backend.app.models.knowledge_graph_snapshot import KnowledgeGraphSnapshot
from backend.app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from backend.app.repositories.knowledge_graph_snapshot_repository import (
    KnowledgeGraphSnapshotRepository,
)

logger = get_logger("knovera.ml.knowledge_graph.persistence")


class GraphPersistenceService:
    """Handles atomic storage, snapshot lifecycle, and graph reconstruction."""

    def __init__(self, base_storage_dir: Optional[Path] = None) -> None:
        self.storage_root = Path(base_storage_dir) if base_storage_dir else Path(settings.STORAGE_LOCAL_PATH)
        self.base_dir = self.storage_root / "knowledge_graphs"

    def persist_snapshot(
        self,
        workspace_id: str,
        graph: nx.MultiDiGraph,
        statistics: GraphStatistics,
        session: Session,
        extraction_run_id: Optional[str] = None,
        source_snapshot_hash: Optional[str] = None,
        is_active: bool = True,
        created_by_user_id: Optional[str] = None,
        validation_policy_version: str = "1.0.0",
    ) -> Tuple[KnowledgeGraphSnapshot, GraphSnapshotManifest]:
        """Atomically serializes and persists a MultiDiGraph snapshot to storage and DB.

        1. Deterministic JSON serialization and SHA-256 calculation.
        2. Write to atomic temp file, verify checksum, and promote.
        3. Write sidecar manifest.json.
        4. Record snapshot in PostgreSQL.
        5. Atomically activate if is_active is True.
        """
        ws_uuid = uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id
        run_uuid = uuid.UUID(extraction_run_id) if extraction_run_id else None
        user_uuid = uuid.UUID(created_by_user_id) if created_by_user_id else None

        # 1. Deterministic serialization
        json_content, checksum, manifest = GraphSerializer.serialize_graph(
            graph=graph,
            statistics=statistics,
            validation_policy_version=validation_policy_version,
        )

        snapshot_id = manifest.snapshot_id or f"snap_{uuid.uuid4().hex[:12]}"
        snapshot_dir = self.base_dir / f"workspace_{ws_uuid}" / f"snapshot_{snapshot_id}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        artifact_file = snapshot_dir / "graph.json"
        tmp_file = snapshot_dir / "graph.json.tmp"
        manifest_file = snapshot_dir / "manifest.json"

        try:
            # 2. Atomic File Write
            with open(tmp_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(json_content)

            # Checksum verification on written file
            with open(tmp_file, "rb") as f:
                written_checksum = hashlib.sha256(f.read()).hexdigest()

            if written_checksum != checksum:
                raise IOError(
                    f"Artifact write verification failed: expected {checksum}, got {written_checksum}"
                )

            # Atomic promotion
            if artifact_file.exists():
                artifact_file.unlink()
            tmp_file.replace(artifact_file)

            # Write manifest
            with open(manifest_file, "w", encoding="utf-8", newline="\n") as f:
                json.dump(manifest.model_dump(), f, indent=2, sort_keys=True)

            rel_artifact_uri = f"knowledge_graphs/workspace_{ws_uuid}/snapshot_{snapshot_id}/graph.json"

            # 3. PostgreSQL Snapshot Registration
            repo = KnowledgeGraphSnapshotRepository(session)
            snapshot_rec = repo.create_snapshot(
                workspace_id=ws_uuid,
                extraction_run_id=run_uuid,
                node_count=statistics.total_nodes,
                concept_count=statistics.concept_count,
                entity_count=statistics.entity_count,
                edge_count=statistics.total_edges,
                isolated_node_count=statistics.isolated_node_count,
                component_count=statistics.connected_components_count,
                graph_statistics=statistics.model_dump(),
                artifact_uri=rel_artifact_uri,
                artifact_checksum=checksum,
                source_snapshot_hash=source_snapshot_hash,
                created_by_user_id=user_uuid,
                status="completed",
                is_active=is_active,
            )

            session.flush()
            logger.info(
                "Persisted knowledge graph snapshot %s for workspace %s (checksum: %s)",
                snapshot_rec.id,
                workspace_id,
                checksum[:12],
            )
            return snapshot_rec, manifest

        except Exception as e:
            logger.error("Failed to persist knowledge graph snapshot: %s", e)
            if tmp_file.exists():
                tmp_file.unlink(missing_ok=True)
            raise

    def load_active_graph(
        self,
        workspace_id: str,
        session: Session,
    ) -> Optional[Tuple[nx.MultiDiGraph, KnowledgeGraphSnapshot]]:
        """Loads and verifies the active MultiDiGraph snapshot for a workspace."""
        ws_uuid = uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id
        repo = KnowledgeGraphSnapshotRepository(session)
        snapshot_rec = repo.get_active_snapshot(ws_uuid)

        if not snapshot_rec or not snapshot_rec.artifact_uri:
            return None

        # Resolve path
        artifact_path = Path(settings.STORAGE_LOCAL_PATH) / snapshot_rec.artifact_uri
        if not artifact_path.exists():
            # Try resolving against self.base_dir parent
            artifact_path = self.base_dir.parent / snapshot_rec.artifact_uri

        if not artifact_path.exists():
            logger.warning("Graph artifact file %s missing on disk. Attempting fallback reconstruction.", artifact_path)
            return self.reconstruct_and_repair(ws_uuid, session, snapshot_rec)

        with open(artifact_path, "r", encoding="utf-8", newline="") as f:
            content = f.read()

        graph = GraphLoader.load_from_json(
            json_content=content,
            expected_checksum=snapshot_rec.artifact_checksum,
        )
        return graph, snapshot_rec

    def load_snapshot(
        self,
        workspace_id: str,
        snapshot_id: str,
        session: Session,
    ) -> Optional[Tuple[nx.MultiDiGraph, KnowledgeGraphSnapshot]]:
        """Loads and verifies a specific MultiDiGraph snapshot by ID for an authorized workspace."""
        ws_uuid = uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id
        try:
            snap_uuid = uuid.UUID(snapshot_id) if isinstance(snapshot_id, str) else snapshot_id
        except (ValueError, TypeError):
            return None

        repo = KnowledgeGraphSnapshotRepository(session)
        snapshot_rec = repo.get_snapshot_by_id(snap_uuid)

        if not snapshot_rec or snapshot_rec.workspace_id != ws_uuid or not snapshot_rec.artifact_uri:
            return None

        # Resolve path
        artifact_path = Path(settings.STORAGE_LOCAL_PATH) / snapshot_rec.artifact_uri
        if not artifact_path.exists():
            # Try resolving against self.base_dir parent
            artifact_path = self.base_dir.parent / snapshot_rec.artifact_uri

        if not artifact_path.exists():
            logger.warning(
                "Graph artifact file %s missing on disk for snapshot %s. Fallback reconstruction.",
                artifact_path,
                snapshot_id,
            )
            return self.reconstruct_and_repair(ws_uuid, session, snapshot_rec)

        with open(artifact_path, "r", encoding="utf-8", newline="") as f:
            content = f.read()

        graph = GraphLoader.load_from_json(
            json_content=content,
            expected_checksum=snapshot_rec.artifact_checksum,
        )
        return graph, snapshot_rec

    def reconstruct_from_db(
        self,
        workspace_id: uuid.UUID,
        session: Session,
        extraction_run_id: Optional[uuid.UUID] = None,
    ) -> Tuple[nx.MultiDiGraph, GraphStatistics]:
        """Reconstructs the knowledge graph purely from canonical PostgreSQL records."""
        kg_repo = KnowledgeGraphRepository(session)
        orm_nodes = kg_repo.get_workspace_nodes(workspace_id=workspace_id, limit=5000)
        orm_rels = kg_repo.get_workspace_relationships(workspace_id=workspace_id, limit=10000)

        # Convert ORM nodes to NormalizedNode schemas
        schema_nodes: List[NormalizedNode] = [
            NormalizedNode(
                id=str(n.id),
                workspace_id=str(n.workspace_id),
                name=n.name,
                normalized_name=n.normalized_name,
                category=n.category,
                node_type=n.node_type,
                description=n.description,
                aliases=n.aliases or [],
            )
            for n in orm_nodes
        ]

        # Convert ORM relationships to ExtractedRelationship schemas
        schema_rels: List[ExtractedRelationship] = []
        for r in orm_rels:
            ev_records = [
                RelationshipEvidenceRecord(
                    id=str(ev.id),
                    chunk_id=str(ev.chunk_id) if ev.chunk_id else "",
                    evidence_text=ev.evidence_text,
                    start_offset=ev.start_offset,
                    end_offset=ev.end_offset,
                    confidence=ev.confidence,
                )
                for ev in r.evidence_records
            ]

            schema_rels.append(
                ExtractedRelationship(
                    id=str(r.id),
                    source_node_name=r.source_node.name if r.source_node else "",
                    target_node_name=r.target_node.name if r.target_node else "",
                    source_node_id=str(r.source_node_id),
                    target_node_id=str(r.target_node_id),
                    predicate=r.relation_type,
                    inverse_predicate=r.inverse_relation_type,
                    is_negated=r.is_negated,
                    modality=r.modality,
                    qualifiers=r.qualifiers or {},
                    evidence=ev_records,
                    confidence=r.confidence,
                    extraction_method=r.extraction_method,
                    validation_status=r.validation_status,
                )
            )

        builder = KnowledgeGraphBuilder()
        graph, stats = builder.build_graph(
            workspace_id=str(workspace_id),
            nodes=schema_nodes,
            relationships=schema_rels,
            extraction_run_id=str(extraction_run_id) if extraction_run_id else None,
        )

        return graph, stats

    def reconstruct_and_repair(
        self,
        workspace_id: uuid.UUID,
        session: Session,
        snapshot_rec: KnowledgeGraphSnapshot,
    ) -> Tuple[nx.MultiDiGraph, KnowledgeGraphSnapshot]:
        """Reconstructs the graph from DB and re-persists the missing artifact file."""
        graph, stats = self.reconstruct_from_db(
            workspace_id=workspace_id,
            session=session,
            extraction_run_id=snapshot_rec.extraction_run_id,
        )
        # Re-save artifact for this snapshot
        json_content, checksum, manifest = GraphSerializer.serialize_graph(
            graph=graph,
            statistics=stats,
        )
        snapshot_id = snapshot_rec.id
        snapshot_dir = self.base_dir / f"workspace_{workspace_id}" / f"snapshot_{snapshot_id}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = snapshot_dir / "graph.json"
        manifest_file = snapshot_dir / "manifest.json"
        with open(artifact_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(json_content)
        with open(manifest_file, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest.model_dump(), f, indent=2, sort_keys=True)

        snapshot_rec.artifact_checksum = checksum
        snapshot_rec.artifact_uri = f"knowledge_graphs/workspace_{workspace_id}/snapshot_{snapshot_id}/graph.json"
        snapshot_rec.node_count = stats.total_nodes
        snapshot_rec.edge_count = stats.total_edges
        snapshot_rec.graph_statistics = stats.model_dump()
        session.flush()

        return graph, snapshot_rec
