"""Context Builder assembling verified evidence into ContextPackage (Phase 3 C3.5)."""

from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.rag.context.deduplicator import EvidenceDeduplicator
from backend.app.rag.context.exceptions import ContextScopeError
from backend.app.rag.context.schemas import ContextPackage, ContextSource
from backend.app.rag.context.selector import EvidenceSelector
from backend.app.rag.context.token_budget import TokenBudgetCalculator, estimate_tokens
from backend.app.rag.retrieval.schemas import SemanticSearchResult

logger = get_logger("knovera.rag.context.builder")


class ContextBuilder:
    """Assembles authorized, deduplicated, and budgeted evidence chunks for LLM generation."""

    def __init__(
        self,
        deduplicator: Optional[EvidenceDeduplicator] = None,
        selector: Optional[EvidenceSelector] = None,
        budget_calculator: Optional[TokenBudgetCalculator] = None,
    ) -> None:
        self.settings = get_settings()
        self.deduplicator = deduplicator or EvidenceDeduplicator()
        self.selector = selector or EvidenceSelector(
            max_chunks=self.settings.CONTEXT_MAX_CHUNKS,
            max_chunks_per_document=self.settings.CONTEXT_MAX_CHUNKS_PER_DOCUMENT,
        )
        self.budget_calculator = budget_calculator or TokenBudgetCalculator(
            safety_margin_tokens=self.settings.CONTEXT_SAFETY_MARGIN_TOKENS
        )

    def build_context(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        query: str,
        retrieval_results: List[SemanticSearchResult],
        max_context_tokens: int = 8192,
        reserved_output_tokens: int = 1500,
        system_prompt_tokens: int = 400,
        conversation_history_tokens: int = 0,
    ) -> ContextPackage:
        """Executes full context construction pipeline with strict authorization revalidation.

        Returns:
            ContextPackage ready for prompt template rendering.
        """
        warnings: List[str] = []

        # 1. Authoritative PostgreSQL revalidation
        valid_candidates: List[SemanticSearchResult] = []
        if retrieval_results:
            for r in retrieval_results:
                if r.workspace_id != workspace_id:
                    raise ContextScopeError(
                        f"Cross-workspace security breach detected: chunk {r.chunk_id} belongs to "
                        f"workspace {r.workspace_id}, but context is requested for workspace {workspace_id}."
                    )

            chunk_ids = [r.chunk_id for r in retrieval_results]
            # Join chunks and documents verifying workspace and non-deleted status
            db_records = (
                db.query(DocumentChunk.id, Document.id, Document.original_filename)
                .join(Document, DocumentChunk.document_id == Document.id)
                .filter(
                    DocumentChunk.id.in_(chunk_ids),
                    DocumentChunk.workspace_id == workspace_id,
                    Document.workspace_id == workspace_id,
                    Document.deleted_at.is_(None),
                )
                .all()
            )
            valid_chunk_map = {row[0]: row[2] for row in db_records}

            for r in retrieval_results:
                if r.chunk_id in valid_chunk_map:
                    # Sync filename from PostgreSQL
                    valid_candidates.append(r.model_copy(update={"document_filename": valid_chunk_map[r.chunk_id]}))
                else:
                    warnings.append(f"Excluded chunk {r.chunk_id}: failed PostgreSQL workspace or active status verification")

        # 2. Deduplicate evidence
        deduped_candidates, dedup_omitted = self.deduplicator.deduplicate(valid_candidates)
        if dedup_omitted > 0:
            warnings.append(f"Deduplicated {dedup_omitted} duplicate or identical-content chunk(s)")

        # 3. Calculate net available evidence budget
        query_tokens = estimate_tokens(query)
        available_evidence_tokens = self.budget_calculator.calculate_evidence_budget(
            max_context_tokens=max_context_tokens,
            reserved_output_tokens=reserved_output_tokens,
            system_prompt_tokens=system_prompt_tokens,
            query_tokens=query_tokens,
            history_tokens=conversation_history_tokens,
        )

        # 4. Select candidates under diversity and budget constraints
        selected_pairs, select_omitted = self.selector.select(
            candidates=deduped_candidates,
            evidence_token_budget=available_evidence_tokens,
        )
        total_omitted = (len(retrieval_results) - len(valid_candidates)) + dedup_omitted + select_omitted

        # 5. Assign prompt-local source IDs ([S1], [S2], ...) and build source mapping
        sources: List[ContextSource] = []
        source_mapping: Dict[str, Dict[str, Any]] = {}
        total_estimated_tokens = 0

        for idx, (candidate, is_truncated) in enumerate(selected_pairs, start=1):
            source_id = f"S{idx}"
            source_obj = ContextSource(
                source_id=source_id,
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                workspace_id=candidate.workspace_id,
                document_name=candidate.document_filename,
                page_start=candidate.page_start,
                page_end=candidate.page_end,
                slide_number=candidate.slide_number,
                section_title=candidate.section_title,
                content=candidate.content,
                retrieval_rank=candidate.rank,
                retrieval_distance=candidate.distance,
                is_truncated=is_truncated,
                source_segments=candidate.source_segments,
            )
            sources.append(source_obj)
            total_estimated_tokens += estimate_tokens(candidate.content)

            source_mapping[source_id] = {
                "source_id": source_id,
                "chunk_id": str(candidate.chunk_id),
                "document_id": str(candidate.document_id),
                "workspace_id": str(candidate.workspace_id),
                "document_name": candidate.document_filename,
                "page_start": candidate.page_start,
                "page_end": candidate.page_end,
                "slide_number": candidate.slide_number,
                "section_title": candidate.section_title,
                "retrieval_rank": candidate.rank,
                "retrieval_distance": candidate.distance,
                "is_truncated": is_truncated,
            }

        logger.info(
            "Built context for workspace %s: %d sources included, %d omitted, estimated tokens: %d",
            workspace_id,
            len(sources),
            total_omitted,
            total_estimated_tokens,
        )

        return ContextPackage(
            query=query,
            sources=sources,
            included_source_count=len(sources),
            omitted_source_count=total_omitted,
            estimated_input_tokens=total_estimated_tokens,
            available_context_tokens=available_evidence_tokens,
            reserved_output_tokens=reserved_output_tokens,
            context_version="context-v1",
            warnings=warnings,
            source_mapping=source_mapping,
        )
