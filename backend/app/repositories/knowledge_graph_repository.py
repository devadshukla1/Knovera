"""Knowledge Graph Repository for PostgreSQL persistence and queries (Phase 7)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from backend.app.core.logging import get_logger
from backend.app.models.knowledge_extraction_run import KnowledgeExtractionRun
from backend.app.models.knowledge_mention import KnowledgeMention
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.knowledge_relationship import KnowledgeRelationship
from backend.app.models.relationship_evidence import RelationshipEvidence
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedRelationship,
    NormalizedNode,
)

logger = get_logger("knovera.repositories.knowledge_graph")


class KnowledgeGraphRepository:
    """Handles database transactions, graph persistence, and retrieval for Knowledge Graph."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_extraction_run(
        self,
        workspace_id: uuid.UUID,
        extraction_method: str = "deterministic",
        ontology_version: str = "1.0.0",
        total_chunks_processed: int = 0,
        total_nodes_extracted: int = 0,
        total_relationships_extracted: int = 0,
        statistics: Optional[Dict[str, Any]] = None,
        status: str = "completed",
        error_message: Optional[str] = None,
    ) -> KnowledgeExtractionRun:
        """Records a knowledge extraction run."""
        now = datetime.now(timezone.utc)
        run = KnowledgeExtractionRun(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            status=status,
            ontology_version=ontology_version,
            extraction_method=extraction_method,
            total_chunks_processed=total_chunks_processed,
            total_nodes_extracted=total_nodes_extracted,
            total_relationships_extracted=total_relationships_extracted,
            statistics=statistics or {},
            error_message=error_message,
            created_at=now,
            updated_at=now,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def get_latest_run(self, workspace_id: uuid.UUID) -> Optional[KnowledgeExtractionRun]:
        """Retrieves most recent extraction run for a workspace."""
        stmt = (
            select(KnowledgeExtractionRun)
            .where(KnowledgeExtractionRun.workspace_id == workspace_id)
            .order_by(desc(KnowledgeExtractionRun.created_at))
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_run_by_id(self, run_id: uuid.UUID) -> Optional[KnowledgeExtractionRun]:
        """Retrieves a specific run by ID."""
        stmt = select(KnowledgeExtractionRun).where(KnowledgeExtractionRun.id == run_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def persist_nodes_and_mentions(
        self,
        workspace_id: uuid.UUID,
        nodes: List[NormalizedNode],
        extraction_run_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, KnowledgeNode]:
        """Persists or retrieves canonical nodes and saves their mentions."""
        node_map: Dict[str, KnowledgeNode] = {}
        if not nodes:
            return node_map

        # Query existing nodes in this workspace
        existing_stmt = select(KnowledgeNode).where(KnowledgeNode.workspace_id == workspace_id)
        existing_nodes = self.session.execute(existing_stmt).scalars().all()
        existing_map: Dict[Tuple[str, str], KnowledgeNode] = {
            (n.normalized_name.lower(), n.category.lower()): n for n in existing_nodes
        }

        now = datetime.now(timezone.utc)

        for n_schema in nodes:
            norm_key = n_schema.normalized_name.lower()
            cat_key = n_schema.category.lower()

            existing_node = existing_map.get((norm_key, cat_key))
            if existing_node:
                # Update aliases if new ones found
                new_aliases = sorted(list(set(existing_node.aliases + n_schema.aliases)))
                existing_node.aliases = new_aliases
                if not existing_node.description and n_schema.description:
                    existing_node.description = n_schema.description
                existing_node.updated_at = now
                node_map[n_schema.name.lower()] = existing_node
                node_map[norm_key] = existing_node
                active_node = existing_node
            else:
                new_node = KnowledgeNode(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    extraction_run_id=extraction_run_id,
                    node_type=n_schema.node_type,
                    category=n_schema.category,
                    name=n_schema.name,
                    normalized_name=n_schema.normalized_name,
                    description=n_schema.description,
                    aliases=n_schema.aliases,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(new_node)
                self.session.flush()
                existing_map[(norm_key, cat_key)] = new_node
                node_map[n_schema.name.lower()] = new_node
                node_map[norm_key] = new_node
                active_node = new_node

            # Set id back on schema
            n_schema.id = str(active_node.id)

            # Persist mentions
            for m in n_schema.mentions:
                chunk_uuid = None
                if m.chunk_id:
                    try:
                        chunk_uuid = uuid.UUID(m.chunk_id) if isinstance(m.chunk_id, str) else m.chunk_id
                    except (ValueError, TypeError):
                        chunk_uuid = None

                mention_record = KnowledgeMention(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    node_id=active_node.id,
                    chunk_id=chunk_uuid,
                    surface_form=m.surface_form,
                    start_offset=m.start_offset,
                    end_offset=m.end_offset,
                    confidence=m.confidence,
                    extraction_method=m.extraction_method,
                    created_at=now,
                )
                self.session.add(mention_record)

        self.session.flush()
        return node_map

    def persist_relationships(
        self,
        workspace_id: uuid.UUID,
        relationships: List[ExtractedRelationship],
        node_map: Dict[str, KnowledgeNode],
        extraction_run_id: Optional[uuid.UUID] = None,
    ) -> List[KnowledgeRelationship]:
        """Persists typed relationships and their verifiable textual evidence."""
        persisted: List[KnowledgeRelationship] = []
        if not relationships:
            return persisted

        now = datetime.now(timezone.utc)

        # Query existing relationships in workspace
        existing_stmt = select(KnowledgeRelationship).where(KnowledgeRelationship.workspace_id == workspace_id)
        existing_rels = self.session.execute(existing_stmt).scalars().all()
        existing_rel_map = {
            (r.source_node_id, r.target_node_id, r.relation_type, r.is_negated): r
            for r in existing_rels
        }

        for rel in relationships:
            src_node = node_map.get(rel.source_node_name.lower())
            tgt_node = node_map.get(rel.target_node_name.lower())

            if not src_node or not tgt_node:
                continue

            rel_key = (src_node.id, tgt_node.id, rel.predicate, rel.is_negated)
            existing = existing_rel_map.get(rel_key)

            if existing:
                rel_record = existing
                existing.confidence = max(existing.confidence, rel.confidence)
                existing.updated_at = now
            else:
                rel_record = KnowledgeRelationship(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    extraction_run_id=extraction_run_id,
                    source_node_id=src_node.id,
                    target_node_id=tgt_node.id,
                    relation_type=rel.predicate,
                    inverse_relation_type=rel.inverse_predicate,
                    is_negated=rel.is_negated,
                    modality=rel.modality,
                    qualifiers=rel.qualifiers,
                    confidence=rel.confidence,
                    extraction_method=rel.extraction_method,
                    validation_status=rel.validation_status,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(rel_record)
                self.session.flush()
                existing_rel_map[rel_key] = rel_record
                persisted.append(rel_record)

            # Insert evidence records
            for ev in rel.evidence:
                chunk_uuid = None
                if ev.chunk_id:
                    try:
                        chunk_uuid = uuid.UUID(ev.chunk_id) if isinstance(ev.chunk_id, str) else ev.chunk_id
                    except (ValueError, TypeError):
                        chunk_uuid = None

                ev_record = RelationshipEvidence(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    relationship_id=rel_record.id,
                    chunk_id=chunk_uuid,
                    evidence_text=ev.evidence_text,
                    start_offset=ev.start_offset,
                    end_offset=ev.end_offset,
                    confidence=ev.confidence,
                    created_at=now,
                )
                self.session.add(ev_record)

        self.session.flush()
        return persisted

    def get_workspace_nodes(
        self,
        workspace_id: uuid.UUID,
        node_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[KnowledgeNode]:
        """Queries canonical nodes for a workspace with optional filters."""
        stmt = (
            select(KnowledgeNode)
            .where(KnowledgeNode.workspace_id == workspace_id)
            .options(joinedload(KnowledgeNode.mentions))
        )
        if node_type:
            stmt = stmt.where(KnowledgeNode.node_type == node_type)
        if category:
            stmt = stmt.where(KnowledgeNode.category == category)

        stmt = stmt.order_by(KnowledgeNode.name).limit(limit).offset(offset)
        return self.session.execute(stmt).unique().scalars().all()

    def get_workspace_relationships(
        self,
        workspace_id: uuid.UUID,
        limit: int = 200,
        offset: int = 0,
    ) -> List[KnowledgeRelationship]:
        """Queries relationships for a workspace with evidence records."""
        stmt = (
            select(KnowledgeRelationship)
            .where(KnowledgeRelationship.workspace_id == workspace_id)
            .options(
                joinedload(KnowledgeRelationship.source_node),
                joinedload(KnowledgeRelationship.target_node),
                joinedload(KnowledgeRelationship.evidence_records),
            )
            .order_by(desc(KnowledgeRelationship.confidence))
            .limit(limit)
            .offset(offset)
        )
        return self.session.execute(stmt).unique().scalars().all()
