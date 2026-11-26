"""Knowledge Extraction Pipeline Orchestrator for Knovera (Phase 7 C7.1 - C7.6).

Executes the end-to-end knowledge graph construction and persistence pipeline:
1. Concept & Entity Extraction (C7.1)
2. Workspace-wide Normalization & Disambiguation (C7.2)
3. Verifiable Typed Relationship Extraction (C7.3)
4. Comprehensive Relationship Validation (C7.4)
5. NetworkX MultiDiGraph Construction & Statistics (C7.5)
6. Relational & Snapshot Persistence with Cryptographic Integrity (C7.6)
"""

from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid
import networkx as nx
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.ml.knowledge_graph.concept_extraction import ConceptExtractionService
from backend.app.ml.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from backend.app.ml.knowledge_graph.graph_persistence import GraphPersistenceService
from backend.app.ml.knowledge_graph.normalization import EntityNormalizationService
from backend.app.ml.knowledge_graph.ontology import ONTOLOGY_VERSION
from backend.app.ml.knowledge_graph.relationship_extraction import RelationshipExtractionService
from backend.app.ml.knowledge_graph.relationships import RELATIONSHIP_ONTOLOGY_VERSION
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedConcept,
    ExtractedRelationship,
    ExtractionMethod,
    GraphStatistics,
    NormalizedNode,
    PipelineExtractionResult,
    RelationshipValidationReport,
)
from backend.app.ml.knowledge_graph.validation import RelationshipValidationService
from backend.app.repositories.knowledge_graph_repository import KnowledgeGraphRepository

logger = get_logger("knovera.ml.knowledge_graph.orchestrator")


