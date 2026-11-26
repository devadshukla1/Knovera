"""Unified document processing orchestrator for Knovera Ingestion (Phase 2 C2.1–C2.8).

Delegates to the 8-stage DocumentProcessingPipeline.
"""

from typing import Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.ingestion.chunking.schemas import ChunkingDiagnostics
from backend.app.ingestion.chunking.semantic_chunker import SemanticChunker
from backend.app.ingestion.cleaning.normalizer import TextNormalizer
from backend.app.ingestion.pipeline.orchestrator import DocumentProcessingPipeline
from backend.app.ingestion.schemas.extracted_document import ExtractedDocument
from backend.app.models.document import Document
from backend.app.storage.base import StorageService


class DocumentProcessingService:
    """Unified coordinator for extraction, normalisation, and semantic chunking."""

    def __init__(
        self,
        normalizer: Optional[TextNormalizer] = None,
        chunker: Optional[SemanticChunker] = None,
    ) -> None:
        self.normalizer = normalizer or TextNormalizer()
        self.chunker = chunker or SemanticChunker()
        self.pipeline = DocumentProcessingPipeline(
            normalizer=self.normalizer,
            chunker=self.chunker,
        )

    def process_document(
        self,
        db: Session,
        document: Document,
        storage: StorageService,
    ) -> Tuple[ExtractedDocument, ChunkingDiagnostics]:
        """Runs the complete end-to-end 8-stage processing pipeline on a stored document.

        Guarantees:
            - Processing status flows: extracting -> chunking -> queued (stage: awaiting_embeddings).
            - Documents are NEVER set to 'ready' during Phase 2.
            - Reprocessing is idempotent: existing pages and chunks are replaced cleanly.
            - Transactional rollback on error with document status marked 'failed'.
        """
        extracted_doc, diagnostics, _ = self.pipeline.process_document(
            db=db,
            document=document,
            storage=storage,
        )
        return extracted_doc, diagnostics
