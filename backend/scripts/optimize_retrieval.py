"""Retrieval Optimization Experiment Runner (Phase 4 C4.8).

Systematic, reproducible parameter exploration and Pareto analysis across:
- Dense candidate count (dense_top_k)
- Lexical candidate count (bm25_top_k)
- BM25 Okapi parameters (k1, b)
- Reciprocal Rank Fusion constant (rrf_k)
- Cross-Encoder candidate pool depth (reranker_candidate_k)
- Final context count (final_k)

Includes:
- Bounded search space sampling
- Quality regression protection rules
- Multi-objective Pareto-frontier computation
- Explicit lexicographic selection strategy
- Holdout test split evaluation protection
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

# Ensure Knovera root is on sys.path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.db.chroma import set_chroma_client
from backend.app.rag.evaluation.metrics import aggregate_metrics, evaluate_query
from backend.app.rag.evaluation.validation import validate_dataset_integrity
from backend.app.rag.reranker.fake_reranker import FakeCrossEncoder
from backend.app.rag.reranker.manager import CrossEncoderModelManager
from backend.app.rag.retrieval.hybrid_retriever import HybridRetriever
from backend.app.rag.vector_store.fake_client import InMemoryChromaClient
from backend.scripts.evaluate_retrieval import (
    compute_percentiles,
    load_dataset,
    setup_benchmark_environment,
)

logger = get_logger("knovera.eval.optimization")


def generate_configuration_space(
    max_configurations: int = 20,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """Generates a bounded, deterministic set of retrieval configurations."""
    # Baseline configuration (always index 0)
    baseline_config = {
        "name": "config_00_baseline",
        "dense_top_k": 20,
        "bm25_top_k": 20,
        "bm25_k1": 1.5,
        "bm25_b": 0.75,
        "rrf_k": 60,
        "reranker_candidate_k": 50,
        "final_k": 10,
    }

    # Bounded candidate parameter values
    param_grid = {
        "dense_top_k": [10, 20, 30],
        "bm25_top_k": [10, 20, 30],
        "bm25_k1": [1.2, 1.5, 1.8],
        "bm25_b": [0.65, 0.75, 0.85],
        "rrf_k": [20, 40, 60, 80],
        "reranker_candidate_k": [15, 30, 50],
        "final_k": [8, 10],
    }

    rng = random.Random(seed)
    configs: List[Dict[str, Any]] = [baseline_config]
    seen_tuples = {
        (
            baseline_config["dense_top_k"],
            baseline_config["bm25_top_k"],
            baseline_config["bm25_k1"],
            baseline_config["bm25_b"],
            baseline_config["rrf_k"],
            baseline_config["reranker_candidate_k"],
            baseline_config["final_k"],
        )
    }

    # Deterministic sampling to fill up to max_configurations
    attempts = 0
    while len(configs) < max_configurations and attempts < 1000:
        attempts += 1
        d_k = rng.choice(param_grid["dense_top_k"])
        b_k = rng.choice(param_grid["bm25_top_k"])
        k1 = rng.choice(param_grid["bm25_k1"])
        b = rng.choice(param_grid["bm25_b"])
        r_k = rng.choice(param_grid["rrf_k"])
        rc_k = rng.choice(param_grid["reranker_candidate_k"])
        f_k = rng.choice(param_grid["final_k"])

        sig = (d_k, b_k, k1, b, r_k, rc_k, f_k)
        if sig not in seen_tuples:
            seen_tuples.add(sig)
            idx = len(configs)
            configs.append({
                "name": f"config_{idx:02d}",
                "dense_top_k": d_k,
                "bm25_top_k": b_k,
                "bm25_k1": k1,
                "bm25_b": b,
                "rrf_k": r_k,
                "reranker_candidate_k": rc_k,
                "final_k": f_k,
            })

    return configs


def evaluate_configuration(
    config: Dict[str, Any],
    retriever: HybridRetriever,
    db: Any,
    workspace_id: uuid.UUID,
    queries: List[Dict[str, Any]],
    qrels: Dict[str, Dict[str, int]],
    chunk_id_to_corpus_id: Dict[uuid.UUID, str],
    relevance_threshold: int = 2,
    k_values: Tuple[int, ...] = (5, 10, 20, 50),
) -> Tuple[Dict[str, Any], float, float]:
    """Runs development queries through a single retrieval parameter configuration."""
    # Invalidate cached BM25 index to force re-indexing with specific k1, b
    retriever.bm25_retriever.cache.invalidate(workspace_id)

    query_eval_results = []
    latencies = []

    for q in queries:
        qid = q["query_id"]
        qtext = q["query"]
        query_qrels = qrels.get(qid, {})

        t0 = time.perf_counter()
        response = retriever.retrieve(
            db=db,
            workspace_id=workspace_id,
            query=qtext,
            top_k=config["final_k"],
            mode="hybrid",
            rerank=True,
            dense_top_k=config["dense_top_k"],
            bm25_top_k=config["bm25_top_k"],
            rrf_k=config["rrf_k"],
            reranker_candidate_k=config["reranker_candidate_k"],
            bm25_k1=config["bm25_k1"],
            bm25_b=config["bm25_b"],
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

    agg = aggregate_metrics(query_eval_results, total_queries=len(queries))
    p50_lat, p95_lat = compute_percentiles(latencies)
    return agg, p50_lat, p95_lat


def compute_pareto_frontier(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identifies non-dominated configurations maximizing (nDCG@10, Recall@10) while minimizing p95 latency."""
    pareto: List[Dict[str, Any]] = []
    for candidate in runs:
        if candidate.get("status") == "rejected":
            continue

        c_ndcg = candidate["metrics"].get("ndcg@10", 0.0)
        c_recall = candidate["metrics"].get("recall@10", 0.0)
        c_lat = candidate["p95_latency_ms"]

        is_dominated = False
        for other in runs:
            if other.get("status") == "rejected" or other["config"]["name"] == candidate["config"]["name"]:
                continue

            o_ndcg = other["metrics"].get("ndcg@10", 0.0)
            o_recall = other["metrics"].get("recall@10", 0.0)
            o_lat = other["p95_latency_ms"]

            # other dominates candidate if other is at least as good in all and strictly better in at least one
            if (o_ndcg >= c_ndcg and o_recall >= c_recall and o_lat <= c_lat) and (
                o_ndcg > c_ndcg or o_recall > c_recall or o_lat < c_lat
            ):
                is_dominated = True
                break

        if not is_dominated:
            pareto.append(candidate)

    return pareto


