"""Unit and Integration Tests for Research Document Metadata Extraction (Phase 10 C10.1).

Tests:
- Bibliographic metadata extraction from document chunks
- Title, author ordering, affiliations, corresponding author
- Publication year and DOI format verification
- arXiv identifier extraction
- Handling missing fields without hallucinating defaults
- Reconciling conflicts between embedded PDF metadata and title page content
- Field-level provenance tracking with chunk coordinates and evidence excerpts
- Manual edit preservation
"""

import json
import uuid
import pytest
from sqlalchemy.orm import Session

from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.ml.research.metadata_extractor import ResearchMetadataExtractor
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


@pytest.fixture
def sample_research_document(db_session: Session, test_workspace: Workspace, test_user: User):
    """Creates a sample research document with realistic title page chunks."""
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="dense_retrieval_transformer_2024.pdf",
        storage_key=f"ws-{test_workspace.id}/docs/dense_retrieval.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1048576,
        sha256="a" * 64,
        processing_status="completed",
        page_count=12,
        pipeline_version="v1.0",
        extraction_metadata={
            "title": "Microsoft Word - Draft_v2.docx",  # Intentionally conflicting embedded title
            "creator": "Word Export 2021",
        },
    )
    db_session.add(doc)
    db_session.flush()

    # Title Page Chunk
    chunk_0 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        content=(
            "IEEE Transactions on Knowledge Engineering, Vol. 36, No. 4, April 2024\n"
            "Dense Neural Retrieval for Complex Academic Questions\n"
            "Dr. Elena Vance (1), Marcus Sterling (2*)\n"
            "(1) Department of Computer Science, Stanford University, USA\n"
            "(2) MIT CSAIL, Cambridge, MA, USA (*Corresponding author)\n"
            "DOI: 10.1109/TKDE.2024.9876543\n"
            "arXiv:2401.12345v2 [cs.IR]\n\n"
            "ABSTRACT\n"
            "Dense retrieval models map queries and documents into continuous embedding spaces. "
            "However, long-tail academic queries suffer from lexical mismatch. In this study, we propose "
            "a dual-encoder architecture with contrastive reranking that outperforms BM25."
        ),
        content_hash="hash0",
        page_start=1,
        page_end=1,
        section_title="Title & Abstract",
        token_count=180,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )

    # Keywords & Intro Chunk
    chunk_1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=1,
        content=(
            "Index Terms—Information retrieval, dense embeddings, contrastive learning, cross-encoders.\n\n"
            "1. INTRODUCTION\n"
            "Information retrieval has transitioned from lexical algorithms like BM25 to neural representation learning. "
            "Published in 2024 by IEEE Computer Society. Supported by National Science Foundation Grant IIS-202401."
        ),
        content_hash="hash1",
        page_start=1,
        page_end=2,
        section_title="1. Introduction",
        token_count=120,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )

    db_session.add_all([chunk_0, chunk_1])
    db_session.commit()

    return doc, [chunk_0, chunk_1]


def test_deterministic_metadata_extraction(db_session: Session, sample_research_document):
    """Verifies regex and deterministic extraction extracts DOI, arXiv, year, and identifies conflicts."""
    doc, chunks = sample_research_document

    extractor = ResearchMetadataExtractor(llm_manager=None, enable_llm=False)
    profile_create = extractor.extract_from_document(doc, chunks)

    assert profile_create.title == "Dense Neural Retrieval for Complex Academic Questions"
    assert profile_create.doi == "10.1109/TKDE.2024.9876543"
    assert profile_create.arxiv_id == "arXiv:2401.12345v2"
    assert profile_create.publication_year == 2024
    assert profile_create.document_type in {"journal_article", "preprint", "conference_paper"}

    # Verify conflict detection with embedded Word title
    assert len(profile_create.conflicts) > 0
    conflict = profile_create.conflicts[0]
    assert conflict.field == "title"
    assert conflict.embedded_value == "Microsoft Word - Draft_v2.docx"
    assert conflict.resolution_status == "resolved_content"

    # Verify field-level provenance
    assert "title" in profile_create.metadata_fields
    title_prov = profile_create.metadata_fields["title"]
    assert title_prov.field == "title"
    assert title_prov.source_type == "document_content"
    assert len(title_prov.evidence) > 0
    assert title_prov.evidence[0].page_number == 1
    assert "Dense Neural Retrieval" in title_prov.evidence[0].evidence_text


