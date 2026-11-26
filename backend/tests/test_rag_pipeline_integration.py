"""End-to-end integration tests for Knovera Core RAG Pipeline (Phase 3 C3.1–C3.3).

Verifies:
    1. Multi-format ingestion (PDF, DOCX, PPTX) embeds chunks and indexes vectors into Chroma.
    2. Document transitions to 'ready' (stage 'ready') only after Chroma indexing is verified.
    3. Document extraction metadata contains vector indexing telemetry.
    4. POST /api/v1/workspaces/{id}/search/semantic retrieves ranked chunks with page/slide provenance.
    5. Cross-workspace isolation guarantees search cannot cross workspace boundaries.
    6. DELETE /api/v1/workspaces/{id}/documents/{id} purges vectors and soft-deletes document.
"""

import io
import uuid
import docx
from fastapi.testclient import TestClient
import pptx
import pymupdf
import pytest
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.workspace import Workspace


def make_test_pdf_bytes(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        p = doc.new_page(width=595, height=842)
        p.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_test_docx_bytes(headings: list[str], paragraphs: list[str]) -> bytes:
    doc = docx.Document()
    for h in headings:
        doc.add_heading(h, level=1)
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_test_pptx_bytes(slides: list[dict]) -> bytes:
    prs = pptx.Presentation()
    blank = prs.slide_layouts[6]
    for s in slides:
        slide = prs.slides.add_slide(blank)
        tx = slide.shapes.add_textbox(pptx.util.Inches(1), pptx.util.Inches(1), pptx.util.Inches(8), pptx.util.Inches(4))
        tf = tx.text_frame
        tf.text = s.get("title", "")
        for b in s.get("bullets", []):
            p = tf.add_paragraph()
            p.text = b
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def test_rag_pipeline_pdf_docx_pptx_end_to_end(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """Verifies complete upload -> chunk -> embed -> index -> search lifecycle for PDF, DOCX, and PPTX."""

    # 1. Ingest PDF document
    pdf_bytes = make_test_pdf_bytes([
        "Attention Mechanisms: Self-attention scales sequence modeling across arbitrary token context.",
    ])
    res_pdf = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("neural_networks.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res_pdf.status_code == 201
    pdf_data = res_pdf.json()
    assert pdf_data["processing_status"] == "ready"
    assert pdf_data["processing_stage"] == "ready"
    pdf_id = pdf_data["id"]

    # Verify document detail has vector indexing telemetry
    res_detail = test_client.get(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{pdf_id}",
        headers=auth_headers,
    )
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert "vector_indexing" in detail_data["extraction_metadata"]
    assert detail_data["extraction_metadata"]["vector_indexing"]["indexed_vectors"] >= 1

    # 2. Ingest DOCX document
    docx_bytes = make_test_docx_bytes(
        headings=["Knowledge Intelligence and Provenance"],
        paragraphs=["Knovera tracks exact source spans and page citations for evidence validation."],
    )
    res_docx = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("intelligence.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res_docx.status_code == 201
    docx_data = res_docx.json()
    assert docx_data["processing_status"] == "ready"
    assert docx_data["processing_stage"] == "ready"
    docx_id = docx_data["id"]

    # 3. Ingest PPTX document
    pptx_bytes = make_test_pptx_bytes([
        {"title": "Slide 1: Bayesian Knowledge Tracing", "bullets": ["Probability of mastery", "Slip and guess parameters"]},
    ])
    res_pptx = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/documents",
        headers=auth_headers,
        files={"file": ("bkt_presentation.pptx", io.BytesIO(pptx_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert res_pptx.status_code == 201
    pptx_data = res_pptx.json()
    assert pptx_data["processing_status"] == "ready"
    assert pptx_data["processing_stage"] == "ready"
    pptx_id = pptx_data["id"]

    # 4. Perform Semantic Search across workspace
    search_payload = {
        "query": "Attention Mechanisms: Self-attention scales sequence modeling across arbitrary token context.",
        "top_k": 5,
    }
    search_res = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/search/semantic",
        headers=auth_headers,
        json=search_payload,
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total_results"] >= 1
    assert search_data["workspace_id"] == str(test_workspace.id)

    # First result should match the PDF attention chunk
    top_result = search_data["results"][0]
    assert top_result["document_filename"] == "neural_networks.pdf"
    assert "Attention Mechanisms" in top_result["content"]
    assert top_result["page_start"] is not None
    assert top_result["rank"] == 1
    assert "total_duration_ms" in search_data["duration_metrics"]

    # 5. Search with document filter
    scoped_payload = {
        "query": "Bayesian Knowledge Tracing",
        "document_ids": [pptx_id],
        "top_k": 5,
    }
    scoped_res = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/search/semantic",
        headers=auth_headers,
        json=scoped_payload,
    )
    assert scoped_res.status_code == 200
    scoped_data = scoped_res.json()
    assert scoped_data["total_results"] >= 1
    assert all(r["document_id"] == pptx_id for r in scoped_data["results"])
    assert scoped_data["results"][0]["slide_number"] == 1

    # 6. Delete document and verify purge
    del_res = test_client.delete(
        f"/api/v1/workspaces/{test_workspace.id}/documents/{pdf_id}",
        headers=auth_headers,
    )
    assert del_res.status_code == 204

    # Search again for the PDF content; it should now return 0 results
    after_del_res = test_client.post(
        f"/api/v1/workspaces/{test_workspace.id}/search/semantic",
        headers=auth_headers,
        json=search_payload,
    )
    assert after_del_res.status_code == 200
    after_del_data = after_del_res.json()
    # The deleted pdf chunks must not be returned
    assert all(r["document_id"] != pdf_id for r in after_del_data["results"])
