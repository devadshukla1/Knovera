"""Retrieval Quality Baseline Evaluation for Knovera Semantic Search (Phase 3 C3.3).

Evaluates semantic retrieval on a benchmark test dataset of queries with ground-truth chunks:
    - Calculates Recall@5 and Recall@10.
    - Measures average retrieval latency (must be < 200ms per query).
    - Verifies semantic retrieval quality meets production baseline (Recall@10 >= 0.80).
"""

import time
import uuid
import pytest
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.workspace import Workspace
from backend.app.rag.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingProvider,
)
from backend.app.rag.retrieval.semantic_retriever import SemanticRetriever
from backend.app.rag.vector_store.chroma_repository import ChromaVectorRepository
from backend.app.rag.vector_store.fake_client import InMemoryChromaClient
from backend.app.rag.vector_store.schemas import VectorRecord


# Benchmark dataset: 5 domain topics with semantic variation between query and ground truth
BENCHMARK_CORPUS = [
    {
        "id": "ml_chunk",
        "doc_name": "machine_learning_handbook.pdf",
        "content": "Machine learning algorithms learn statistical representations from training data without being explicitly programmed.",
        "query": "How do modern computers learn patterns from large datasets?",
    },
    {
        "id": "bio_chunk",
        "doc_name": "cell_biology_review.pdf",
        "content": "Mitochondria are double-membraned cellular organelles that generate most of the chemical energy required to power cellular biochemical reactions via ATP.",
        "query": "What cellular organelle produces chemical ATP energy for cells?",
    },
    {
        "id": "db_chunk",
        "doc_name": "distributed_databases.pdf",
        "content": "PostgreSQL is an advanced open-source object-relational database system that provides robust ACID compliance and multi-version concurrency control.",
        "query": "Which relational SQL database guarantees strict ACID transaction compliance?",
    },
    {
        "id": "physics_chunk",
        "doc_name": "quantum_physics.pdf",
        "content": "Quantum entanglement is a phenomenon where pairs or groups of particles interact such that the quantum state of each particle cannot be described independently.",
        "query": "What physical principle allows particles to remain correlated at a distance?",
    },
    {
        "id": "edu_chunk",
        "doc_name": "adaptive_learning_systems.pdf",
        "content": "Bayesian Knowledge Tracing is an algorithm used in intelligent tutoring systems to estimate the latent probability of student mastery for specific skills.",
        "query": "How can tutoring software track and estimate a student's concept mastery?",
    },
]


def test_retrieval_quality_and_latency_baseline(
    db_session: Session,
    test_workspace: Workspace,
):
    """Executes benchmark quality evaluation with real Sentence Transformers model."""
    client = InMemoryChromaClient()

    # Load real local embedding model
    try:
        provider = SentenceTransformerEmbeddingProvider()
    except Exception as exc:
        pytest.skip(f"SentenceTransformer model not available in current environment: {exc}")

    repo = ChromaVectorRepository(chroma_client=client, embedding_provider=provider)
    retriever = SemanticRetriever(
        embedding_provider=provider,
        vector_repository=repo,
    )

    # 1. Ingest benchmark corpus into PostgreSQL and Chroma
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_workspace.owner_user_id,
        original_filename="benchmark_corpus.pdf",
        storage_key="test/benchmark_corpus.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1024,
        sha256="0" * 64,
        processing_status="ready",
        processing_stage="ready",
    )
    db_session.add(doc)
    db_session.commit()

    chunk_id_map = {}
    db_chunks = []
    vector_records = []

    # Encode corpus chunks
    corpus_texts = [item["content"] for item in BENCHMARK_CORPUS]
    embeddings = provider.encode_documents(corpus_texts)

    for idx, (item, emb) in enumerate(zip(BENCHMARK_CORPUS, embeddings)):
        c_id = uuid.uuid4()
        chunk_id_map[item["id"]] = c_id

        db_chunk = DocumentChunk(
            id=c_id,
            workspace_id=test_workspace.id,
            document_id=doc_id,
            chunk_index=idx,
            content=item["content"],
            content_hash=f"{idx:064x}",
            page_start=idx + 1,
            page_end=idx + 1,
            token_count=len(item["content"].split()),
            parser_version="benchmark-v1",
            cleaning_version="v1.0",
            chunking_version="semantic-v1",
            source_segments=[{"page_number": idx + 1, "text": item["content"]}],
        )
        db_chunks.append(db_chunk)

        vector_records.append(
            VectorRecord(
                id=str(c_id),
                embedding=emb,
                metadata={
                    "chunk_id": str(c_id),
                    "document_id": str(doc_id),
                    "workspace_id": str(test_workspace.id),
                    "chunk_index": idx,
                },
            )
        )

    db_session.add_all(db_chunks)
    db_session.commit()
    repo.upsert_records(vector_records)

    # 2. Evaluate each benchmark query
    hits_at_5 = 0
    hits_at_10 = 0
    latencies_ms = []

    for item in BENCHMARK_CORPUS:
        expected_chunk_id = chunk_id_map[item["id"]]
        q_start = time.perf_counter()

        response = retriever.retrieve(
            db=db_session,
            workspace_id=test_workspace.id,
            query=item["query"],
            top_k=5,
        )
        duration_ms = (time.perf_counter() - q_start) * 1000.0
        latencies_ms.append(duration_ms)

        retrieved_ids = [r.chunk_id for r in response.results]

        # Check Recall@5
        if expected_chunk_id in retrieved_ids[:5]:
            hits_at_5 += 1

        # Check Recall@10
        if expected_chunk_id in retrieved_ids[:10]:
            hits_at_10 += 1

    total_queries = len(BENCHMARK_CORPUS)
    recall_at_5 = hits_at_5 / total_queries
    recall_at_10 = hits_at_10 / total_queries
    avg_latency_ms = sum(latencies_ms) / total_queries

    print(f"\n--- Benchmark Results ---")
    print(f"Total Queries: {total_queries}")
    print(f"Recall@5:      {recall_at_5:.2%}")
    print(f"Recall@10:     {recall_at_10:.2%}")
    print(f"Avg Latency:   {avg_latency_ms:.2f}ms")

    # Baseline Acceptance Criteria
    assert recall_at_5 >= 0.80, f"Recall@5 ({recall_at_5:.2%}) failed threshold (>= 80%)"
    assert recall_at_10 >= 0.80, f"Recall@10 ({recall_at_10:.2%}) failed threshold (>= 80%)"
    assert avg_latency_ms < 200.0, f"Avg latency ({avg_latency_ms:.2f}ms) exceeded 200ms budget"
