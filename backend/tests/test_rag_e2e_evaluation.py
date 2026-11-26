"""Regression and quality gate tests for C11.3 End-to-End RAG Evaluation."""

from pathlib import Path
import pytest

from backend.app.rag.evaluation.rag_evaluator import (
    RAGEvaluator,
    compute_token_f1,
    tokenize_content,
)
from backend.scripts.evaluate_rag_e2e import run_e2e_rag_evaluation


@pytest.mark.rag
@pytest.mark.unit
def test_tokenize_and_f1_computation():
    """Verifies tokenization and F1 calculations."""
    text1 = "TCP three-way handshake establishes reliable connections."
    text2 = "TCP establishes connections with a three-way handshake."
    precision, recall, f1 = compute_token_f1(text1, text2)

    assert precision > 0.7
    assert recall > 0.7
    assert f1 > 0.7

    # Disjoint texts
    p0, r0, f0 = compute_token_f1("Apple banana cherry", "Quantum entanglement physics")
    assert p0 == 0.0
    assert r0 == 0.0
    assert f0 == 0.0


@pytest.mark.rag
@pytest.mark.unit
def test_abstention_detection_logic():
    """Verifies identification of valid abstentions."""
    ans1 = "The available documents in this workspace do not provide sufficient evidence to answer your question."
    ans2 = "There are no searchable documents in this workspace yet. Please upload files."
    ans3 = "TCP establishes a connection via SYN, SYN-ACK, and ACK packets."

    assert RAGEvaluator.is_abstention_response(ans1) is True
    assert RAGEvaluator.is_abstention_response(ans2) is True
    assert RAGEvaluator.is_abstention_response(ans3) is False
    assert RAGEvaluator.is_abstention_response("anything", insufficient_evidence_flag=True) is True


@pytest.mark.rag
@pytest.mark.unit
def test_faithfulness_and_citation_evaluation():
    """Verifies claim faithfulness and citation precision/recall scoring."""
    context = (
        "The Transmission Control Protocol (TCP) provides reliable, ordered stream delivery "
        "using a three-way handshake involving SYN, SYN-ACK, and ACK packets."
    )
    answer = "TCP provides reliable, ordered stream delivery using a three-way handshake."
    faithfulness = RAGEvaluator.evaluate_faithfulness(answer, context)
    assert faithfulness >= 0.9

    # Unfaithful answer containing hallucinations
    hallucinated = "TCP operates at the physical layer using fiber optic light refraction."
    unfaithful_score = RAGEvaluator.evaluate_faithfulness(hallucinated, context)
    assert unfaithful_score < 0.5


@pytest.mark.rag
@pytest.mark.integration
def test_end_to_end_rag_evaluation_run(tmp_path: Path):
    """Executes full evaluation runner on the benchmark dataset and verifies metric thresholds."""
    repo_root = Path(__file__).resolve().parents[2]
    dataset_path = repo_root / "data" / "retrieval_eval" / "e2e_rag_eval.jsonl"
    corpus_path = repo_root / "data" / "retrieval_eval" / "corpus.jsonl"
    out_path = tmp_path / "rag_eval_test.json"

    report = run_e2e_rag_evaluation(dataset_path, corpus_path, out_path)

    # 1. Verification of evaluation coverage
    assert report.total_queries == 20
    assert report.answerable_queries == 16
    assert report.unanswerable_queries == 4

    # 2. Abstention accuracy threshold (must be 100% on out-of-domain set)
    assert report.abstention_accuracy >= 0.95

    # 3. Grounded generation quality thresholds
    assert report.mean_faithfulness >= 0.85
    assert report.mean_correctness_f1 >= 0.50
    assert report.mean_completeness >= 0.70
    assert report.mean_citation_precision >= 0.80

    # 4. Retrieval comparisons exist
    assert "Dense_Semantic" in report.retrieval_comparison
    assert "BM25_Lexical" in report.retrieval_comparison
    assert "Hybrid_RRF" in report.retrieval_comparison
    assert "Hybrid_Reranked" in report.retrieval_comparison

    # Cross-Encoder Reranked Hybrid should achieve high Recall@5 and MRR
    reranked = report.retrieval_comparison["Hybrid_Reranked"]
    assert reranked["Recall@5"] >= 0.70
    assert reranked["MRR"] >= 0.70
