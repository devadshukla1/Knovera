"""Tests for Context Construction, Deduplication, Budgeting, and Selection (Phase 3 C3.5)."""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.workspace import Workspace
from backend.app.rag.context.builder import ContextBuilder
from backend.app.rag.context.deduplicator import EvidenceDeduplicator
from backend.app.rag.context.exceptions import ContextBudgetExceededError
from backend.app.rag.context.schemas import ContextSource
from backend.app.rag.context.selector import EvidenceSelector
from backend.app.rag.context.source_formatter import SourceFormatter
from backend.app.rag.context.token_budget import TokenBudgetCalculator, estimate_tokens
from backend.app.rag.retrieval.schemas import SemanticSearchResult


def test_token_budget_calculator_calculations():
    """Verifies token budget calculation and budget exceeded exception."""
    calc = TokenBudgetCalculator(safety_margin_tokens=250)

    # Context window 8192, reserved 1500, system 400, query 50, history 100, safety 250
    # Available = 8192 - (400 + 50 + 100 + 1500 + 250) = 8192 - 2300 = 5892
    available = calc.calculate_evidence_budget(
        max_context_tokens=8192,
        reserved_output_tokens=1500,
        system_prompt_tokens=400,
        query_tokens=50,
        history_tokens=100,
    )
    assert available == 5892

    # Context window too small to support fixed requirements
    with pytest.raises(ContextBudgetExceededError):
        calc.calculate_evidence_budget(
            max_context_tokens=1000,
            reserved_output_tokens=1500,
            system_prompt_tokens=400,
            query_tokens=50,
        )


def test_evidence_deduplicator():
    """Verifies that duplicate chunk IDs and identical content hashes are removed."""
    dedup = EvidenceDeduplicator()
    ws_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk1_id = uuid.uuid4()
    chunk2_id = uuid.uuid4()

    candidates = [
        SemanticSearchResult(
            chunk_id=chunk1_id,
            document_id=doc_id,
            workspace_id=ws_id,
            document_filename="doc1.pdf",
            content="Unique text on neural networks.",
            distance=0.1,
            rank=1,
            embedding_model="test-model",
            embedding_revision="main",
        ),
        # Duplicate chunk_id
        SemanticSearchResult(
            chunk_id=chunk1_id,
            document_id=doc_id,
            workspace_id=ws_id,
            document_filename="doc1.pdf",
            content="Unique text on neural networks.",
            distance=0.1,
            rank=2,
            embedding_model="test-model",
            embedding_revision="main",
        ),
        # Different chunk_id but identical text
        SemanticSearchResult(
            chunk_id=chunk2_id,
            document_id=doc_id,
            workspace_id=ws_id,
            document_filename="doc1.pdf",
            content="Unique text on neural networks.",
            distance=0.15,
            rank=3,
            embedding_model="test-model",
            embedding_revision="main",
        ),
    ]

    deduped, omitted = dedup.deduplicate(candidates)
    assert len(deduped) == 1
    assert omitted == 2
    assert deduped[0].chunk_id == chunk1_id


def test_evidence_selector_diversity():
    """Verifies EvidenceSelector limits per-document chunks and total chunks."""
    selector = EvidenceSelector(max_chunks=4, max_chunks_per_document=2)
    ws_id = uuid.uuid4()
    doc_a = uuid.uuid4()
    doc_b = uuid.uuid4()

    candidates = [
        # 3 chunks from doc_a
        SemanticSearchResult(chunk_id=uuid.uuid4(), document_id=doc_a, workspace_id=ws_id, document_filename="a.pdf", content="Content A1", distance=0.1, rank=1, embedding_model="m", embedding_revision="r"),
        SemanticSearchResult(chunk_id=uuid.uuid4(), document_id=doc_a, workspace_id=ws_id, document_filename="a.pdf", content="Content A2", distance=0.2, rank=2, embedding_model="m", embedding_revision="r"),
        SemanticSearchResult(chunk_id=uuid.uuid4(), document_id=doc_a, workspace_id=ws_id, document_filename="a.pdf", content="Content A3", distance=0.3, rank=3, embedding_model="m", embedding_revision="r"),
        # 2 chunks from doc_b
        SemanticSearchResult(chunk_id=uuid.uuid4(), document_id=doc_b, workspace_id=ws_id, document_filename="b.pdf", content="Content B1", distance=0.4, rank=4, embedding_model="m", embedding_revision="r"),
        SemanticSearchResult(chunk_id=uuid.uuid4(), document_id=doc_b, workspace_id=ws_id, document_filename="b.pdf", content="Content B2", distance=0.5, rank=5, embedding_model="m", embedding_revision="r"),
    ]

    selected, omitted = selector.select(candidates, evidence_token_budget=5000)
    # max 2 from doc_a + 2 from doc_b = 4 total
    assert len(selected) == 4
    assert omitted == 1
    doc_a_selected = sum(1 for item, _ in selected if item.document_id == doc_a)
    doc_b_selected = sum(1 for item, _ in selected if item.document_id == doc_b)
    assert doc_a_selected == 2
    assert doc_b_selected == 2