def select_best_configuration(
    pareto_runs: List[Dict[str, Any]],
    baseline_run: Dict[str, Any],
) -> Tuple[Dict[str, Any], str]:
    """Selects preferred configuration from Pareto frontier using explicit documented priorities."""
    if not pareto_runs:
        return baseline_run, "Fallback to baseline: no Pareto-efficient candidate passed constraints."

    # Sort key:
    # 1. Recall@10 DESC
    # 2. nDCG@10 DESC
    # 3. MRR@10 DESC
    # 4. p95 latency ASC
    sorted_candidates = sorted(
        pareto_runs,
        key=lambda r: (
            r["metrics"].get("recall@10", 0.0),
            r["metrics"].get("ndcg@10", 0.0),
            r["metrics"].get("mrr@10", 0.0),
            -r["p95_latency_ms"],
        ),
        reverse=True,
    )

    winner = sorted_candidates[0]
    reason = (
        f"Selected '{winner['config']['name']}' on Pareto frontier: "
        f"Recall@10={winner['metrics'].get('recall@10', 0.0):.4f}, "
        f"nDCG@10={winner['metrics'].get('ndcg@10', 0.0):.4f}, "
        f"MRR@10={winner['metrics'].get('mrr@10', 0.0):.4f}, "
        f"p95={winner['p95_latency_ms']:.1f}ms."
    )
    return winner, reason


