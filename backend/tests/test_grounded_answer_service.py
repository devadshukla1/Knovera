"""Tests for Grounded Answer Generation Service and Abstention Policy (Phase 3 C3.7)."""

import json
import uuid
import pytest
from sqlalchemy.orm import Session

from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.llm.registry import LLMProviderRegistry
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.workspace import Workspace
from backend.app.rag.orchestration.abstention import AbstentionPolicy
from backend.app.rag.orchestration.answer_generator import GroundedAnswerService


def create_test_chunk(
    db: Session,
    workspace: Workspace,
    content: str,
    page_start: int = 1,
    page_end: int = 1,
    doc_name: str = "deep_learning.pdf",
    ext: str = ".pdf",
) -> DocumentChunk:
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        uploaded_by_user_id=workspace.owner_user_id,
        original_filename=doc_name,
        storage_key=f"test/{uuid.uuid4().hex[:12]}_{doc_name}",
        media_type="application/pdf" if ext == ".pdf" else "application/vnd.openxmlformats",
        file_extension=ext,
        file_size_bytes=1000,
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        processing_status="ready",
    )
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        document_id=doc.id,
        chunk_index=0,
        content=content,
        content_hash=uuid.uuid4().hex,
        page_start=page_start,
        page_end=page_end,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    db.add_all([doc, chunk])
    db.commit()
    db.refresh(chunk)
    return chunk


