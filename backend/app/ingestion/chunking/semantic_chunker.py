"""Structure-aware semantic chunking engine for Knovera."""

from typing import List, Optional, Tuple
import uuid

from backend.app.core.config import get_settings
from backend.app.ingestion.chunking.boundary_detector import SentenceBoundaryDetector
from backend.app.ingestion.chunking.metadata_builder import ChunkMetadataBuilder
from backend.app.ingestion.chunking.overlap_manager import OverlapManager
from backend.app.ingestion.chunking.schemas import (
    ChunkingDiagnostics,
    DocumentChunkData,
)
from backend.app.ingestion.chunking.token_counter import (
    EstimateTokenCounter,
    TokenCounter,
)
from backend.app.ingestion.cleaning.boilerplate import clean_text_of_noise
from backend.app.ingestion.cleaning.schemas import NormalisedBlock, NormalisedDocument


class SemanticChunker:
    """Structure-aware, content-aware semantic chunker preserving document hierarchy and source provenance."""

    def __init__(
        self,
        target_tokens: Optional[int] = None,
        max_tokens: Optional[int] = None,
        min_tokens: Optional[int] = None,
        overlap_tokens: Optional[int] = None,
        chunking_version: str = "semantic-v1",
        token_counter: Optional[TokenCounter] = None,
    ) -> None:
        settings = get_settings()
        self.target_tokens = target_tokens or getattr(settings, "CHUNK_TARGET_TOKENS", 500)
        self.max_tokens = max_tokens or getattr(settings, "CHUNK_MAX_TOKENS", 700)
        self.min_tokens = min_tokens or getattr(settings, "CHUNK_MIN_TOKENS", 80)
        self.overlap_tokens = overlap_tokens or getattr(settings, "CHUNK_OVERLAP_TOKENS", 75)
        self.chunking_version = getattr(settings, "CHUNKING_VERSION", chunking_version)

        self.token_counter = token_counter or EstimateTokenCounter()
        self.sentence_detector = SentenceBoundaryDetector()
        self.overlap_manager = OverlapManager(
            target_overlap_tokens=self.overlap_tokens,
            token_counter=self.token_counter,
        )
        self.metadata_builder = ChunkMetadataBuilder(
            token_counter=self.token_counter,
            chunking_version=self.chunking_version,
        )

    def _split_large_table(
        self, table_block: NormalisedBlock
    ) -> List[Tuple[str, List[NormalisedBlock]]]:
        """Splits an oversized table at row boundaries, repeating column headers on subsequent chunks."""
        lines = table_block.text.split("\n")
        if len(lines) <= 3:
            return [(table_block.text, [table_block])]

        # Identify header line and separator line if present
        header_lines = []
        data_lines = []
        for i, line in enumerate(lines):
            if i < 2 and ("|" in line or "Table" in line or "---" in line):
                header_lines.append(line)
            else:
                data_lines.append(line)

        header_prefix = "\n".join(header_lines) + "\n" if header_lines else ""
        sub_tables: List[Tuple[str, List[NormalisedBlock]]] = []

        current_rows: List[str] = []
        current_tokens = self.token_counter.count_tokens(header_prefix)

        for row in data_lines:
            row_tokens = self.token_counter.count_tokens(row)
            if current_rows and (current_tokens + row_tokens > self.max_tokens):
                # Flush table chunk
                table_text = (header_prefix + "\n".join(current_rows)).strip()
                sub_tables.append((table_text, [table_block]))
                current_rows = [row]
                current_tokens = self.token_counter.count_tokens(header_prefix) + row_tokens
            else:
                current_rows.append(row)
                current_tokens += row_tokens

        if current_rows:
            table_text = (header_prefix + "\n".join(current_rows)).strip()
            sub_tables.append((table_text, [table_block]))

        return sub_tables if sub_tables else [(table_block.text, [table_block])]

    def chunk_document(
        self,
        document: NormalisedDocument,
        workspace_id: uuid.UUID,
    ) -> Tuple[List[DocumentChunkData], ChunkingDiagnostics]:
        """Divides a NormalisedDocument into semantically coherent, bounded chunks with source provenance."""
        if not document.blocks:
            diag = ChunkingDiagnostics(
                total_extracted_blocks=0,
                total_normalised_characters=0,
                chunk_count=0,
                min_token_count=0,
                max_token_count=0,
                avg_token_count=0.0,
                empty_chunk_count=0,
                target_token_budget=self.target_tokens,
                max_token_budget=self.max_tokens,
                overlap_token_budget=self.overlap_tokens,
                chunking_version=self.chunking_version,
                warnings=["Document contains no blocks to chunk."],
            )
            return [], diag

        doc_id = document.document_id or uuid.uuid4()
        is_pptx = document.file_type == ".pptx"

        chunks: List[DocumentChunkData] = []
        chunk_idx = 0

        # Accumulated chunk state
        current_texts: List[str] = []
        current_blocks: List[NormalisedBlock] = []
        current_tokens = 0
        last_chunk_sentences: List[str] = []
        last_section: Optional[str] = None
        current_slide_num: Optional[int] = None

        def flush_current_chunk() -> None:
            nonlocal chunk_idx, current_texts, current_blocks, current_tokens, last_chunk_sentences, last_section
            if not current_texts:
                return

            full_chunk_text = "\n\n".join(current_texts).strip()
            full_chunk_text = clean_text_of_noise(full_chunk_text)
            if not full_chunk_text or len(full_chunk_text.strip()) < 5:
                current_texts = []
                current_blocks = []
                current_tokens = 0
                return

            # Extract sentences from flushed chunk for next overlap
            sentences_in_chunk = self.sentence_detector.split_sentences(full_chunk_text)
            last_chunk_sentences = sentences_in_chunk
            last_section = current_blocks[0].section_title if current_blocks else None

            chunk_data = self.metadata_builder.build_chunk(
                workspace_id=workspace_id,
                document_id=doc_id,
                chunk_index=chunk_idx,
                content=full_chunk_text,
                contributing_blocks=current_blocks,
                parser_version=document.parser_version,
                cleaning_version=document.cleaning_metadata.cleaning_version,
            )
            chunks.append(chunk_data)
            chunk_idx += 1

            # Reset accumulated state
            current_texts = []
            current_blocks = []
            current_tokens = 0

        for block in document.blocks:
            # PPTX boundary rule: Keep chunk within single slide unless slide is huge
            if is_pptx and block.slide_number is not None:
                if current_slide_num is not None and block.slide_number != current_slide_num:
                    flush_current_chunk()
                    last_chunk_sentences = []  # Reset overlap across distinct slides
                current_slide_num = block.slide_number

            # Handle Table blocks
            if block.block_type == "table":
                table_token_count = self.token_counter.count_tokens(block.text)
                if table_token_count > self.max_tokens:
                    # Oversized table: flush prior content, then split table at row boundaries
                    flush_current_chunk()
                    for sub_text, sub_blocks in self._split_large_table(block):
                        current_texts = [sub_text]
                        current_blocks = sub_blocks
                        flush_current_chunk()
                    continue
                elif current_tokens + table_token_count > self.target_tokens and current_texts:
                    # Flush prior paragraphs before starting table
                    flush_current_chunk()

            # Heading block: flush prior content if heading starts new major section
            if block.block_type == "heading" and current_tokens >= self.min_tokens:
                flush_current_chunk()

            # Prepend overlap if starting a fresh chunk
            if not current_texts and last_chunk_sentences and self.overlap_tokens > 0:
                overlap_text = self.overlap_manager.get_sentence_overlap(
                    sentences=last_chunk_sentences,
                    previous_section=last_section,
                    next_section=block.section_title,
                )
                if overlap_text:
                    overlap_tokens = self.token_counter.count_tokens(overlap_text)
                    current_texts.append(overlap_text)
                    current_tokens += overlap_tokens

            block_text = block.text
            block_tokens = self.token_counter.count_tokens(block_text)

            # Check if block fits within current chunk
            if current_tokens + block_tokens <= self.target_tokens:
                current_texts.append(block_text)
                current_blocks.append(block)
                current_tokens += block_tokens

            elif current_tokens + block_tokens <= self.max_tokens:
                # Still within max upper bound
                current_texts.append(block_text)
                current_blocks.append(block)
                current_tokens += block_tokens
                # Trigger flush as target is reached
                flush_current_chunk()

            else:
                # Exceeds max tokens: if block is a paragraph, split by sentences
                if block.block_type in ("paragraph", "page_text", "shape_text"):
                    sentences = self.sentence_detector.split_sentences(block_text)
                    for sentence in sentences:
                        s_tokens = self.token_counter.count_tokens(sentence)
                        if current_tokens + s_tokens > self.max_tokens and current_texts:
                            flush_current_chunk()

                        current_texts.append(sentence)
                        if block not in current_blocks:
                            current_blocks.append(block)
                        current_tokens += s_tokens

                        if current_tokens >= self.target_tokens:
                            flush_current_chunk()
                else:
                    # Flush prior and put atomic block in its own chunk
                    flush_current_chunk()
                    current_texts.append(block_text)
                    current_blocks.append(block)
                    current_tokens += block_tokens
                    if current_tokens >= self.target_tokens:
                        flush_current_chunk()

        # Flush any remaining accumulated text
        flush_current_chunk()

        # Build quality diagnostics
        total_norm_chars = sum(len(c.content) for c in chunks)
        token_counts = [c.token_count for c in chunks] if chunks else [0]
        min_tok = min(token_counts) if chunks else 0
        max_tok = max(token_counts) if chunks else 0
        avg_tok = round(sum(token_counts) / len(token_counts), 2) if chunks else 0.0

        diagnostics = ChunkingDiagnostics(
            total_extracted_blocks=len(document.blocks),
            total_normalised_characters=total_norm_chars,
            chunk_count=len(chunks),
            min_token_count=min_tok,
            max_token_count=max_tok,
            avg_token_count=avg_tok,
            empty_chunk_count=0,
            target_token_budget=self.target_tokens,
            max_token_budget=self.max_tokens,
            overlap_token_budget=self.overlap_tokens,
            chunking_version=self.chunking_version,
            warnings=[],
        )

        return chunks, diagnostics
