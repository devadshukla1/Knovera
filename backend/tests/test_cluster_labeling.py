"""Unit tests for Cluster Keyword Extraction and Labeling Service (Phase 6 C6.5)."""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.app.llm.schemas import LLMGenerationResponse
from backend.app.ml.topic_clustering.keyword_extraction import ClusterKeywordExtractor
from backend.app.ml.topic_clustering.labeling import ClusterLabelingService
from backend.app.ml.topic_clustering.schemas import (
    ClusterAssignment,
    ClusterStats,
    TopicKeyword,
    TopicLabelMetadata,
)
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk


def test_cluster_keyword_extractor_distinct_topics():
    extractor = ClusterKeywordExtractor(top_k=5)
    cluster_texts = {
        0: [
            "Gradient descent optimization with backpropagation in neural networks.",
            "Stochastic gradient descent updates network weights and minimizes loss.",
            "Learning rate tuning is essential for backpropagation convergence.",
        ],
        1: [
            "PostgreSQL database query optimization and B-tree indexes.",
            "Relational database schema design, foreign keys, and indexes.",
            "SQL query execution plans and database normalization.",
        ],
    }

    keywords = extractor.extract_cluster_keywords(cluster_texts)

    assert 0 in keywords
    assert 1 in keywords

    c0_terms = [kw.term.lower() for kw in keywords[0]]
    c1_terms = [kw.term.lower() for kw in keywords[1]]

    # Topic 0 should have ML terms
    assert any("gradient" in t or "backpropagation" in t or "neural" in t for t in c0_terms)
    # Topic 1 should have DB terms
    assert any("database" in t or "query" in t or "sql" in t or "indexes" in t for t in c1_terms)


def test_deterministic_label_generation():
    service = ClusterLabelingService()
    keywords = [
        TopicKeyword(term="gradient descent", score=0.65),
        TopicKeyword(term="backpropagation", score=0.58),
        TopicKeyword(term="neural networks", score=0.45),
    ]

    title, desc = service.generate_deterministic_label(keywords, cluster_id=0)
    assert "Gradient Descent" in title
    assert "Backpropagation" in title
    assert "gradient descent" in desc.lower()


def test_deterministic_label_generation_empty_fallback():
    service = ClusterLabelingService()
    title, desc = service.generate_deterministic_label([], cluster_id=2)
    assert title == "Mixed Topic Cluster 2"
    assert "diverse or weakly separated" in desc


@pytest.mark.asyncio
async def test_llm_assisted_label_generation_success():
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMGenerationResponse(
            content='{"label": "Neural Network Optimization", "description": "Techniques for model training and loss minimization."}',
            provider="mock",
            requested_model="mock-model",
            input_tokens=50,
            output_tokens=30,
            latency_ms=100,
        )
    )

    service = ClusterLabelingService(llm_manager=mock_llm)
    keywords = [TopicKeyword(term="gradient descent", score=0.8)]
    res = await service.generate_llm_assisted_label(
        cluster_id=0,
        keywords=keywords,
        representative_excerpts=["Some sample text"],
    )

    assert res is not None
    label, desc = res
    assert label == "Neural Network Optimization"
    assert "Techniques for model training" in desc


@pytest.mark.asyncio
async def test_llm_assisted_label_generation_malformed_fallback():
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMGenerationResponse(
            content="Sorry, I cannot process this request.",  # Not valid JSON
            provider="mock",
            requested_model="mock-model",
            input_tokens=50,
            output_tokens=10,
            latency_ms=100,
        )
    )

    service = ClusterLabelingService(llm_manager=mock_llm)
    keywords = [TopicKeyword(term="gradient descent", score=0.8)]
    res = await service.generate_llm_assisted_label(
        cluster_id=0,
        keywords=keywords,
        representative_excerpts=["Some sample text"],
    )

    assert res is None  # Handled safely, callers fall back to deterministic


def test_human_approved_label_preservation(db_session):
    ws_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    doc = Document(
        id=doc_id,
        workspace_id=ws_id,
        uploaded_by_user_id=uuid.uuid4(),
        original_filename="doc.pdf",
        storage_key=f"doc_{uuid.uuid4()}.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1000,
        sha256="d" * 64,
        processing_status="completed",
    )
    chunk = DocumentChunk(
        id=chunk_id,
        workspace_id=ws_id,
        document_id=doc_id,
        chunk_index=0,
        content="Deep learning and tensor operations.",
        content_hash="h" * 64,
        parser_version="v1",
        cleaning_version="v1",
        chunking_version="v1",
    )
    db_session.add_all([doc, chunk])
    db_session.commit()

    service = ClusterLabelingService()
    assignments = [
        ClusterAssignment(
            chunk_id=str(chunk_id),
            cluster_id=0,
            distance_to_centroid=0.15,
            is_representative=True,
        )
    ]
    stats_map = {
        0: ClusterStats(
            cluster_id=0,
            size=1,
            proportion=1.0,
            min_distance=0.15,
            mean_distance=0.15,
            max_distance=0.15,
            representative_chunk_ids=[str(chunk_id)],
        )
    }

    # Simulate existing human approved topic for cluster_0
    existing = {
        "cluster_0": TopicLabelMetadata(
            cluster_key="cluster_0",
            cluster_id=0,
            label="Human Verified Deep Learning Architecture",
            description="Verified by Domain Lead.",
            label_source="human_reviewed",
            label_status="approved",
            keywords=[],
            representative_chunk_ids=[str(chunk_id)],
        )
    }

    labeled = service.label_clusters(
        session=db_session,
        workspace_id=ws_id,
        assignments=assignments,
        cluster_stats=stats_map,
        existing_topic_labels=existing,
    )

    assert 0 in labeled
    assert labeled[0].label == "Human Verified Deep Learning Architecture"
    assert labeled[0].label_status == "approved"
    assert labeled[0].label_source == "human_reviewed"