@pytest.mark.asyncio
async def test_empty_workspace_abstains_without_calling_llm(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies that an empty workspace immediately returns abstention without invoking the LLM."""
    mock_provider = MockLLMProvider()
    registry = LLMProviderRegistry()
    registry.register("mock", mock_provider)
    llm_manager = LLMManager(registry=registry)

    service = GroundedAnswerService(llm_manager=llm_manager)
    draft = await service.generate_grounded_answer(
        db=db_session,
        workspace_id=test_workspace.id,
        query="What is supervised learning?",
    )

    assert draft.insufficient_evidence is True
    assert "no searchable documents" in draft.answer.lower()
    assert len(mock_provider.call_history) == 0  # LLM was NEVER called!
    assert len(draft.citation_drafts) == 0


@pytest.mark.asyncio
async def test_no_retrieval_match_abstains_without_calling_llm(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies that when vector retrieval finds no relevant chunks, abstention is returned without LLM call."""
    # Seed an unrelated chunk
    create_test_chunk(db_session, test_workspace, "Cooking recipe for chocolate cake.")

    mock_provider = MockLLMProvider()
    registry = LLMProviderRegistry()
    registry.register("mock", mock_provider)
    llm_manager = LLMManager(registry=registry)

    # Use a mock retriever that returns 0 results
    class EmptyRetriever:
        def retrieve(self, *args, **kwargs):
            from backend.app.rag.retrieval.schemas import SemanticSearchResponse
            return SemanticSearchResponse(
                workspace_id=test_workspace.id,
                query="Quantum physics",
                total_results=0,
                results=[],
            )

    service = GroundedAnswerService(retriever=EmptyRetriever(), llm_manager=llm_manager)
    draft = await service.generate_grounded_answer(
        db=db_session,
        workspace_id=test_workspace.id,
        query="Quantum physics teleportation",
    )

    assert draft.insufficient_evidence is True
    assert "not provide sufficient evidence" in draft.answer.lower()
    assert len(mock_provider.call_history) == 0  # LLM was NEVER called!


@pytest.mark.asyncio
async def test_grounded_answer_single_source(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies complete grounded answer generation for a single supporting source chunk."""
    chunk = create_test_chunk(
        db_session,
        test_workspace,
        "Supervised learning trains models on labelled datasets where input features map to ground truth targets.",
        page_start=12,
        page_end=13,
    )

    # Mock provider returning valid JSON referencing S1
    mock_response = json.dumps({
        "answer": "Supervised learning relies on labelled datasets to train predictive models [S1].",
        "claims": [
            {
                "text": "Supervised learning relies on labelled datasets to train predictive models.",
                "source_ids": ["S1"],
            }
        ],
        "limitations": [],
        "insufficient_evidence": False,
    })
    mock_provider = MockLLMProvider(default_response=mock_response)
    registry = LLMProviderRegistry()
    registry.register("mock", mock_provider)
    llm_manager = LLMManager(registry=registry)

    # Retriever returning the chunk
    class SingleChunkRetriever:
        def retrieve(self, *args, **kwargs):
            from backend.app.rag.retrieval.schemas import SemanticSearchResponse, SemanticSearchResult
            return SemanticSearchResponse(
                workspace_id=test_workspace.id,
                query="What is supervised learning?",
                total_results=1,
                results=[
                    SemanticSearchResult(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        workspace_id=test_workspace.id,
                        document_filename="deep_learning.pdf",
                        content=chunk.content,
                        distance=0.08,
                        rank=1,
                        embedding_model="mock",
                        embedding_revision="v1",
                        page_start=12,
                        page_end=13,
                    )
                ],
            )

    service = GroundedAnswerService(retriever=SingleChunkRetriever(), llm_manager=llm_manager)
    draft = await service.generate_grounded_answer(
        db=db_session,
        workspace_id=test_workspace.id,
        query="What is supervised learning?",
    )

    assert draft.insufficient_evidence is False
    assert "[S1]" in draft.answer
    assert len(draft.citation_drafts) == 1
    citation = draft.citation_drafts[0]
    assert citation.chunk_id == chunk.id
    assert citation.page_start == 12
    assert citation.page_end == 13
    assert citation.location_label == "Pages 12–13"
    assert citation.document_name == "deep_learning.pdf"


@pytest.mark.asyncio
async def test_grounded_answer_multi_source_and_conflicts(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies generation with multiple sources and preserved claim attribution."""
    chunk1 = create_test_chunk(db_session, test_workspace, "Study A claims that learning rate 0.01 is optimal.")
    chunk2 = create_test_chunk(db_session, test_workspace, "Study B argues that learning rate 0.001 achieves higher stability.")

    mock_response = json.dumps({
        "answer": "The sources report conflicting values: Study A recommends 0.01 [S1], whereas Study B recommends 0.001 [S2].",
        "claims": [
            {"text": "Study A recommends learning rate 0.01.", "source_ids": ["S1"]},
            {"text": "Study B recommends learning rate 0.001.", "source_ids": ["S2"]},
        ],
        "limitations": ["Sources present conflicting optimal hyperparameters."],
        "insufficient_evidence": False,
    })
    mock_provider = MockLLMProvider(default_response=mock_response)
    registry = LLMProviderRegistry()
    registry.register("mock", mock_provider)
    llm_manager = LLMManager(registry=registry)

    class MultiChunkRetriever:
        def retrieve(self, *args, **kwargs):
            from backend.app.rag.retrieval.schemas import SemanticSearchResponse, SemanticSearchResult
            return SemanticSearchResponse(
                workspace_id=test_workspace.id,
                query="optimal learning rate",
                total_results=2,
                results=[
                    SemanticSearchResult(
                        chunk_id=chunk1.id,
                        document_id=chunk1.document_id,
                        workspace_id=test_workspace.id,
                        document_filename="deep_learning.pdf",
                        content=chunk1.content,
                        distance=0.05,
                        rank=1,
                        embedding_model="mock",
                        embedding_revision="v1",
                    ),
                    SemanticSearchResult(
                        chunk_id=chunk2.id,
                        document_id=chunk2.document_id,
                        workspace_id=test_workspace.id,
                        document_filename="deep_learning.pdf",
                        content=chunk2.content,
                        distance=0.07,
                        rank=2,
                        embedding_model="mock",
                        embedding_revision="v1",
                    ),
                ],
            )

    service = GroundedAnswerService(retriever=MultiChunkRetriever(), llm_manager=llm_manager)
    draft = await service.generate_grounded_answer(
        db=db_session,
        workspace_id=test_workspace.id,
        query="What is the optimal learning rate?",
    )

    assert draft.insufficient_evidence is False
    assert len(draft.citation_drafts) == 2
    assert len(draft.limitations) == 1
    assert "conflicting" in draft.limitations[0].lower()
