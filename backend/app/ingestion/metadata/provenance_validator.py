"""Provenance and source metadata validator for Knovera Ingestion (Chunk C2.6)."""

from typing import List, Optional
import uuid

from backend.app.ingestion.chunking.schemas import DocumentChunkData
from backend.app.ingestion.extractors.exceptions import ExtractionException
from backend.app.ingestion.schemas.extracted_document import ExtractedDocument


class ProvenanceValidationError(ExtractionException):
    """Raised when chunk provenance or source coordinates fail consistency validation."""

    error_code = "chunk_provenance_invalid"


class ProvenanceValidator:
    """Validates structural integrity and coordinate accuracy of chunks against their source document."""

    def validate_chunks_provenance(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        chunks: List[DocumentChunkData],
        extracted_doc: ExtractedDocument,
    ) -> None:
        """Enforces provenance invariants before committing chunks to the database."""
        if not chunks and extracted_doc.blocks:
            raise ProvenanceValidationError(
                f"Document {document_id} produced 0 chunks despite having {len(extracted_doc.blocks)} extracted blocks."
            )

        file_type = extracted_doc.file_type.lower()
        max_page = extracted_doc.total_pages
        max_slide = extracted_doc.total_slides

        seen_indices = set()

        for chunk in chunks:
            # 1. Identity coherence
            if chunk.document_id != document_id:
                raise ProvenanceValidationError(
                    f"Chunk document_id mismatch: {chunk.document_id} != {document_id}"
                )
            if chunk.workspace_id != workspace_id:
                raise ProvenanceValidationError(
                    f"Chunk workspace_id mismatch: {chunk.workspace_id} != {workspace_id}"
                )

            # 2. Sequence ordering
            if chunk.chunk_index in seen_indices:
                raise ProvenanceValidationError(
                    f"Duplicate chunk_index {chunk.chunk_index} detected in document {document_id}."
                )
            seen_indices.add(chunk.chunk_index)

            # 3. Non-empty content
            if not chunk.content or not chunk.content.strip():
                raise ProvenanceValidationError(
                    f"Chunk index {chunk.chunk_index} contains empty content."
                )

            # 4. Source segments presence
            if not chunk.source_segments:
                raise ProvenanceValidationError(
                    f"Chunk index {chunk.chunk_index} lacks source_segments provenance records."
                )

            # 5. Format-specific coordinate verification
            if file_type == ".pdf":
                if chunk.page_start is not None and chunk.page_start < 1:
                    raise ProvenanceValidationError(
                        f"PDF chunk {chunk.chunk_index} has invalid page_start: {chunk.page_start} (must be >= 1)."
                    )
                if chunk.page_end is not None and chunk.page_start is not None:
                    if chunk.page_end < chunk.page_start:
                        raise ProvenanceValidationError(
                            f"PDF chunk {chunk.chunk_index} has page_end ({chunk.page_end}) < page_start ({chunk.page_start})."
                        )
                if max_page and chunk.page_start and chunk.page_start > max_page:
                    raise ProvenanceValidationError(
                        f"PDF chunk {chunk.chunk_index} page_start ({chunk.page_start}) exceeds max page count ({max_page})."
                    )

            elif file_type == ".pptx":
                if chunk.slide_number is not None and chunk.slide_number < 1:
                    raise ProvenanceValidationError(
                        f"PPTX chunk {chunk.chunk_index} has invalid slide_number: {chunk.slide_number} (must be >= 1)."
                    )
                if max_slide and chunk.slide_number and chunk.slide_number > max_slide:
                    raise ProvenanceValidationError(
                        f"PPTX chunk {chunk.chunk_index} slide_number ({chunk.slide_number}) exceeds slide count ({max_slide})."
                    )

            elif file_type == ".docx":
                # For DOCX, ensure at least one segment has paragraph, table, or section info
                has_docx_coord = any(
                    seg.section_title or seg.paragraph_index is not None or seg.table_index is not None
                    for seg in chunk.source_segments
                )
                if not has_docx_coord:
                    raise ProvenanceValidationError(
                        f"DOCX chunk {chunk.chunk_index} lacks section, paragraph, or table provenance."
                    )

            elif file_type in (".txt", ".md"):
                # For plain text and Markdown, ensure at least one segment has paragraph or block info
                has_txt_coord = any(
                    seg.section_title or seg.paragraph_index is not None or seg.block_index is not None
                    for seg in chunk.source_segments
                )
                if not has_txt_coord:
                    raise ProvenanceValidationError(
                        f"Text chunk {chunk.chunk_index} lacks paragraph or block provenance."
                    )
