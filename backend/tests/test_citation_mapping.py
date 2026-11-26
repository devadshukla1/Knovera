"""Tests for Knovera citation validation, location mapping, and detail retrieval (Phase 3 C3.8)."""

from datetime import datetime, timezone
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from backend.app.citations.exceptions import (
    CitationAccessDeniedError,
    CitationDocumentDeletedError,
    CitationNotFoundError,
    CitationWorkspaceMismatchError,
    UnknownSourceIdError,
)
from backend.app.citations.mapper import CitationMapper
from backend.app.citations.repository import CitationRepository
from backend.app.citations.validator import CitationValidator
from backend.app.models.citation import Citation
from backend.app.models.conversation import Conversation
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.message import Message
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.rag.context.schemas import ContextPackage
from backend.app.rag.prompts.schemas import FactClaim


def create_document_and_chunk(
    db: Session,
    workspace: Workspace,
    filename: str,
    content: str,
    file_ext: str,
    page_start: int | None = None,
    page_end: int | None = None,
    slide_number: int | None = None,
    section_title: str | None = None,
    source_segments: list | None = None,
    deleted: bool = False,
) -> tuple[Document, DocumentChunk]:
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        uploaded_by_user_id=workspace.owner_user_id,
        original_filename=filename,
        storage_key=f"test/{uuid.uuid4().hex[:10]}_{filename}",
        media_type="application/pdf" if file_ext == ".pdf" else "application/vnd.openxmlformats",
        file_extension=file_ext,
        file_size_bytes=2048,
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        processing_status="deleted" if deleted else "ready",
        deleted_at=datetime.now(timezone.utc) if deleted else None,
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
        slide_number=slide_number,
        section_title=section_title,
        source_segments=source_segments or [],
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    db.add_all([doc, chunk])
    db.commit()
    db.refresh(doc)
    db.refresh(chunk)
    return doc, chunk


