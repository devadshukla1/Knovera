"""Command-line runner for Knovera retrieval evaluation benchmark (Phase 4 C4.6).

Evaluates and compares:
1. Dense Semantic Retrieval (Bi-Encoder)
2. Lexical Keyword Retrieval (BM25 Okapi)
3. Hybrid Retrieval (Dense + BM25 via Reciprocal Rank Fusion)
4. Hybrid Retrieval + Cross-Encoder Reranking (RRF + MS MARCO MiniLM)
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Set, Tuple
import uuid

# Ensure Knovera root is on sys.path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.db.base import Base
from backend.app.db.chroma import set_chroma_client
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.rag.evaluation.metrics import (
    QueryEvaluationResult,
    aggregate_metrics,
    evaluate_query,
)
from backend.app.rag.evaluation.validation import validate_dataset_integrity
from backend.app.rag.reranker.fake_reranker import FakeCrossEncoder
from backend.app.rag.reranker.manager import CrossEncoderModelManager
from backend.app.rag.reranker.reranker import CrossEncoderReranker
from backend.app.rag.retrieval.bm25.retriever import BM25Retriever
from backend.app.rag.retrieval.hybrid_retriever import HybridRetriever
from backend.app.rag.retrieval.semantic_retriever import SemanticRetriever
from backend.app.rag.vector_store.chroma_repository import ChromaVectorRepository
from backend.app.rag.vector_store.fake_client import InMemoryChromaClient
from backend.app.rag.vector_store.schemas import VectorRecord

logger = get_logger("knovera.eval.retrieval")


def load_dataset(dataset_dir: Path, split: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Dict[str, int]], List[Dict[str, Any]]]:
    """Loads corpus, filtered queries, relevance judgments, and all queries."""
    corpus_file = dataset_dir / "corpus.jsonl"
    queries_file = dataset_dir / "queries.jsonl"
    qrels_file = dataset_dir / "qrels.tsv"

    # 1. Corpus
    corpus: Dict[str, Any] = {}
    with open(corpus_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                corpus[item["id"]] = item

    # 2. Queries
    all_queries: List[Dict[str, Any]] = []
    filtered_queries: List[Dict[str, Any]] = []
    with open(queries_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                all_queries.append(q)
                if split == "all" or q["split"] == split:
                    filtered_queries.append(q)

    # 3. Qrels
    qrels: Dict[str, Dict[str, int]] = {}
    with open(qrels_file, "r", encoding="utf-8") as f:
        header = f.readline()  # skip header
        for line in f:
            if line.strip():
                parts = line.strip().split("\t")
                if len(parts) >= 3:
                    qid, cid, score_str = parts[0], parts[1], parts[2]
                    if qid not in qrels:
                        qrels[qid] = {}
                    qrels[qid][cid] = int(score_str)

    return corpus, filtered_queries, qrels, all_queries


def setup_benchmark_environment(
    corpus: Dict[str, Any],
    use_mock_models: bool = False,
) -> Tuple[Any, uuid.UUID, Dict[str, uuid.UUID], Dict[uuid.UUID, str]]:
    """Populates an in-memory SQLite database and vector repository with corpus chunks."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    # User & Workspace
    user = User(
        id=uuid.uuid4(),
        email="eval_runner@knovera.ai",
        password_hash="eval_hash",
        display_name="Benchmark Runner",
        status="active",
    )
    ws = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name="Retrieval Benchmark Workspace",
    )
    db.add_all([user, ws])
    db.commit()

    chunk_id_to_corpus_id: Dict[uuid.UUID, str] = {}
    corpus_id_to_chunk_id: Dict[str, uuid.UUID] = {}

    doc_cache: Dict[str, Document] = {}

    vector_repo = ChromaVectorRepository()
    records_to_insert = []

    for cid, item in corpus.items():
        doc_fn = item["document_filename"]
        if doc_fn not in doc_cache:
            doc = Document(
                id=uuid.uuid4(),
                workspace_id=ws.id,
                uploaded_by_user_id=user.id,
                original_filename=doc_fn,
                storage_key=f"eval/{doc_fn}",
                media_type="application/pdf",
                file_extension=".pdf",
                file_size_bytes=len(item["content"]),
                sha256=f"hash_{uuid.uuid4().hex[:8]}",
                processing_status="ready",
                processing_stage="ready",
            )
            db.add(doc)
            db.commit()
            doc_cache[doc_fn] = doc

        chunk_uuid = uuid.uuid4()
        chunk = DocumentChunk(
            id=chunk_uuid,
            document_id=doc_cache[doc_fn].id,
            workspace_id=ws.id,
            chunk_index=len(chunk_id_to_corpus_id),
            content=item["content"],
            token_count=len(item["content"].split()),
            token_count_method="estimate_v1",
            parser_version="eval_v1",
            cleaning_version="v1",
            chunking_version="v1",
            content_hash=f"hash_{cid}",
            source_segments=[],
            page_start=item["page_start"],
            page_end=item["page_end"],
            section_title=item.get("section_title"),
        )
        db.add(chunk)
        chunk_id_to_corpus_id[chunk_uuid] = cid
        corpus_id_to_chunk_id[cid] = chunk_uuid

        records_to_insert.append((
            str(chunk_uuid),
            item["content"],
            {
                "document_id": str(doc_cache[doc_fn].id),
                "workspace_id": str(ws.id),
                "page_start": item["page_start"],
                "page_end": item["page_end"],
            }
        ))

    db.commit()

    # Index into vector store
    vector_records = []
    for chunk_id_str, text, meta in records_to_insert:
        embedding = vector_repo.provider.encode_documents([text])[0]
        vector_records.append(
            VectorRecord(
                id=chunk_id_str,
                embedding=embedding,
                metadata={
                    "chunk_id": chunk_id_str,
                    "document_id": meta["document_id"],
                    "workspace_id": meta["workspace_id"],
                    "page_start": meta["page_start"],
                    "page_end": meta["page_end"],
                },
                document_text=text,
            )
        )
    vector_repo.upsert_records(vector_records)

    return db, ws.id, corpus_id_to_chunk_id, chunk_id_to_corpus_id


