"""API integration tests for Research Intelligence endpoints (Phase 10 C10.1 - C10.3)."""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


@pytest.fixture
def sample_academic_doc(db_session: Session, test_workspace: Workspace, test_user: User):
    """Creates a processed academic document with chunks for API testing."""
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="attention_is_all_you_need.pdf",
        storage_key=f"ws-{test_workspace.id}/docs/attention.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=2048000,
        sha256="a" * 64,
        processing_status="completed",
        page_count=15,
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "Attention Is All You Need Preprint"},
    )
    db_session.add(doc)
    db_session.flush()

    chunk_0 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        content=(
            "Attention Is All You Need\n"
            "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin\n"
            "Google Brain, Google Research\n"
            "arXiv:1706.03762v5 [cs.CL] 6 Dec 2017\n"
            "DOI: 10.48550/arXiv.1706.03762\n\n"
            "Abstract: The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. "
            "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms."
        ),
        content_hash="att_chunk0",
        page_start=1,
        page_end=1,
        section_title="Abstract",
        token_count=120,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )

    chunk_1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=1,
        content=(
            "1. Introduction\n"
            "Recurrent neural networks, long short-term memory and gated recurrent neural networks in particular, "
            "have been firmly established as state of the art approaches in sequence modeling.\n"
            "The primary objective of this work is to eliminate recurrence entirely and rely entirely on an attention mechanism "
            "to draw global dependencies between input and output.\n\n"
            "RQ1: Does self-attention achieve competitive translation quality without recurrent recurrence?"
        ),
        content_hash="att_chunk1",
        page_start=1,
        page_end=2,
        section_title="1. Introduction",
        token_count=140,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )

    chunk_2 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=2,
        content=(
            "3. Training and Evaluation\n"
            "We trained on the standard WMT 2014 English-German dataset consisting of 4.5 million sentence pairs.\n"
            "Evaluation metrics include BLEU score computed on newstest2014.\n"
            "Models were trained with Adam optimizer with beta1=0.9, beta2=0.98 on 8 NVIDIA P100 GPUs.\n"
            "A limitation of this work is the quadratic computational complexity with respect to sequence length."
        ),
        content_hash="att_chunk2",
        page_start=5,
        page_end=5,
        section_title="3. Training and Evaluation",
        token_count=150,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )

    db_session.add_all([chunk_0, chunk_1, chunk_2])
    db_session.commit()

    return doc


def test_post_research_analysis_execution(
    test_client: TestClient,
    sample_academic_doc: Document,
    test_workspace: Workspace,
    auth_headers: dict,
):
    """Tests triggering an end-to-end research intelligence extraction run via API."""
    url = f"/api/v1/workspaces/{test_workspace.id}/documents/{sample_academic_doc.id}/research-analysis"
    resp = test_client.post(url, headers=auth_headers, json={"force_reanalysis": True})

    assert resp.status_code in (200, 202), resp.text
    data = resp.json()

    assert data["status"] in ("completed", "completed_with_warnings")
    assert data["workspace_id"] == str(test_workspace.id)
    assert data["document_id"] == str(sample_academic_doc.id)
    assert data["metadata_status"] == "completed"
    assert data["objectives_status"] == "completed"
    assert data["methodology_status"] == "completed"


def test_get_unified_research_analysis(
    test_client: TestClient,
    sample_academic_doc: Document,
    test_workspace: Workspace,
    auth_headers: dict,
):
    """Tests retrieving unified analysis overview containing metadata, objectives, and methodology."""
    # First trigger analysis
    post_url = f"/api/v1/workspaces/{test_workspace.id}/documents/{sample_academic_doc.id}/research-analysis"
    post_resp = test_client.post(post_url, headers=auth_headers, json={"force_reanalysis": True})
    assert post_resp.status_code in (200, 202)

    # Fetch unified analysis
    get_url = f"/api/v1/workspaces/{test_workspace.id}/documents/{sample_academic_doc.id}/research-analysis"
    resp = test_client.get(get_url, headers=auth_headers)

    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Verify active run
    assert data["active_run"] is not None
    assert data["active_run"]["document_id"] == str(sample_academic_doc.id)

    # Verify metadata profile
    meta = data["metadata_profile"]
    assert meta is not None
    assert "Attention Is All You Need" in meta["title"]
    assert meta["arxiv_id"] == "1706.03762" or "1706.03762" in (meta["doi"] or "")

    # Verify objective profile
    obj = data["objective_profile"]
    assert obj is not None
    assert obj["primary_objective"] is not None

    # Verify methodology profile
    meth = data["methodology_profile"]
    assert meth is not None
    assert len(meth["evaluation_metrics"]) >= 1