class KnowledgeExtractionOrchestrator:
    """Orchestrates concept extraction, normalization, validation, graph construction, and persistence."""

    def __init__(
        self,
        concept_service: Optional[ConceptExtractionService] = None,
        normalization_service: Optional[EntityNormalizationService] = None,
        relationship_service: Optional[RelationshipExtractionService] = None,
        validation_service: Optional[RelationshipValidationService] = None,
        graph_builder: Optional[KnowledgeGraphBuilder] = None,
        persistence_service: Optional[GraphPersistenceService] = None,
    ) -> None:
        self.concept_service = concept_service or ConceptExtractionService()
        self.normalization_service = normalization_service or EntityNormalizationService()
        self.relationship_service = relationship_service or RelationshipExtractionService()
        self.validation_service = validation_service or RelationshipValidationService()
        self.graph_builder = graph_builder or KnowledgeGraphBuilder()
        self.persistence_service = persistence_service or GraphPersistenceService()

    def run_pipeline(
        self,
        workspace_id: str,
        chunks: List[Dict[str, Any]],  # [{id: str, content: str, content_hash?: str, workspace_id?: str}]
        use_llm: bool = False,
        session: Optional[Session] = None,
        source_snapshot_hash: Optional[str] = None,
        created_by_user_id: Optional[str] = None,
        persist_graph_snapshot: bool = True,
    ) -> PipelineExtractionResult:
        """Executes full knowledge extraction, validation, graph building, and snapshot persistence."""
        start_time = time.perf_counter()
        logger.info(
            "Starting knowledge extraction for workspace %s on %d chunks (use_llm=%s)",
            workspace_id,
            len(chunks),
            use_llm,
        )

        all_extracted_concepts: List[ExtractedConcept] = []
        context_snippets: Dict[str, str] = {}
        total_mentions = 0

        # Step 1: Concept & Entity Extraction per chunk (C7.1)
        for chunk in chunks:
            chunk_id = chunk.get("id", "")
            chunk_content = chunk.get("content", "")
            if not chunk_content:
                continue

            context_snippets[chunk_id] = chunk_content[:300]
            concepts = self.concept_service.extract_from_chunk(
                chunk_text=chunk_content,
                chunk_id=chunk_id,
                use_llm=use_llm,
            )
            all_extracted_concepts.extend(concepts)
            for c in concepts:
                total_mentions += len(c.mentions)

        logger.info(
            "Extracted %d raw concept candidates with %d total mentions",
            len(all_extracted_concepts),
            total_mentions,
        )

        # Step 2: Entity & Concept Normalization across workspace (C7.2)
        normalized_nodes: List[NormalizedNode] = self.normalization_service.normalize_and_deduplicate(
            concepts=all_extracted_concepts,
            workspace_id=workspace_id,
            context_snippets_by_chunk=context_snippets,
        )

        logger.info(
            "Normalized into %d canonical nodes for workspace %s",
            len(normalized_nodes),
            workspace_id,
        )

        # Step 3: Verifiable Typed Relationship Extraction (C7.3)
        relationships: List[ExtractedRelationship] = self.relationship_service.extract_relationships(
            chunks=chunks,
            nodes=normalized_nodes,
            use_llm=use_llm,
        )

        logger.info(
            "Extracted %d candidate relationships for workspace %s",
            len(relationships),
            workspace_id,
        )

        # Step 4: Relationship Validation (C7.4)
        validation_report: RelationshipValidationReport = self.validation_service.validate_relationships(
            workspace_id=workspace_id,
            relationships=relationships,
            nodes=normalized_nodes,
            chunks=chunks,
            use_llm_review=use_llm,
        )

        logger.info(
            "Validation complete: %d validated, %d needs_review, %d rejected",
            validation_report.validated_count,
            validation_report.needs_review_count,
            validation_report.rejected_count,
        )

        # Step 5: NetworkX MultiDiGraph Construction (C7.5)
        graph, stats = self.graph_builder.build_graph(
            workspace_id=workspace_id,
            nodes=normalized_nodes,
            relationships=relationships,
            source_snapshot_hash=source_snapshot_hash,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Step 6: Relational & Snapshot Persistence (C7.6)
        run_id_str = None
        if session is not None:
            try:
                ws_uuid = uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id
                repo = KnowledgeGraphRepository(session)

                method = ExtractionMethod.HYBRID.value if use_llm else ExtractionMethod.DETERMINISTIC.value
                run_stats = {
                    "total_chunks": len(chunks),
                    "total_mentions": total_mentions,
                    "total_nodes": len(normalized_nodes),
                    "total_relationships": len(relationships),
                    "validated_relationships": validation_report.validated_count,
                    "rejected_relationships": validation_report.rejected_count,
                    "needs_review_relationships": validation_report.needs_review_count,
                    "graph_nodes": stats.total_nodes,
                    "graph_edges": stats.total_edges,
                    "duration_ms": round(duration_ms, 2),
                }

                run = repo.create_extraction_run(
                    workspace_id=ws_uuid,
                    extraction_method=method,
                    ontology_version=ONTOLOGY_VERSION,
                    total_chunks_processed=len(chunks),
                    total_nodes_extracted=len(normalized_nodes),
                    total_relationships_extracted=len(relationships),
                    statistics=run_stats,
                    status="completed",
                )
                run_id_str = str(run.id)

                # Persist nodes and mentions
                node_map = repo.persist_nodes_and_mentions(
                    workspace_id=ws_uuid,
                    nodes=normalized_nodes,
                    extraction_run_id=run.id,
                )

                # Persist relationships and evidence
                repo.persist_relationships(
                    workspace_id=ws_uuid,
                    relationships=relationships,
                    node_map=node_map,
                    extraction_run_id=run.id,
                )

                # Persist versioned graph snapshot artifact and metadata
                if persist_graph_snapshot:
                    self.persistence_service.persist_snapshot(
                        workspace_id=workspace_id,
                        graph=graph,
                        statistics=stats,
                        session=session,
                        extraction_run_id=run_id_str,
                        source_snapshot_hash=source_snapshot_hash,
                        is_active=True,
                        created_by_user_id=created_by_user_id,
                    )

                session.commit()
                logger.info("Successfully committed knowledge extraction run %s and snapshot", run.id)
            except Exception as e:
                session.rollback()
                logger.error("Failed to persist knowledge extraction and graph: %s", e)
                raise

        return PipelineExtractionResult(
            workspace_id=workspace_id,
            nodes=normalized_nodes,
            relationships=relationships,
            total_chunks_processed=len(chunks),
            total_mentions_extracted=total_mentions,
            total_nodes_extracted=len(normalized_nodes),
            total_relationships_extracted=len(relationships),
            duration_ms=round(duration_ms, 2),
            run_id=run_id_str,
            extraction_method=ExtractionMethod.HYBRID.value if use_llm else ExtractionMethod.DETERMINISTIC.value,
        )
