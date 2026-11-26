"""End-to-end integration test verifying Cross-Encoder reranking promotes relevant evidence to rank 1 (Phase 4 C4.4–C4.5)."""

import json
from unittest.mock import MagicMock
import uuid
import pytest

from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.rag.orchestration.answer_generator import GroundedAnswerService
from backend.app.rag.reranker.manager import CrossEncoderModelManager
from backend.app.rag.reranker.reranker import CrossEncoderReranker
from backend.app.rag.retrieval.hybrid_retriever import HybridRetriever


class CustomScoringCrossEncoder:
    """Mock Cross-Encoder scoring specifically designed to test reranking inversion."""

    def predict(self, sentences, **kwargs):
        scores = []
        for pair in sentences:
            query, text = pair[0].lower(), pair[1].lower()
            if "raft" in text and "leader" in text:
                scores.append(8.5)  # High relevance for true answer
            else:
                scores.append(-3.2)  # Low relevance for distractor
        return scores


@pytest.mark.asyncio
async def test_e2e_reranking_promotes_relevant_chunk_and_generates_grounded_answer(db_session):
    # Setup test user and workspace
    user = User(
        id=uuid.uuid4(),
        email=f"rerank_tester_{uuid.uuid4().hex[:6]}@knovera.ai",
        password_hash="pw_hash",
        display_name="Rerank Tester",
        status="active",
    )
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name="Distributed Systems Workspace",
    )
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="consensus_protocols.pdf",
        storage_key=f"test/{uuid.uuid4().hex}_consensus.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=2048,
        sha256=f"hash_{uuid.uuid4().hex[:8]}",
        processing_status="ready",
        processing_stage="ready",
    )

    # Chunk A (Distractor): Has high keyword frequency for "consensus algorithm"
    chunk_distractor = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        workspace_id=ws.id,
        chunk_index=0,
        content="General background introduction to distributed algorithm theory and general consensus algorithms.",
        token_count=15,
        token_count_method="estimate_v1",
        parser_version="pdfplumber_v1",
        cleaning_version="v1",
        chunking_version="v1",
        content_hash="h_distractor",
        source_segments=[],
        page_start=1,
        page_end=1,
        section_title="Introduction",
    )

    # Chunk B (True Answer): Authoritative explanation of Raft consensus protocol
    chunk_authoritative = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        workspace_id=ws.id,
        chunk_index=1,
        content="Raft divides consensus into leader election, log replication, and safety guarantees for cluster state machines.",
        token_count=18,
        token_count_method="estimate_v1",
        parser_version="pdfplumber_v1",
        cleaning_version="v1",
        chunking_version="v1",
        content_hash="h_authoritative",
        source_segments=[],
        page_start=5,
        page_end=6,
        section_title="Raft Leader Protocol",
    )

    db_session.add_all([user, ws, doc, chunk_distractor, chunk_authoritative])
    db_session.commit()

    # 1. Setup mock dense retrieval where Distractor initially ranks 1st and Authoritative ranks 2nd
    mock_dense = MagicMock()
    mock_dense.vector_repo.query_nearest.return_value = [
        (str(chunk_distractor.id), 0.10),
        (str(chunk_authoritative.id), 0.35),
    ]

    # 2. Configure Cross-Encoder to accurately score Chunk B higher
    custom_encoder = CustomScoringCrossEncoder()
    CrossEncoderModelManager.get_instance().set_model(custom_encoder)

    retriever = HybridRetriever(semantic_retriever=mock_dense)
    retriever.bm25_retriever.cache.invalidate(ws.id)

    # Execute hybrid retrieval with reranking enabled
    query = "How does Raft elect a leader and replicate logs?"
    response = retriever.retrieve(
        db=db_session,
        workspace_id=ws.id,
        query=query,
        top_k=2,
        mode="hybrid",
        rerank=True,
    )

    # VERIFICATION 1: Cross-Encoder inverted initial order and promoted Chunk B to Rank 1!
    assert response.total_results == 2
    assert response.reranked is True

    top_result = response.results[0]
    assert top_result.chunk_id == chunk_authoritative.id
    assert top_result.rank == 1
    assert top_result.reranker_rank == 1
    assert top_result.reranker_score == 8.5
    assert top_result.section_title == "Raft Leader Protocol"

    second_result = response.results[1]
    assert second_result.chunk_id == chunk_distractor.id
    assert second_result.rank == 2
    assert second_result.reranker_rank == 2
    assert second_result.reranker_score == -3.2

    # 3. VERIFICATION 2: GroundedAnswerService feeds reranked evidence and maps citation
    mock_llm_payload = {
        "answer": "Raft achieves consensus by electing a cluster leader that replicates log entries [S1].",
        "claims": [
            {
                "text": "Raft achieves consensus by electing a cluster leader that replicates log entries.",
                "source_ids": ["S1"],
            }
        ],
        "limitations": [],
        "insufficient_evidence": False,
    }
    mock_provider = MockLLMProvider(default_response=json.dumps(mock_llm_payload))
    LLMManager.get_instance().registry.register("mock", mock_provider)

    answer_service = GroundedAnswerService(retriever=retriever)
    answer_draft = await answer_service.generate_grounded_answer(
        db=db_session,
        workspace_id=ws.id,
        query=query,
        provider_name="mock",
        model_name="mock-model",
    )

    assert not answer_draft.insufficient_evidence
    assert len(answer_draft.citation_drafts) == 1

    citation = answer_draft.citation_drafts[0]
    # S1 must map to the top-ranked authoritative chunk
    assert citation.chunk_id == chunk_authoritative.id
    assert citation.document_name == "consensus_protocols.pdf"
    assert citation.page_start == 5
    assert citation.page_end == 6
