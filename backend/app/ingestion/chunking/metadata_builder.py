"""Metadata and provenance builder for semantic chunks."""

from datetime import datetime, timezone
import hashlib
from typing import List, Optional
import uuid

from backend.app.ingestion.chunking.schemas import ChunkSegment, DocumentChunkData
from backend.app.ingestion.chunking.token_counter import TokenCounter
from backend.app.ingestion.cleaning.schemas import NormalisedBlock


class ChunkMetadataBuilder:
    """Constructs stable IDs, content hashes, and detailed provenance mappings for chunks."""

    def __init__(self, token_counter: TokenCounter, chunking_version: str = "semantic-v1") -> None:
        self.token_counter = token_counter
        self.chunking_version = chunking_version

    def build_chunk(
        self,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_index: int,
        content: str,
        contributing_blocks: List[NormalisedBlock],
        parser_version: str,
        cleaning_version: str,
    ) -> DocumentChunkData:
        """Assembles a verified DocumentChunkData object with source provenance and deterministic ID."""
        clean_content = content.strip()

        # 1. SHA-256 Content Hash
        content_hash = hashlib.sha256(clean_content.encode("utf-8")).hexdigest()

        # 2. Deterministic UUID5 based on document, version, index, and hash
        seed = f"{document_id}:{self.chunking_version}:{chunk_index}:{content_hash}"
        chunk_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, seed)

        # 3. Provenance segments & coordinates
        segments: List[ChunkSegment] = []
        page_numbers: List[int] = []
        slide_numbers: List[int] = []
        section_titles: List[str] = []

        for b in contributing_blocks:
            if b.page_number:
                page_numbers.append(b.page_number)
            if b.slide_number:
                slide_numbers.append(b.slide_number)
            if b.section_title and b.section_title not in section_titles:
                section_titles.append(b.section_title)

            segments.append(
                ChunkSegment(
                    source_type=b.source_type,
                    block_index=b.block_index,
                    page_number=b.page_number,
                    slide_number=b.slide_number,
                    section_title=b.section_title,
                    paragraph_index=b.paragraph_index,
                    table_index=b.table_index,
                    start_offset=b.source_start_offset,
                    end_offset=b.source_end_offset,
                )
            )

        page_start = min(page_numbers) if page_numbers else None
        page_end = max(page_numbers) if page_numbers else None
        slide_number = slide_numbers[0] if slide_numbers else None
        section_title = section_titles[0] if section_titles else None

        token_count = self.token_counter.count_tokens(clean_content)

        return DocumentChunkData(
            id=chunk_uuid,
            workspace_id=workspace_id,
            document_id=document_id,
            chunk_index=chunk_index,
            content=clean_content,
            content_hash=content_hash,
            page_start=page_start,
            page_end=page_end,
            slide_number=slide_number,
            section_title=section_title,
            source_start_offset=None,
            source_end_offset=None,
            token_count=token_count,
            token_count_method=self.token_counter.method_name,
            parser_version=parser_version,
            cleaning_version=cleaning_version,
            chunking_version=self.chunking_version,
            source_segments=segments,
            created_at=datetime.now(timezone.utc),
        )