def compute_percentiles(values: List[float]) -> Tuple[float, float]:
    """Calculates p50 and p95 percentiles from a list of float values."""
    if not values:
        return 0.0, 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    p50_idx = min(int(round(0.50 * n)), n - 1)
    p95_idx = min(int(round(0.95 * n)), n - 1)
    return round(sorted_vals[p50_idx], 2), round(sorted_vals[p95_idx], 2)


def evaluate_system(
    system_name: str,
    retriever: HybridRetriever,
    db: Any,
    workspace_id: uuid.UUID,
    queries: List[Dict[str, Any]],
    qrels: Dict[str, Dict[str, int]],
    chunk_id_to_corpus_id: Dict[uuid.UUID, str],
    mode: str,
    rerank: bool,
    top_k: int = 50,
    relevance_threshold: int = 2,
    k_values: Tuple[int, ...] = (5, 10, 20, 50),
) -> Tuple[Dict[str, Any], float, float, List[Dict[str, Any]]]:
    """Runs evaluation queries through a specified retriever configuration."""
    query_eval_results: List[QueryEvaluationResult] = []
    latencies: List[float] = []
    detailed_runs: List[Dict[str, Any]] = []

    for q in queries:
        qid = q["query_id"]
        qtext = q["query"]
        query_qrels = qrels.get(qid, {})

        t0 = time.perf_counter()
        response = retriever.retrieve(
            db=db,
            workspace_id=workspace_id,
            query=qtext,
            top_k=top_k,
            mode=mode,
            rerank=rerank,
        )
        duration_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(duration_ms)

        retrieved_corpus_ids = [
            chunk_id_to_corpus_id.get(r.chunk_id, str(r.chunk_id))
            for r in response.results
        ]

        candidate_corpus_ids = None
        if response.candidate_results:
            candidate_corpus_ids = [
                chunk_id_to_corpus_id.get(r.chunk_id, str(r.chunk_id))
                for r in response.candidate_results
            ]

        eval_res = evaluate_query(
            retrieved_ids=retrieved_corpus_ids,
            qrels=query_qrels,
            relevance_threshold=relevance_threshold,
            k_values=k_values,
            query_id=qid,
            query=qtext,
            category=q.get("category"),
            candidate_ids=candidate_corpus_ids,
            latency_ms=round(duration_ms, 2),
        )
        query_eval_results.append(eval_res)

        detailed_runs.append({
            "query_id": qid,
            "query": qtext,
            "category": q.get("category"),
            "latency_ms": round(duration_ms, 2),
            "is_evaluable": eval_res.is_evaluable,
            "relevant_chunks_total": eval_res.relevant_chunks_total,
            "relevant_chunks_retrieved": eval_res.relevant_chunks_retrieved,
            "first_relevant_rank": eval_res.first_relevant_rank,
            "known_judgment_count": eval_res.known_judgment_count,
            "judgment_coverage": eval_res.judgment_coverage,
            "metrics": eval_res.metrics,
            "candidate_metrics": eval_res.candidate_metrics,
            "retrieved_ids": retrieved_corpus_ids,
        })

    agg = aggregate_metrics(query_eval_results, total_queries=len(queries))
    p50_lat, p95_lat = compute_percentiles(latencies)
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    agg["p50_latency_ms"] = p50_lat
    agg["p95_latency_ms"] = p95_lat
    agg["avg_latency_ms"] = avg_latency

    return agg, p50_lat, p95_lat, detailed_runs


