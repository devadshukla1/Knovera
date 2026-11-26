"""Dedicated abstention policy for Knovera Grounded RAG (Phase 3 C3.7)."""

from typing import List, Optional
import uuid
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.rag.context.schemas import ContextPackage
from backend.app.rag.orchestration.schemas import GroundedAnswerDraft
from backend.app.rag.prompts.version import PROMPT_VERSION

logger = get_logger("knovera.rag.abstention")


class AbstentionPolicy:
    """Enforces evidence-based abstention when information is missing or unverified."""

    @staticmethod
    def workspace_has_active_chunks(db: Session, workspace_id: uuid.UUID) -> bool:
        """Checks if the workspace contains any indexed chunks from active documents."""
        count = (
            db.query(DocumentChunk.id)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(
                DocumentChunk.workspace_id == workspace_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .limit(1)
            .count()
        )
        return count > 0

    @staticmethod
    def build_no_documents_abstention(
        workspace_id: uuid.UUID,
        query: str,
    ) -> GroundedAnswerDraft:
        """Returns structured abstention when the workspace has no indexed documents."""
        logger.info("Workspace %s has no indexed chunks. Returning abstention without LLM call.", workspace_id)
        empty_context = ContextPackage(
            query=query,
            sources=[],
            included_source_count=0,
            omitted_source_count=0,
            available_context_tokens=4096,
            reserved_output_tokens=1500,
            source_mapping={},
        )
        return GroundedAnswerDraft(
            answer=(
                "There are no searchable documents in this workspace yet. "
                "Please upload relevant documents (PDF, DOCX, or PPTX) to begin asking questions."
            ),
            claims=[],
            limitations=["Workspace contains no indexed document evidence."],
            insufficient_evidence=True,
            context_package=empty_context,
            citation_drafts=[],
            model_provider="system_policy",
            model_name="none",
            latency_ms=0,
            prompt_version=PROMPT_VERSION,
            retrieval_metrics={"reason": "no_workspace_documents"},
        )

    @staticmethod
    def build_no_evidence_abstention(
        query: str,
        context_package: ContextPackage,
    ) -> GroundedAnswerDraft:
        """Returns structured abstention when semantic retrieval returned no relevant chunks."""
        logger.info("Retrieval returned zero usable chunks for query '%s'. Returning abstention.", query)
        return GroundedAnswerDraft(
            answer=(
                "The available documents in this workspace do not provide sufficient evidence to answer your question. "
                "Please ensure the relevant documents are uploaded or consider refining your query."
            ),
            claims=[],
            limitations=["No relevant document chunks matched the query with adequate similarity."],
            insufficient_evidence=True,
            context_package=context_package,
            citation_drafts=[],
            model_provider="system_policy",
            model_name="none",
            latency_ms=0,
            prompt_version=PROMPT_VERSION,
            retrieval_metrics={"reason": "insufficient_evidence"},
        )