def test_source_formatter_multiformat():
    """Verifies source formatting for PDF pages, PPTX slides, and DOCX sections."""
    formatter = SourceFormatter()

    pdf_source = ContextSource(
        source_id="S1",
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        document_name="deep_learning.pdf",
        page_start=5,
        page_end=6,
        content="Backpropagation algorithm propagates gradients backwards.",
        retrieval_rank=1,
    )
    formatted_pdf = formatter.format_single_source(pdf_source)
    assert "SOURCE [S1]" in formatted_pdf
    assert "Document: deep_learning.pdf" in formatted_pdf
    assert "Location: Pages 5–6" in formatted_pdf
    assert "Backpropagation algorithm" in formatted_pdf

    pptx_source = ContextSource(
        source_id="S2",
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        document_name="deck.pptx",
        slide_number=3,
        section_title="Attention Layers",
        content="Self-attention matrices Q, K, and V.",
        retrieval_rank=2,
    )
    formatted_pptx = formatter.format_single_source(pptx_source)
    assert "SOURCE [S2]" in formatted_pptx
    assert "Slide 3" in formatted_pptx
    assert "Section: Attention Layers" in formatted_pptx


def test_context_builder_postgresql_authorization_revalidation(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies that ContextBuilder revalidates chunks in PostgreSQL and filters out soft-deleted docs."""
    builder = ContextBuilder()

    # 1. Create valid document and chunk
    doc_valid = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_workspace.owner_user_id,
        original_filename="valid.pdf",
        storage_key="test/valid.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1000,
        sha256="1" * 64,
        processing_status="ready",
    )
    chunk_valid = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc_valid.id,
        chunk_index=0,
        content="Valid active evidence.",
        content_hash="h1",
        page_start=1,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )

    # 2. Create soft-deleted document and chunk
    doc_deleted = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_workspace.owner_user_id,
        original_filename="deleted.pdf",
        storage_key="test/deleted.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1000,
        sha256="2" * 64,
        processing_status="deleted",
        deleted_at=datetime.now(timezone.utc),
    )
    chunk_deleted = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc_deleted.id,
        chunk_index=0,
        content="Deleted document evidence.",
        content_hash="h2",
        page_start=1,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )

    db_session.add_all([doc_valid, chunk_valid, doc_deleted, chunk_deleted])
    db_session.commit()

    retrieval_candidates = [
        SemanticSearchResult(
            chunk_id=chunk_valid.id,
            document_id=doc_valid.id,
            workspace_id=test_workspace.id,
            document_filename="valid.pdf",
            content=chunk_valid.content,
            distance=0.1,
            rank=1,
            embedding_model="m",
            embedding_revision="r",
        ),
        SemanticSearchResult(
            chunk_id=chunk_deleted.id,
            document_id=doc_deleted.id,
            workspace_id=test_workspace.id,
            document_filename="deleted.pdf",
            content=chunk_deleted.content,
            distance=0.15,
            rank=2,
            embedding_model="m",
            embedding_revision="r",
        ),
        # Non-existent foreign chunk
        SemanticSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            workspace_id=test_workspace.id,
            document_filename="ghost.pdf",
            content="Ghost chunk.",
            distance=0.2,
            rank=3,
            embedding_model="m",
            embedding_revision="r",
        ),
    ]

    package = builder.build_context(
        db=db_session,
        workspace_id=test_workspace.id,
        query="Explain active evidence",
        retrieval_results=retrieval_candidates,
    )

    # Only chunk_valid should survive validation
    assert package.included_source_count == 1
    assert len(package.sources) == 1
    assert package.sources[0].source_id == "S1"
    assert package.sources[0].chunk_id == chunk_valid.id
    assert "S1" in package.source_mapping
    assert package.source_mapping["S1"]["chunk_id"] == str(chunk_valid.id)
    assert package.omitted_source_count == 2