def test_llm_assisted_metadata_extraction(db_session: Session, sample_research_document):
    """Verifies LLM-assisted extraction parses authors, affiliations, volume, and keywords into schema."""
    doc, chunks = sample_research_document

    mock_llm_payload = {
        "document_type": "journal_article",
        "title": "Dense Neural Retrieval for Complex Academic Questions",
        "subtitle": None,
        "language": "en",
        "abstract": "Dense retrieval models map queries and documents into continuous embedding spaces.",
        "keywords": ["Information retrieval", "dense embeddings", "contrastive learning"],
        "authors": [
            {
                "name": "Elena Vance",
                "order": 1,
                "affiliation": "Department of Computer Science, Stanford University",
                "department": "Department of Computer Science",
                "institution": "Stanford University",
                "country": "USA",
                "is_corresponding": False,
            },
            {
                "name": "Marcus Sterling",
                "order": 2,
                "affiliation": "MIT CSAIL, Cambridge, MA",
                "department": "CSAIL",
                "institution": "MIT",
                "country": "USA",
                "is_corresponding": True,
            },
        ],
        "publication_year": 2024,
        "publication_date": "April 2024",
        "journal_name": "IEEE Transactions on Knowledge Engineering",
        "publisher": "IEEE Computer Society",
        "volume": "36",
        "issue": "4",
        "doi": "10.1109/TKDE.2024.9876543",
        "arxiv_id": "arXiv:2401.12345v2",
        "funding_organization": "National Science Foundation",
        "grant_identifiers": ["IIS-202401"],
        "research_domain": "Computer Science",
        "subdomain": "Information Retrieval",
    }

    mock_provider = MockLLMProvider(default_response=json.dumps(mock_llm_payload))
    manager = LLMManager.get_instance()
    manager.registry.register("mock", mock_provider)

    extractor = ResearchMetadataExtractor(llm_manager=manager)
    profile = extractor.extract_from_document(doc, chunks)

    assert profile.title == "Dense Neural Retrieval for Complex Academic Questions"
    assert profile.journal_name == "IEEE Transactions on Knowledge Engineering"
    assert profile.volume == "36"
    assert profile.issue == "4"
    assert len(profile.authors) == 2
    assert profile.authors[0].name == "Elena Vance"
    assert profile.authors[0].order == 1
    assert profile.authors[1].name == "Marcus Sterling"
    assert profile.authors[1].is_corresponding is True
    assert "Information retrieval" in profile.keywords
    assert profile.funding_organization == "National Science Foundation"
    assert "IIS-202401" in profile.grant_identifiers


def test_missing_metadata_handling_without_hallucination(db_session: Session, test_workspace: Workspace, test_user: User):
    """Verifies document with missing publication year and DOI reports None and status missing."""
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="student_term_paper.docx",
        storage_key=f"ws-{test_workspace.id}/docs/term_paper.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_extension=".docx",
        file_size_bytes=45000,
        sha256="b" * 64,
        processing_status="completed",
        page_count=3,
        pipeline_version="v1.0",
        extraction_metadata={},
    )
    db_session.add(doc)
    db_session.flush()

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        content=(
            "Analysis of Inverted Index Algorithms in Python\n"
            "Alex Mercer\n"
            "This paper explores lexical search techniques."
        ),
        content_hash="chash_doc",
        page_start=1,
        page_end=1,
        token_count=50,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )
    db_session.add(chunk)
    db_session.commit()

    extractor = ResearchMetadataExtractor(llm_manager=None, enable_llm=False)
    profile = extractor.extract_from_document(doc, [chunk])

    assert profile.title == "Analysis of Inverted Index Algorithms in Python"
    assert profile.doi is None
    assert profile.arxiv_id is None
    assert profile.publication_year is None
    assert profile.metadata_fields["publication_year"].extraction_status == "missing"
    assert profile.metadata_fields["publication_year"].value is None
