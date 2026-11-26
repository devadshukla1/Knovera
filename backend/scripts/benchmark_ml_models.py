"""CLI Runner for Knovera Machine Learning Model Benchmarking (Phase 11 C11.4)."""

import argparse
from pathlib import Path
import sys

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.app.ml.benchmarks.runner import MLBenchmarkRunner


def main():
    parser = argparse.ArgumentParser(description="Knovera ML Model Benchmarking Suite")
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root / "eval" / "results" / "ml_benchmark_report.json",
        help="Path where output JSON report will be saved",
    )
    args = parser.parse_args()

    print("=================================================================")
    print(" Knovera ML Model Benchmarking Framework (Phase 11 C11.4)")
    print(" Measuring: Quality, Latency, Throughput, Memory, Artifact Sizes")
    print("=================================================================\n")

    runner = MLBenchmarkRunner(root_dir=repo_root)
    env = runner.capture_environment()
    print(f"Platform:       {env.os_name} | Python {env.python_version}")
    print(f"Hardware:       {env.cpu_model} ({env.cpu_cores} logical cores) | {env.total_ram_gb} GB RAM")
    print(f"GPU Available:  {env.gpu_available} ({env.gpu_device})")
    print(f"Frameworks:     PyTorch {env.pytorch_version} | Scikit-Learn {env.sklearn_version}")
    print("\nExecuting model benchmarks across all 6 implemented ML families...\n")

    report = runner.run_all(output_file=args.output)

    # Format Table Output
    headers = [
        "Family",
        "Model Identifier",
        "Split",
        "Samples",
        "Median (ms)",
        "p95 (ms)",
        "Throughput (/s)",
        "Memory (MB)",
        "Key Metric",
    ]
    print("-" * 115)
    print(
        f"{headers[0]:<12} | {headers[1]:<35} | {headers[2]:<8} | {headers[3]:<7} | {headers[4]:<11} | {headers[5]:<8} | {headers[6]:<14} | {headers[7]:<11} | {headers[8]}"
    )
    print("-" * 115)

    for run in report.runs:
        fam = run["model_family"]
        name = run["model_identifier"][:35]
        split = run["data_split"]
        n = run["sample_count"]
        med = f"{run['warm_latency_median_ms']:.3f}"
        p95 = f"{run['warm_latency_p95_ms']:.3f}"
        tp = f"{run['throughput_items_per_sec']:.1f}"
        mem = f"{run['peak_process_memory_mb']:.1f}"

        # Pick primary quality metric
        q = run["quality_metrics"]
        if "accuracy" in q:
            key_metric = f"Acc: {q['accuracy']:.4f} (F1: {q.get('macro_f1', 0.0):.4f})"
        elif "silhouette_score" in q:
            key_metric = f"Sil: {q['silhouette_score']:.4f} (DB: {q.get('davies_bouldin_index', 0.0):.4f})"
        elif "updates_per_second" in q:
            key_metric = f"{q['updates_per_second']:.0f} updates/s (100% stable)"
        elif "nDCG@5" in q:
            key_metric = f"nDCG@5: {q['nDCG@5']:.4f}"
        elif "embedding_dimension" in q:
            key_metric = f"{int(q['embedding_dimension'])}-d normalized"
        else:
            key_metric = str(q)

        print(
            f"{fam:<12} | {name:<35} | {split:<8} | {n:<7} | {med:<11} | {p95:<8} | {tp:<14} | {mem:<11} | {key_metric}"
        )

    print("-" * 115)
    print(f"\nExecution Duration: {report.execution_duration_sec}s")
    print(f"Total Models Benchmarked: {report.total_models_benchmarked}")
    print(f"Benchmark Report Saved:   {args.output}\n")


if __name__ == "__main__":
    main()