def test_get_workspace_research_documents_catalog(
    test_client: TestClient,
    sample_academic_doc: Document,
    test_workspace: Workspace,
    auth_headers: dict,
):
    """Tests listing all research documents in workspace with their analysis statuses."""
    # First trigger analysis
    post_url = f"/api/v1/workspaces/{test_workspace.id}/documents/{sample_academic_doc.id}/research-analysis"
    test_client.post(post_url, headers=auth_headers, json={"force_reanalysis": True})

    catalog_url = f"/api/v1/workspaces/{test_workspace.id}/research-documents"
    resp = test_client.get(catalog_url, headers=auth_headers)

    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) >= 1
    doc_item = next((item for item in items if item["document_id"] == str(sample_academic_doc.id)), None)
    assert doc_item is not None
    assert doc_item["has_metadata"] is True
    assert doc_item["has_objectives"] is True
    assert doc_item["has_methodology"] is True


def test_manual_edits_and_preservation(
    test_client: TestClient,
    sample_academic_doc: Document,
    test_workspace: Workspace,
    auth_headers: dict,
):
    """Tests manual curation update and verifies re-run without force preserves manual edits."""
    # 1. Trigger initial run
    post_url = f"/api/v1/workspaces/{test_workspace.id}/documents/{sample_academic_doc.id}/research-analysis"
    test_client.post(post_url, headers=auth_headers, json={"force_reanalysis": True})

    # 2. Patch metadata manually
    patch_url = f"/api/v1/workspaces/{test_workspace.id}/documents/{sample_academic_doc.id}/research-analysis/metadata"
    patch_resp = test_client.patch(
        patch_url,
        headers=auth_headers,
        json={
            "title": "Curated Attention Architecture Paper",
            "publication_year": 2017,
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    patched = patch_resp.json()
    assert patched["title"] == "Curated Attention Architecture Paper"
    assert patched["is_manually_edited"] is True

    # 3. Re-run analysis WITHOUT force_reanalysis
    rerun_resp = test_client.post(post_url, headers=auth_headers, json={"force_reanalysis": False})
    assert rerun_resp.status_code in (200, 202)

    # 4. Check unified GET - manual edits must be preserved
    get_url = f"/api/v1/workspaces/{test_workspace.id}/documents/{sample_academic_doc.id}/research-analysis"
    get_resp = test_client.get(get_url, headers=auth_headers)
    assert get_resp.status_code == 200
    meta = get_resp.json()["metadata_profile"]
    assert meta["title"] == "Curated Attention Architecture Paper"
    assert meta["is_manually_edited"] is True


def test_multi_tenant_workspace_isolation(
    test_client: TestClient,
    sample_academic_doc: Document,
    test_workspace: Workspace,
    other_auth_headers: dict,
):
    """Tests that unauthorized user cannot access or trigger research analysis in another workspace."""
    url = f"/api/v1/workspaces/{test_workspace.id}/documents/{sample_academic_doc.id}/research-analysis"
    # Attempt POST
    post_resp = test_client.post(url, headers=other_auth_headers, json={"force_reanalysis": True})
    assert post_resp.status_code in (403, 404)

    # Attempt GET
    get_resp = test_client.get(url, headers=other_auth_headers)
    assert get_resp.status_code in (403, 404)
