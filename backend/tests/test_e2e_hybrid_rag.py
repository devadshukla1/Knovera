"""End-to-end integration tests for Hybrid Retrieval (Dense + BM25 + RRF) and Grounded Answering (Phase 4)."""

import json
import uuid
import pytest

from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.rag.orchestration.answer_generator import GroundedAnswerService
from backend.app.rag.retrieval.hybrid_retriever import HybridRetriever


@pytest.mark.asyncio
async def test_e2e_hybrid_rag_with_exact_lexical_keyword(db_session):
    # Setup test user, workspace, and documents
    user = User(
        id=uuid.uuid4(),
        email=f"hybrid_rag_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hash",
        display_name="RAG Tester",
        status="active",
    )
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name="Hybrid RAG Workspace",
    )
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="networking_protocols.pdf",
        storage_key=f"test/{uuid.uuid4().hex}_net.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=4096,
        sha256=f"hash_{uuid.uuid4().hex[:8]}",
        processing_status="ready",
        processing_stage="ready",
    )
    # Target chunk with specific acronym and technical terms
    c1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        workspace_id=ws.id,
        chunk_index=0,
        content=(
            "The Transmission Control Protocol (TCP) provides reliable, ordered, and error-checked "
            "delivery of a stream of octets between applications running on hosts communicating via an IP network. "
            "Major internet applications such as the World Wide Web rely on TCP/IP."
        ),
        token_count=45,
        token_count_method="estimate_v1",
        parser_version="pdfplumber_v1",
        cleaning_version="v1",
        chunking_version="v1",
        content_hash="chash_net1",
        source_segments=[{"page_number": 3, "text": "TCP/IP networking"}],
        page_start=3,
        page_end=3,
    )
    db_session.add_all([user, ws, doc, c1])
    db_session.commit()

    # Configure Mock LLM Provider to return structured answer citing [S1]
    mock_payload = {
        "answer": "TCP/IP ensures reliable and ordered packet delivery across computer networks [S1].",
        "claims": [
            {
                "text": "TCP/IP ensures reliable and ordered packet delivery across computer networks.",
                "source_ids": ["S1"],
            }
        ],
        "limitations": [],
        "insufficient_evidence": False,
    }
    mock_provider = MockLLMProvider(
        default_response=json.dumps(mock_payload),
    )
    LLMManager.get_instance().registry.register("mock", mock_provider)

    # Initialize HybridRetriever and GroundedAnswerService
    hybrid_retriever = HybridRetriever()
    hybrid_retriever.bm25_retriever.cache.invalidate(ws.id)

    service = GroundedAnswerService(retriever=hybrid_retriever)

    # Execute grounded answering for query targeting TCP/IP
    answer_draft = await service.generate_grounded_answer(
        db=db_session,
        workspace_id=ws.id,
        query="Explain TCP/IP reliable delivery",
        provider_name="mock",
        model_name="mock-model",
    )

    # Verifications
    assert not answer_draft.insufficient_evidence
    assert "reliable" in answer_draft.answer
    assert len(answer_draft.claims) == 1
    assert answer_draft.claims[0].source_ids == ["S1"]

    # Verify citation mapping to authoritative PostgreSQL page provenance
    assert len(answer_draft.citation_drafts) == 1
    cit = answer_draft.citation_drafts[0]
    assert cit.chunk_id == c1.id
    assert cit.document_id == doc.id
    assert cit.document_name == "networking_protocols.pdf"
    assert cit.page_start == 3
    assert cit.page_end == 3