def main() -> None:
    parser = argparse.ArgumentParser(description="Knovera Retrieval Optimization Experiment Runner (Phase 4 C4.8)")
    parser.add_argument("--split", choices=["dev", "test"], default="dev", help="Dataset split for tuning (default 'dev' strictly preserves holdout)")
    parser.add_argument("--dataset-dir", default="data/retrieval_eval", help="Path to evaluation dataset")
    parser.add_argument("--output-dir", default="eval/optimization_results", help="Directory for experiment outputs")
    parser.add_argument("--max-configurations", type=int, default=20, help="Maximum parameter configurations to explore")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for search space generation")
    parser.add_argument("--relevance-threshold", type=int, default=2, help="Binary relevance threshold")
    parser.add_argument("--max-allowed-recall-regression", type=float, default=0.05, help="Maximum allowed drop in Recall@10")
    parser.add_argument("--max-allowed-ndcg-regression", type=float, default=0.05, help="Maximum allowed drop in nDCG@10")
    parser.add_argument("--max-p95-latency-ms", type=float, default=500.0, help="Maximum allowed p95 latency in ms")
    parser.add_argument("--test-eval", action="store_true", help="Evaluate the frozen selected configuration on the holdout test split")
    parser.add_argument("--use-real-models", action="store_true", help="Use real SentenceTransformers / CrossEncoder models")
    args = parser.parse_args()

    dataset_dir = (repo_root / args.dataset_dir).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n=================================================================")
    print(" Knovera Retrieval Optimization Experiment Runner (C4.8)")
    print(f" Split: {args.split} (Holdout test protected: {'YES' if args.split == 'dev' else 'NO'})")
    print(f" Max Configurations: {args.max_configurations} | Seed: {args.seed}")
    print("=================================================================\n")

    corpus, dev_queries, qrels, all_queries = load_dataset(dataset_dir, split=args.split)
    validate_dataset_integrity(corpus=corpus, queries=all_queries, qrels=qrels)
    print(f"Dataset integrity validated. Loaded {len(corpus)} corpus chunks, {len(dev_queries)} queries on '{args.split}'.")

    # Configure isolated Chroma & Models
    in_memory_chroma = InMemoryChromaClient()
    set_chroma_client(in_memory_chroma)
    if not args.use_real_models:
        CrossEncoderModelManager.get_instance().set_model(FakeCrossEncoder())

    print("Indexing corpus snapshot into benchmark environment...")
    db, workspace_id, corpus_id_to_chunk_id, chunk_id_to_corpus_id = setup_benchmark_environment(
        corpus=corpus,
        use_mock_models=not args.use_real_models,
    )
    print(f"Benchmark environment initialized. Workspace ID: {workspace_id}\n")

    retriever = HybridRetriever()

    # Generate configuration space
    configs = generate_configuration_space(max_configurations=args.max_configurations, seed=args.seed)
    print(f"Generated {len(configs)} configurations for exploration. Running baseline evaluation...")

    k_values = (5, 10, 20, 50)
    all_runs: List[Dict[str, Any]] = []

    # 1. Run Baseline (config 0)
    baseline_cfg = configs[0]
    base_agg, base_p50, base_p95 = evaluate_configuration(
        config=baseline_cfg,
        retriever=retriever,
        db=db,
        workspace_id=workspace_id,
        queries=dev_queries,
        qrels=qrels,
        chunk_id_to_corpus_id=chunk_id_to_corpus_id,
        relevance_threshold=args.relevance_threshold,
        k_values=k_values,
    )
    baseline_run = {
        "config": baseline_cfg,
        "metrics": base_agg,
        "p50_latency_ms": base_p50,
        "p95_latency_ms": base_p95,
        "status": "accepted",
        "rejection_reason": None,
    }
    all_runs.append(baseline_run)

    base_recall_10 = base_agg.get("recall@10", 0.0)
    base_ndcg_10 = base_agg.get("ndcg@10", 0.0)
    print(f"Baseline: Recall@10={base_recall_10:.4f}, nDCG@10={base_ndcg_10:.4f}, p50={base_p50:.1f}ms, p95={base_p95:.1f}ms\n")

    print("-" * 120)
    print(f"{'Config Name':<20} | {'Dense/BM25':<10} | {'k1 / b':<10} | {'RRF k':<6} | {'Cand K':<6} | {'Recall@10':<9} | {'nDCG@10':<8} | {'p95 ms':<7} | {'Status':<10}")
    print("-" * 120)

    # Print baseline
    print(
        f"{baseline_cfg['name']:<20} | "
        f"{baseline_cfg['dense_top_k']}/{baseline_cfg['bm25_top_k']:<7} | "
        f"{baseline_cfg['bm25_k1']}/{baseline_cfg['bm25_b']:<7} | "
        f"{baseline_cfg['rrf_k']:<6} | "
        f"{baseline_cfg['reranker_candidate_k']:<6} | "
        f"{base_recall_10:<9.4f} | "
        f"{base_ndcg_10:<8.4f} | "
        f"{base_p95:<7.1f} | "
        f"{'BASELINE':<10}"
    )

    # 2. Run remaining configurations
    for cfg in configs[1:]:
        agg, p50, p95 = evaluate_configuration(
            config=cfg,
            retriever=retriever,
            db=db,
            workspace_id=workspace_id,
            queries=dev_queries,
            qrels=qrels,
            chunk_id_to_corpus_id=chunk_id_to_corpus_id,
            relevance_threshold=args.relevance_threshold,
            k_values=k_values,
        )

        cand_recall_10 = agg.get("recall@10", 0.0)
        cand_ndcg_10 = agg.get("ndcg@10", 0.0)

        # Quality Regression Protection Checks
        status = "accepted"
        rejection_reason = None

        if cand_recall_10 < (base_recall_10 - args.max_allowed_recall_regression):
            status = "rejected"
            rejection_reason = f"Recall@10 dropped to {cand_recall_10:.4f} (allowed min: {base_recall_10 - args.max_allowed_recall_regression:.4f})"
        elif cand_ndcg_10 < (base_ndcg_10 - args.max_allowed_ndcg_regression):
            status = "rejected"
            rejection_reason = f"nDCG@10 dropped to {cand_ndcg_10:.4f} (allowed min: {base_ndcg_10 - args.max_allowed_ndcg_regression:.4f})"
        elif p95 > args.max_p95_latency_ms:
            status = "rejected"
            rejection_reason = f"p95 latency {p95:.1f}ms exceeded limit {args.max_p95_latency_ms}ms"

        run_rec = {
            "config": cfg,
            "metrics": agg,
            "p50_latency_ms": p50,
            "p95_latency_ms": p95,
            "status": status,
            "rejection_reason": rejection_reason,
        }
        all_runs.append(run_rec)

        print(
            f"{cfg['name']:<20} | "
            f"{cfg['dense_top_k']}/{cfg['bm25_top_k']:<7} | "
            f"{cfg['bm25_k1']}/{cfg['bm25_b']:<7} | "
            f"{cfg['rrf_k']:<6} | "
            f"{cfg['reranker_candidate_k']:<6} | "
            f"{cand_recall_10:<9.4f} | "
            f"{cand_ndcg_10:<8.4f} | "
            f"{p95:<7.1f} | "
            f"{status.upper():<10}"
        )

    print("-" * 120)

    # 3. Compute Pareto frontier & Selection
    pareto_runs = compute_pareto_frontier(all_runs)
    print(f"\nPareto frontier contains {len(pareto_runs)} non-dominated configurations.")

    best_run, selection_reason = select_best_configuration(pareto_runs, baseline_run)
    print(f"\n=================================================================")
    print(f" OPTIMIZATION SELECTION RESULT")
    print(f"=================================================================")
    print(f"Selected Configuration: {best_run['config']['name']}")
    print(f"Parameters: {best_run['config']}")
    print(f"Reason: {selection_reason}\n")

    # 4. Optional holdout test evaluation
    test_eval_result = None
    if args.test_eval:
        print("Running one-time unbiased evaluation on holdout 'test' split...")
        _, test_queries, _, _ = load_dataset(dataset_dir, split="test")

        # Baseline on test
        base_test_agg, _, base_test_p95 = evaluate_configuration(
            config=baseline_cfg,
            retriever=retriever,
            db=db,
            workspace_id=workspace_id,
            queries=test_queries,
            qrels=qrels,
            chunk_id_to_corpus_id=chunk_id_to_corpus_id,
            relevance_threshold=args.relevance_threshold,
            k_values=k_values,
        )

        # Selected config on test
        opt_test_agg, _, opt_test_p95 = evaluate_configuration(
            config=best_run["config"],
            retriever=retriever,
            db=db,
            workspace_id=workspace_id,
            queries=test_queries,
            qrels=qrels,
            chunk_id_to_corpus_id=chunk_id_to_corpus_id,
            relevance_threshold=args.relevance_threshold,
            k_values=k_values,
        )

        test_eval_result = {
            "baseline_test_metrics": base_test_agg,
            "baseline_test_p95": base_test_p95,
            "optimized_test_metrics": opt_test_agg,
            "optimized_test_p95": opt_test_p95,
        }
        print(f"Holdout Test Baseline : Recall@10={base_test_agg.get('recall@10'):.4f}, nDCG@10={base_test_agg.get('ndcg@10'):.4f}, p95={base_test_p95:.1f}ms")
        print(f"Holdout Test Optimized: Recall@10={opt_test_agg.get('recall@10'):.4f}, nDCG@10={opt_test_agg.get('ndcg@10'):.4f}, p95={opt_test_p95:.1f}ms\n")

    # 5. Save artifacts
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    full_manifest_file = output_dir / f"retrieval_optimization_{args.split}_{timestamp_str}.json"
    selected_config_file = output_dir / "selected_config.json"

    manifest_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "split": args.split,
        "dataset": "knovera_synthetic_smoke_test",
        "dataset_type": "synthetic_smoke_test",
        "seed": args.seed,
        "max_configurations": args.max_configurations,
        "relevance_threshold": args.relevance_threshold,
        "baseline_configuration": baseline_cfg,
        "selected_configuration": best_run["config"],
        "selection_reason": selection_reason,
        "pareto_configurations_count": len(pareto_runs),
        "all_configurations_evaluated": len(all_runs),
        "test_split_evaluation": test_eval_result,
        "runs": all_runs,
    }

    with open(full_manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, indent=2)

    with open(selected_config_file, "w", encoding="utf-8") as f:
        json.dump({
            "selected_at": datetime.now(timezone.utc).isoformat(),
            "configuration": best_run["config"],
            "selection_reason": selection_reason,
            "development_metrics": best_run["metrics"],
            "development_p95_latency_ms": best_run["p95_latency_ms"],
        }, f, indent=2)

    print(f"Full optimization manifest saved to: {full_manifest_file}")
    print(f"Selected configuration saved to: {selected_config_file}\n")


if __name__ == "__main__":
    main()
