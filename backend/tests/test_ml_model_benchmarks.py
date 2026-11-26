"""Regression tests for C11.4 ML Model Benchmarking Framework."""

from pathlib import Path
import pytest

from backend.app.ml.benchmarks.runner import MLBenchmarkRunner
from backend.app.ml.benchmarks.schemas import ModelFamily


@pytest.mark.ml
@pytest.mark.unit
def test_environment_capture():
    """Verifies environment hardware and software capture."""
    runner = MLBenchmarkRunner()
    env = runner.capture_environment()

    assert env.os_name is not None
    assert env.python_version.startswith("3.")
    assert env.cpu_cores > 0
    assert env.total_ram_gb > 0.0


@pytest.mark.ml
@pytest.mark.unit
def test_embedding_and_reranker_benchmarking():
    """Verifies embedding and reranker model benchmarks."""
    runner = MLBenchmarkRunner()
    embed_records = runner.benchmark_embeddings()
    assert len(embed_records) >= 1
    assert embed_records[0].model_family == ModelFamily.EMBEDDINGS.value
    assert embed_records[0].warm_latency_median_ms >= 0.0
    assert embed_records[0].throughput_items_per_sec > 0.0

    rerank_records = runner.benchmark_reranker()
    assert len(rerank_records) >= 1
    assert rerank_records[0].model_family == ModelFamily.RERANKER.value
    assert rerank_records[0].quality_metrics["nDCG@5"] == 1.0


@pytest.mark.ml
@pytest.mark.integration
def test_query_intent_benchmarks_on_test_split():
    """Verifies intent models benchmarked on held-out test split."""
    runner = MLBenchmarkRunner()
    intent_records = runner.benchmark_query_intent()
    assert len(intent_records) >= 2  # Logistic Regression and Linear SVM

    for rec in intent_records:
        assert rec.model_family == ModelFamily.INTENT.value
        assert rec.sample_count == 78  # Exact test split count
        assert rec.data_split == "test"
        assert rec.quality_metrics["accuracy"] >= 0.70
        assert rec.quality_metrics["macro_f1"] >= 0.70
        assert rec.throughput_items_per_sec > 100.0


@pytest.mark.ml
@pytest.mark.unit
def test_clustering_bkt_and_nli_benchmarks():
    """Verifies K-Means, BKT and NLI benchmarks."""
    runner = MLBenchmarkRunner()

    # Topic clustering
    cluster_records = runner.benchmark_topic_clustering()
    assert len(cluster_records) == 4  # K in [3, 4, 5, 6]
    for r in cluster_records:
        assert r.quality_metrics["silhouette_score"] > 0.40

    # BKT
    bkt_records = runner.benchmark_bkt()
    assert len(bkt_records) >= 1
    assert bkt_records[0].quality_metrics["updates_per_second"] > 10_000.0
    assert bkt_records[0].quality_metrics["numerical_stability_pass"] == 1.0

    # NLI
    nli_records = runner.benchmark_nli()
    assert len(nli_records) >= 1
    assert nli_records[0].quality_metrics["accuracy"] >= 0.40


@pytest.mark.ml
@pytest.mark.integration
def test_full_benchmark_run_and_report_generation(tmp_path: Path):
    """Executes full benchmark suite and verifies JSON report artifact."""
    out_file = tmp_path / "test_ml_benchmark_report.json"
    runner = MLBenchmarkRunner()
    report = runner.run_all(output_file=out_file)

    assert report.total_models_benchmarked >= 10
    assert out_file.exists()
    assert len(report.family_summaries) == 6