def test_pdf_page_mapping_single_and_multi_page(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies that PDF citations accurately map 1-based page numbers and ranges."""
    mapper = CitationMapper()

    # 1. Single page chunk
    _, chunk_p4 = create_document_and_chunk(
        db_session, test_workspace, "lecture1.pdf", "Gradient descent converges to a local minimum.",
        ".pdf", page_start=4, page_end=4,
    )
    # 2. Multi-page chunk
    _, chunk_p7_8 = create_document_and_chunk(
        db_session, test_workspace, "textbook.pdf", "Attention mechanisms compute weighted sums of value vectors.",
        ".pdf", page_start=7, page_end=8,
    )

    source_mapping = {
        "S1": {"chunk_id": str(chunk_p4.id), "document_id": str(chunk_p4.document_id), "document_name": "lecture1.pdf"},
        "S2": {"chunk_id": str(chunk_p7_8.id), "document_id": str(chunk_p7_8.document_id), "document_name": "textbook.pdf"},
    }
    claims = [
        FactClaim(text="Gradient descent converges to minimum.", source_ids=["S1"]),
        FactClaim(text="Attention computes weighted sums.", source_ids=["S2"]),
    ]

    drafts = mapper.create_citation_drafts(
        claims=claims,
        source_mapping=source_mapping,
        db=db_session,
        workspace_id=test_workspace.id,
    )

    assert len(drafts) == 2
    d1, d2 = drafts[0], drafts[1]

    # Single page verification
    assert d1.source_id == "S1"
    assert d1.location_type == "pdf_pages"
    assert d1.location_label == "Page 4"
    assert d1.page_start == 4
    assert d1.page_end == 4

    # Multi-page verification
    assert d2.source_id == "S2"
    assert d2.location_type == "pdf_pages"
    assert d2.location_label == "Pages 7–8"
    assert d2.page_start == 7
    assert d2.page_end == 8


def test_docx_section_mapping_never_invents_pages(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies that DOCX citations use section hierarchy and never invent page numbers."""
    mapper = CitationMapper()
    _, chunk_docx = create_document_and_chunk(
        db_session, test_workspace, "notes.docx",
        "Logistic regression is a linear classifier for binary probabilities.",
        ".docx", section_title="Binary Classification",
        source_segments=[{"section_path": ["Machine Learning", "Binary Classification"]}],
    )

    source_mapping = {
        "S1": {"chunk_id": str(chunk_docx.id), "document_id": str(chunk_docx.document_id), "document_name": "notes.docx"},
    }
    claims = [FactClaim(text="Logistic regression is for binary classification.", source_ids=["S1"])]

    drafts = mapper.create_citation_drafts(
        claims=claims,
        source_mapping=source_mapping,
        db=db_session,
        workspace_id=test_workspace.id,
    )

    assert len(drafts) == 1
    d = drafts[0]
    assert d.location_type == "docx_section"
    assert d.location_label == "Section: Binary Classification"
    assert d.page_start is None  # Never invented!
    assert d.page_end is None


def test_pptx_slide_mapping_uses_1_based_index(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies that PPTX citations use 1-based slide numbers."""
    mapper = CitationMapper()
    _, chunk_pptx = create_document_and_chunk(
        db_session, test_workspace, "deck.pptx",
        "Convolutional layers apply spatial kernels across input feature maps.",
        ".pptx", slide_number=5,
    )

    source_mapping = {
        "S1": {"chunk_id": str(chunk_pptx.id), "document_id": str(chunk_pptx.document_id), "document_name": "deck.pptx"},
    }
    claims = [FactClaim(text="CNNs apply spatial kernels.", source_ids=["S1"])]

    drafts = mapper.create_citation_drafts(
        claims=claims,
        source_mapping=source_mapping,
        db=db_session,
        workspace_id=test_workspace.id,
    )

    assert len(drafts) == 1
    d = drafts[0]
    assert d.location_type == "pptx_slide"
    assert d.location_label == "Slide 5"
    assert d.slide_number == 5


def test_citation_validator_rejects_unknown_source_id(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies that UnknownSourceIdError is raised when model cites an unprovided source ID."""
    validator = CitationValidator()
    ctx = ContextPackage(
        query="test",
        sources=[],
        available_context_tokens=4096,
        reserved_output_tokens=1500,
        source_mapping={},  # empty context
    )

    with pytest.raises(UnknownSourceIdError):
        validator.validate_source_ids(
            source_ids=["S99"],
            context_package=ctx,
            db=db_session,
            workspace_id=test_workspace.id,
        )


def test_citation_validator_rejects_deleted_document(
    db_session: Session,
    test_workspace: Workspace,
):
    """Verifies that CitationDocumentDeletedError is raised if cited document is soft-deleted."""
    validator = CitationValidator()
    _, chunk_deleted = create_document_and_chunk(
        db_session, test_workspace, "old.pdf", "Obsolete content.", ".pdf",
        deleted=True,
    )

    ctx = ContextPackage(
        query="test",
        sources=[],
        available_context_tokens=4096,
        reserved_output_tokens=1500,
        source_mapping={"S1": {"chunk_id": str(chunk_deleted.id)}},
    )

    with pytest.raises(CitationDocumentDeletedError):
        validator.validate_source_ids(
            source_ids=["S1"],
            context_package=ctx,
            db=db_session,
            workspace_id=test_workspace.id,
        )


def test_citation_api_and_cross_user_isolation(
    test_client: TestClient,
    test_workspace: Workspace,
    auth_headers: dict[str, str],
    other_user: User,
    db_session: Session,
):
    """Verifies GET /api/v1/citations/{id} returns full metadata for owner and 404 for other user."""
    # 1. Create document, chunk, conversation, message, citation
    _, chunk = create_document_and_chunk(
        db_session, test_workspace, "research.pdf",
        "Transformers eliminate recurrence entirely using multi-head self-attention.",
        ".pdf", page_start=3, page_end=3,
    )
    conv = Conversation(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        created_by_user_id=test_workspace.owner_user_id,
        title="Research Q&A",
    )
    msg = Message(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        conversation_id=conv.id,
        role="assistant",
        content="Transformers use multi-head attention [S1].",
        status="complete",
    )
    citation = Citation(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        message_id=msg.id,
        chunk_id=chunk.id,
        display_order=1,
    )
    db_session.add_all([conv, msg, citation])
    db_session.commit()

    # 2. Owner retrieves citation detail via API
    res_owner = test_client.get(f"/api/v1/citations/{citation.id}", headers=auth_headers)
    assert res_owner.status_code == 200
    detail = res_owner.json()
    assert detail["citation_id"] == str(citation.id)
    assert detail["document_name"] == "research.pdf"
    assert detail["location_label"] == "Page 3"
    assert "Transformers eliminate recurrence" in detail["excerpt"]

    # 3. Create auth token for other user
    from backend.app.core.auth import create_access_token
    other_token = create_access_token(other_user.id)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # 4. Other user attempts to view citation -> Must return 404 (Security boundary)
    res_other = test_client.get(f"/api/v1/citations/{citation.id}", headers=other_headers)
    assert res_other.status_code == 404
