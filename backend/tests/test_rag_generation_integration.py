"""End-to-end integration tests for Knovera Generation Layer (Phase 3 C3.4–C3.6).

Verifies the full pipeline from document retrieval to prompt construction, LLM generation,
and structured answer parsing:
    1. Multi-document retrieval produces ranked candidate chunks.
    2. ContextBuilder validates PostgreSQL provenance, deduplicates, assigns [S1] IDs,
       and constructs ContextPackage.
    3. GeneralQAPrompt renders system instructions, anti-injection <document_evidence> blocks,
       and structured output schemas.
    4. LLMManager generates structured JSON response via registered provider.
    5. StructuredOutputParser validates citation IDs and extracts structured claims.
    6. Cross-workspace chunk injection is rejected by ContextBuilder.
"""

import io
import json
import uuid
import docx
from fastapi.testclient import TestClient
import pymupdf
import pytest
from sqlalchemy.orm import Session

from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.llm.registry import LLMProviderRegistry
from backend.app.llm.schemas import LLMGenerationRequest, MessageRole
from backend.app.models.workspace import Workspace
from backend.app.rag.context.builder import ContextBuilder
from backend.app.rag.context.exceptions import ContextScopeError
from backend.app.rag.prompts.general_qa import GeneralQAPrompt
from backend.app.rag.prompts.parser import StructuredOutputParser
from backend.app.rag.prompts.schemas import PromptInput
from backend.app.rag.retrieval.schemas import SemanticSearchResult
from backend.app.rag.retrieval.semantic_retriever import SemanticRetriever


def make_test_pdf_bytes(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        p = doc.new_page(width=595, height=842)
        p.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_test_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = docx.Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_e2e_retrieval_to_generation_and_parsing(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """Verifies complete flow: Upload -> Search -> Context -> Prompt -> LLM -> Parse."""
    ws_id = test_workspace.id

    # 1. Ingest PDF document
    pdf_bytes = make_test_pdf_bytes([
        "Knowledge retrieval uses dense vector embeddings to find relevant semantic contexts.",
    ])
    res_pdf = test_client.post(
        f"/api/v1/workspaces/{ws_id}/documents",
        headers=auth_headers,
        files={"file": ("retrieval.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res_pdf.status_code == 201

    # 2. Ingest DOCX document
    docx_bytes = make_test_docx_bytes([
        "Cross-Encoder reranking evaluates candidate chunks by scoring query and passage pairs together.",
    ])
    res_docx = test_client.post(
        f"/api/v1/workspaces/{ws_id}/documents",
        headers=auth_headers,
        files={"file": ("reranking.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res_docx.status_code == 201

    # 3. Perform semantic retrieval
    retriever = SemanticRetriever()
    search_response = retriever.retrieve(
        db=db_session,
        workspace_id=ws_id,
        query="dense vector embeddings",
        top_k=4,
    )
    assert search_response.total_results >= 1

    # 4. Context Construction
    builder = ContextBuilder()
    context_package = builder.build_context(
        db=db_session,
        workspace_id=ws_id,
        query="dense vector embeddings",
        retrieval_results=search_response.results,
        max_context_tokens=4096,
    )
    assert context_package.included_source_count >= 1
    assert "S1" in context_package.source_mapping

    # 5. Prompt Engineering
    prompt_renderer = GeneralQAPrompt()
    prompt_input = PromptInput(
        query="How does knowledge retrieval work?",
        context_package=context_package,
    )
    rendered_prompt = prompt_renderer.render(prompt_input)
    assert len(rendered_prompt.messages) == 2
    assert rendered_prompt.messages[0].role == MessageRole.SYSTEM
    assert rendered_prompt.messages[1].role == MessageRole.USER
    assert "<document_evidence>" in rendered_prompt.messages[1].content
    assert "[S1]" in rendered_prompt.messages[1].content

    # 6. LLM Generation via Mock Provider
    mock_answer_json = json.dumps({
        "answer": "Knowledge retrieval relies on dense vector embeddings to locate relevant contexts [S1].",
        "claims": [
            {
                "text": "Knowledge retrieval relies on dense vector embeddings to locate relevant contexts.",
                "source_ids": ["S1"],
            }
        ],
        "limitations": [],
        "insufficient_evidence": False,
    })
    mock_provider = MockLLMProvider(default_response=mock_answer_json)

    registry = LLMProviderRegistry()
    registry.register("mock", mock_provider)
    llm_manager = LLMManager(registry=registry)

    generation_req = LLMGenerationRequest(
        model="mock-model",
        messages=rendered_prompt.messages,
        temperature=0.0,
        response_format="json_object",
    )
    llm_res = await llm_manager.generate_with_retry(generation_req, provider=mock_provider)
    assert llm_res.content == mock_answer_json
    assert llm_res.finish_reason == "stop"

    # 7. Structured Output Parsing & Citation Validation
    parser = StructuredOutputParser()
    parsed_draft = parser.parse(
        raw_completion=llm_res.content,
        valid_source_ids=set(context_package.source_mapping.keys()),
    )
    assert parsed_draft.insufficient_evidence is False
    assert len(parsed_draft.claims) == 1
    assert parsed_draft.claims[0].source_ids == ["S1"]
    assert "[S1]" in parsed_draft.answer


def test_context_builder_rejects_cross_workspace_chunks(
    test_workspace: Workspace,
    db_session: Session,
):
    """Verifies that passing a chunk belonging to another workspace raises ContextScopeError."""
    foreign_ws_id = uuid.uuid4()
    foreign_result = SemanticSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        workspace_id=foreign_ws_id,  # Foreign workspace
        document_filename="leak.pdf",
        content="Confidential foreign data.",
        rank=1,
        distance=0.1,
        embedding_model="test-embed",
        embedding_revision="v1",
    )

    builder = ContextBuilder()
    with pytest.raises(ContextScopeError):
        builder.build_context(
            db=db_session,
            workspace_id=test_workspace.id,
            query="test query",
            retrieval_results=[foreign_result],
        )
