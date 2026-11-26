"""Research Analysis Orchestrator (Phase 10 C10.1, C10.2, C10.3).

Coordinates bibliographic metadata extraction, research objective extraction, and
methodology extraction into unified, version-preserved research document profiles.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.llm.manager import LLMManager
from backend.app.ml.research.metadata_extractor import ResearchMetadataExtractor
from backend.app.ml.research.methodology_extractor import ResearchMethodologyExtractor
from backend.app.ml.research.objective_extractor import ResearchObjectiveExtractor
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.research_intelligence import (
    ResearchAnalysisRun,
    ResearchMetadataProfile,
    ResearchMethodologyProfile,
    ResearchObjectiveProfile,
)
from backend.app.schemas.research_intelligence import (
    ResearchAnalysisOverviewResponse,
    ResearchAnalysisRunRequest,
    ResearchAnalysisRunResponse,
    ResearchDocumentSummary,
    ResearchMetadataProfileResponse,
    ResearchMethodologyProfileResponse,
    ResearchObjectiveProfileResponse,
)

logger = get_logger("knovera.research.orchestrator")


class ResearchAnalysisOrchestrator:
    """Orchestrates end-to-end research document understanding pipeline."""

    def __init__(self, llm_manager: Optional[LLMManager] = None):
        self.llm_manager = llm_manager
        self.metadata_extractor = ResearchMetadataExtractor(llm_manager=llm_manager)
        self.objective_extractor = ResearchObjectiveExtractor(llm_manager=llm_manager)
        self.methodology_extractor = ResearchMethodologyExtractor(llm_manager=llm_manager)

    def execute_analysis(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
        request: ResearchAnalysisRunRequest,
    ) -> ResearchAnalysisRun:
        """Executes selected extraction components and persists profiles atomically."""
        # 1. Validate Document
        doc_stmt = (
            select(Document)
            .where(Document.id == document_id, Document.workspace_id == workspace_id)
        )
        doc = db.execute(doc_stmt).scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {document_id} not found in workspace {workspace_id}")

        if doc.processing_status != "completed":
            raise ValueError(f"Document {document_id} has status '{doc.processing_status}'. Ingestion must be completed before research analysis.")

        # Load document chunks
        chunks_stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id, DocumentChunk.workspace_id == workspace_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        chunks = list(db.execute(chunks_stmt).scalars().all())
        if not chunks:
            raise ValueError(f"Document {document_id} has 0 extracted chunks.")

        # Determine requested components
        req_components: List[str] = []
        if request.extract_metadata:
            req_components.append("metadata")
        if request.extract_objectives:
            req_components.append("objectives")
        if request.extract_methodology:
            req_components.append("methodology")

        # 2. Create Run Record
        active_provider_name = None
        manager = self.llm_manager or LLMManager.get_instance()
        if manager:
            try:
                active_provider_name = manager.get_active_provider_name()
            except Exception:
                active_provider_name = "mock"

        run = ResearchAnalysisRun(
            workspace_id=workspace_id,
            document_id=document_id,
            document_version=doc.pipeline_version or "v1.0",
            status="running",
            components_requested=req_components,
            metadata_status="queued" if request.extract_metadata else "not_requested",
            objectives_status="queued" if request.extract_objectives else "not_requested",
            methodology_status="queued" if request.extract_methodology else "not_requested",
            warnings=[],
            provider_used=active_provider_name,
            model_used=getattr(manager.settings, "LLM_MODEL", "mock-model") if manager else "mock-model",
            prompt_version="v1.0",
        )
        db.add(run)
        db.flush()

        has_warnings = False
        error_msgs: List[str] = []

        extracted_title: Optional[str] = None
        primary_objective: Optional[str] = None

        # 3. Component C10.1: Metadata Extraction
        if request.extract_metadata:
            run.metadata_status = "running"
            try:
                # Check existing profile
                existing_meta = db.execute(
                    select(ResearchMetadataProfile).where(
                        ResearchMetadataProfile.document_id == document_id,
                        ResearchMetadataProfile.workspace_id == workspace_id,
                    )
                ).scalar_one_or_none()

                if existing_meta and existing_meta.is_manually_edited and not request.should_force():
                    run.metadata_status = "completed"
                    extracted_title = existing_meta.title
                    run.warnings.append({"component": "metadata", "message": "Preserved manually edited metadata profile."})
                else:
                    meta_create = self.metadata_extractor.extract_from_document(
                        document=doc,
                        chunks=chunks,
                        run_id=run.id,
                    )
                    extracted_title = meta_create.title

                    if existing_meta:
                        # Update fields
                        for field, val in meta_create.model_dump(exclude={"workspace_id", "document_id"}).items():
                            setattr(existing_meta, field, val)
                        existing_meta.run_id = run.id
                        existing_meta.updated_at = datetime.now(timezone.utc)
                    else:
                        new_meta = ResearchMetadataProfile(
                            workspace_id=workspace_id,
                            document_id=document_id,
                            run_id=run.id,
                            document_version=meta_create.document_version,
                            document_type=meta_create.document_type,
                            title=meta_create.title,
                            subtitle=meta_create.subtitle,
                            alternative_title=meta_create.alternative_title,
                            language=meta_create.language,
                            abstract=meta_create.abstract,
                            keywords=meta_create.keywords,
                            authors=[a.model_dump() for a in meta_create.authors],
                            publication_year=meta_create.publication_year,
                            publication_date=meta_create.publication_date,
                            journal_name=meta_create.journal_name,
                            conference_name=meta_create.conference_name,
                            publisher=meta_create.publisher,
                            volume=meta_create.volume,
                            issue=meta_create.issue,
                            page_range=meta_create.page_range,
                            doi=meta_create.doi,
                            arxiv_id=meta_create.arxiv_id,
                            isbn_issn=meta_create.isbn_issn,
                            publication_status=meta_create.publication_status,
                            funding_organization=meta_create.funding_organization,
                            acknowledgements=meta_create.acknowledgements,
                            grant_identifiers=meta_create.grant_identifiers,
                            research_domain=meta_create.research_domain,
                            subdomain=meta_create.subdomain,
                            metadata_fields={k: v.model_dump() for k, v in meta_create.metadata_fields.items()},
                            conflicts=[c.model_dump() for c in meta_create.conflicts],
                            validation_status=meta_create.validation_status,
                        )
                        db.add(new_meta)

                    run.metadata_status = "completed"
            except Exception as exc:
                logger.error("Metadata extraction failed for document %s: %s", document_id, exc)
                run.metadata_status = "failed"
                has_warnings = True
                error_msgs.append(f"Metadata: {str(exc)}")

        # 4. Component C10.2: Research Objective Extraction
        if request.extract_objectives:
            run.objectives_status = "running"
            try:
                existing_obj = db.execute(
                    select(ResearchObjectiveProfile).where(
                        ResearchObjectiveProfile.document_id == document_id,
                        ResearchObjectiveProfile.workspace_id == workspace_id,
                    )
                ).scalar_one_or_none()

                if existing_obj and existing_obj.is_manually_edited and not request.should_force():
                    run.objectives_status = "completed"
                    primary_objective = existing_obj.primary_objective
                    run.warnings.append({"component": "objectives", "message": "Preserved manually edited objective profile."})
                else:
                    # Load known knowledge nodes for concept linking
                    known_concepts = list(
                        db.execute(
                            select(KnowledgeNode).where(KnowledgeNode.workspace_id == workspace_id)
                        ).scalars().all()
                    )

                    obj_create = self.objective_extractor.extract_from_document(
                        document=doc,
                        chunks=chunks,
                        known_concepts=known_concepts,
                        paper_title=extracted_title,
                        run_id=run.id,
                    )
                    primary_objective = obj_create.primary_objective

                    if existing_obj:
                        for field, val in obj_create.model_dump(exclude={"workspace_id", "document_id"}).items():
                            setattr(existing_obj, field, val)
                        existing_obj.run_id = run.id
                        existing_obj.updated_at = datetime.now(timezone.utc)
                    else:
                        new_obj = ResearchObjectiveProfile(
                            workspace_id=workspace_id,
                            document_id=document_id,
                            run_id=run.id,
                            document_version=obj_create.document_version,
                            primary_objective=obj_create.primary_objective,
                            problem_statement=obj_create.problem_statement,
                            motivation=obj_create.motivation,
                            research_scope=obj_create.research_scope,
                            objectives=[o.model_dump() for o in obj_create.objectives],
                            research_questions=[q.model_dump() for q in obj_create.research_questions],
                            hypotheses=[h.model_dump() for h in obj_create.hypotheses],
                            claimed_contributions=[c.model_dump() for c in obj_create.claimed_contributions],
                            validation_status=obj_create.validation_status,
                        )
                        db.add(new_obj)

                    run.objectives_status = "completed"
            except Exception as exc:
                logger.error("Objective extraction failed for document %s: %s", document_id, exc)
                run.objectives_status = "failed"
                has_warnings = True
                error_msgs.append(f"Objectives: {str(exc)}")

        # 5. Component C10.3: Methodology Extraction
        if request.extract_methodology:
            run.methodology_status = "running"
            try:
                existing_meth = db.execute(
                    select(ResearchMethodologyProfile).where(
                        ResearchMethodologyProfile.document_id == document_id,
                        ResearchMethodologyProfile.workspace_id == workspace_id,
                    )
                ).scalar_one_or_none()

                if existing_meth and existing_meth.is_manually_edited and not request.should_force():
                    run.methodology_status = "completed"
                    run.warnings.append({"component": "methodology", "message": "Preserved manually edited methodology profile."})
                else:
                    meth_create = self.methodology_extractor.extract_from_document(
                        document=doc,
                        chunks=chunks,
                        paper_title=extracted_title,
                        primary_objective=primary_objective,
                        run_id=run.id,
                    )

                    if existing_meth:
                        for field, val in meth_create.model_dump(exclude={"workspace_id", "document_id"}).items():
                            setattr(existing_meth, field, val)
                        existing_meth.run_id = run.id
                        existing_meth.updated_at = datetime.now(timezone.utc)
                    else:
                        new_meth = ResearchMethodologyProfile(
                            workspace_id=workspace_id,
                            document_id=document_id,
                            run_id=run.id,
                            document_version=meth_create.document_version,
                            research_approaches=meth_create.research_approaches,
                            research_designs=meth_create.research_designs,
                            study_setting=meth_create.study_setting,
                            datasets=[d.model_dump() for d in meth_create.datasets],
                            variables=[v.model_dump() for v in meth_create.variables],
                            methods_and_models=[m.model_dump() for m in meth_create.methods_and_models],
                            tools_and_instruments=[t.model_dump() for t in meth_create.tools_and_instruments],
                            experimental_setup=meth_create.experimental_setup.model_dump(),
                            evaluation_metrics=[em.model_dump() for em in meth_create.evaluation_metrics],
                            limitations=[l.model_dump() for l in meth_create.limitations],
                            validation_status=meth_create.validation_status,
                        )
                        db.add(new_meth)

                    run.methodology_status = "completed"
            except Exception as exc:
                logger.error("Methodology extraction failed for document %s: %s", document_id, exc)
                run.methodology_status = "failed"
                has_warnings = True
                error_msgs.append(f"Methodology: {str(exc)}")

        # 6. Finalize Run Status
        all_failed = (
            (not request.extract_metadata or run.metadata_status == "failed")
            and (not request.extract_objectives or run.objectives_status == "failed")
            and (not request.extract_methodology or run.methodology_status == "failed")
        )
        if all_failed and req_components:
            run.status = "failed"
        elif has_warnings:
            run.status = "completed_with_warnings"
        else:
            run.status = "completed"

        if error_msgs:
            run.error_message = "; ".join(error_msgs)

        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)

        return run

    def get_overview(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> ResearchAnalysisOverviewResponse:
        """Retrieves active research analysis profiles and most recent run."""
        doc_stmt = (
            select(Document)
            .where(Document.id == document_id, Document.workspace_id == workspace_id)
        )
        doc = db.execute(doc_stmt).scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {document_id} not found in workspace {workspace_id}")

        meta = db.execute(
            select(ResearchMetadataProfile).where(
                ResearchMetadataProfile.document_id == document_id,
                ResearchMetadataProfile.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

        obj = db.execute(
            select(ResearchObjectiveProfile).where(
                ResearchObjectiveProfile.document_id == document_id,
                ResearchObjectiveProfile.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

        meth = db.execute(
            select(ResearchMethodologyProfile).where(
                ResearchMethodologyProfile.document_id == document_id,
                ResearchMethodologyProfile.workspace_id == workspace_id,
            )
        ).scalar_one_or_none()

        last_run = db.execute(
            select(ResearchAnalysisRun)
            .where(
                ResearchAnalysisRun.document_id == document_id,
                ResearchAnalysisRun.workspace_id == workspace_id,
            )
            .order_by(ResearchAnalysisRun.created_at.desc())
        ).scalars().first()

        return ResearchAnalysisOverviewResponse(
            document_id=document_id,
            workspace_id=workspace_id,
            document_version=doc.pipeline_version or "v1.0",
            active_run=ResearchAnalysisRunResponse.model_validate(last_run) if last_run else None,
            metadata_profile=ResearchMetadataProfileResponse.model_validate(meta) if meta else None,
            objective_profile=ResearchObjectiveProfileResponse.model_validate(obj) if obj else None,
            methodology_profile=ResearchMethodologyProfileResponse.model_validate(meth) if meth else None,
        )

    def list_research_documents(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ResearchDocumentSummary]:
        """Lists workspace documents with their research analysis status summary."""
        docs = list(
            db.execute(
                select(Document)
                .where(Document.workspace_id == workspace_id)
                .order_by(Document.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).scalars().all()
        )

        summaries: List[ResearchDocumentSummary] = []
        for d in docs:
            meta = db.execute(
                select(ResearchMetadataProfile).where(
                    ResearchMetadataProfile.document_id == d.id,
                    ResearchMetadataProfile.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()

            obj = db.execute(
                select(ResearchObjectiveProfile).where(
                    ResearchObjectiveProfile.document_id == d.id,
                    ResearchObjectiveProfile.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()

            meth = db.execute(
                select(ResearchMethodologyProfile).where(
                    ResearchMethodologyProfile.document_id == d.id,
                    ResearchMethodologyProfile.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()

            author_names = [a.get("name") for a in (meta.authors if meta else []) if a.get("name")]
            doc_title = meta.title if (meta and meta.title) else d.original_filename

            summaries.append(
                ResearchDocumentSummary(
                    document_id=d.id,
                    workspace_id=workspace_id,
                    original_filename=d.original_filename,
                    media_type=d.media_type,
                    document_type=meta.document_type if meta else "unknown",
                    title=doc_title,
                    authors=author_names,
                    publication_year=meta.publication_year if meta else None,
                    primary_objective=obj.primary_objective if obj else None,
                    has_metadata=meta is not None,
                    has_objectives=obj is not None,
                    has_methodology=meth is not None,
                    last_analyzed_at=meta.updated_at if meta else None,
                )
            )

        return summaries