def main() -> None:
    parser = argparse.ArgumentParser(description="Knovera Retrieval Evaluation Runner (Phase 4 C4.6–C4.7)")
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev", help="Dataset split to evaluate")
    parser.add_argument("--dataset-dir", default="data/retrieval_eval", help="Path to evaluation dataset")
    parser.add_argument("--output-dir", default="eval/results", help="Directory for JSON evaluation reports")
    parser.add_argument("--relevance-threshold", type=int, default=2, help="Binary relevance grade cutoff (default 2: grades >=2 are relevant)")
    parser.add_argument("--k-values", default="5,10,20,50", help="Comma-separated K values for cutoffs")
    parser.add_argument("--use-real-models", action="store_true", help="Load real PyTorch/HF models instead of deterministic test providers")
    args = parser.parse_args()

    k_values = tuple(int(x.strip()) for x in args.k_values.split(",") if x.strip())
    dataset_dir = (repo_root / args.dataset_dir).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=================================================================")
    print(f" Knovera Retrieval Benchmark Evaluation Runner (C4.7)")
    print(f" Split: {args.split} | Relevance Threshold: {args.relevance_threshold}")
    print(f" K Values: {k_values} | Dataset: {dataset_dir}")
    print(f"=================================================================\n")

    corpus, queries, qrels, all_queries = load_dataset(dataset_dir, split=args.split)
    print(f"Loaded {len(corpus)} corpus documents, {len(queries)} queries for split '{args.split}' ({len(all_queries)} total in dataset), {sum(len(v) for v in qrels.values())} relevance judgments.")

    # Validate full dataset integrity
    val_report = validate_dataset_integrity(corpus=corpus, queries=all_queries, qrels=qrels)
    print(f"Dataset integrity validated: {val_report['total_judgments']} judgments across {val_report['grade_distribution']} grades.")

    # Configure isolated Chroma & Models
    in_memory_chroma = InMemoryChromaClient()
    set_chroma_client(in_memory_chroma)

    if not args.use_real_models:
        CrossEncoderModelManager.get_instance().set_model(FakeCrossEncoder())

    print("Indexing corpus into benchmark environment...")
    db, workspace_id, corpus_id_to_chunk_id, chunk_id_to_corpus_id = setup_benchmark_environment(
        corpus=corpus,
        use_mock_models=not args.use_real_models,
    )
    print(f"Index complete. Workspace UUID: {workspace_id}\n")

    retriever = HybridRetriever()

    systems = [
        ("Dense (Bi-Encoder)", "semantic", False),
        ("Lexical (BM25 Okapi)", "bm25", False),
        ("Hybrid (RRF Dense+BM25)", "hybrid", False),
        ("Hybrid + Cross-Encoder Rerank", "hybrid", True),
    ]

    all_results: Dict[str, Any] = {}

    print("-" * 115)
    print(f"{'Retrieval System':<30} | {'Recall@5':<8} | {'Recall@10':<9} | {'Recall@20':<9} | {'MRR@10':<7} | {'nDCG@10':<7} | {'p50 ms':<6} | {'p95 ms':<6}")
    print("-" * 115)

    for sys_name, mode, rerank in systems:
        agg, p50_lat, p95_lat, detailed = evaluate_system(
            system_name=sys_name,
            retriever=retriever,
            db=db,
            workspace_id=workspace_id,
            queries=queries,
            qrels=qrels,
            chunk_id_to_corpus_id=chunk_id_to_corpus_id,
            mode=mode,
            rerank=rerank,
            top_k=max(k_values),
            relevance_threshold=args.relevance_threshold,
            k_values=k_values,
        )

        row = {
            "system": sys_name,
            "mode": mode,
            "rerank": rerank,
            "relevance_threshold": args.relevance_threshold,
            "k_values": list(k_values),
            "aggregate_metrics": agg,
            "p50_latency_ms": p50_lat,
            "p95_latency_ms": p95_lat,
            "query_runs": detailed,
        }
        all_results[sys_name] = row

        print(
            f"{sys_name:<30} | "
            f"{agg.get('recall@5', 0.0):<8.4f} | "
            f"{agg.get('recall@10', 0.0):<9.4f} | "
            f"{agg.get('recall@20', 0.0):<9.4f} | "
            f"{agg.get('mrr@10', 0.0):<7.4f} | "
            f"{agg.get('ndcg@10', 0.0):<7.4f} | "
            f"{p50_lat:<6.1f} | "
            f"{p95_lat:<6.1f}"
        )

    print("-" * 115)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_file = output_dir / f"retrieval_eval_{args.split}_{timestamp_str}.json"
    report_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "split": args.split,
        "dataset": "knovera_synthetic_smoke_test",
        "dataset_type": "synthetic_smoke_test",
        "relevance_threshold": args.relevance_threshold,
        "k_values": list(k_values),
        "queries_count": len(queries),
        "corpus_count": len(corpus),
        "systems": all_results,
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    print(f"\nSaved benchmark evaluation report to: {report_file}\n")


if __name__ == "__main__":
    main()
