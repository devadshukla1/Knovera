"""Unit tests for Cross-Encoder model manager, reranker service, and candidate selection (Phase 4 C4.4–C4.5)."""

import math
from typing import Any, List
from unittest.mock import MagicMock, patch
import uuid
import pytest

from backend.app.core.config import Settings
from backend.app.rag.reranker import (
    CrossEncoderModelManager,
    CrossEncoderReranker,
    FakeCrossEncoder,
    InferenceError,
    InvalidScoreError,
    ModelLoadError,
    format_query_passage_pair,
)


class DummyCandidate:
    def __init__(self, chunk_id: str, content: str, section_title: str = None, rank: int = 1):
        self.chunk_id = chunk_id
        self.content = content
        self.section_title = section_title
        self.rank = rank


def test_format_query_passage_pair():
    # Without section title
    pair = format_query_passage_pair("  What is TCP? ", " TCP provides reliable stream delivery. ")
    assert pair == ["What is TCP?", "TCP provides reliable stream delivery."]

    # With section title
    pair2 = format_query_passage_pair("Query", "Passage body", "Section Header")
    assert pair2 == ["Query", "Section Header\nPassage body"]


def test_cross_encoder_model_manager_singleton():
    CrossEncoderModelManager.reset()
    mgr1 = CrossEncoderModelManager.get_instance()
    mgr2 = CrossEncoderModelManager.get_instance()
    assert mgr1 is mgr2

    # Device resolution
    mgr1.settings = Settings(CROSS_ENCODER_DEVICE="cpu")
    mgr1._resolved_device = None
    assert mgr1.resolve_device() == "cpu"

    CrossEncoderModelManager.reset()


def test_cross_encoder_model_manager_readiness_and_mock():
    CrossEncoderModelManager.reset()
    mgr = CrossEncoderModelManager.get_instance()
    fake_model = FakeCrossEncoder(fixed_score=4.2)
    mgr.set_model(fake_model)

    ready, info = mgr.check_readiness()
    assert ready is True
    assert info["ready"] is True
    assert info["model_class"] == "FakeCrossEncoder"

    CrossEncoderModelManager.reset()


def test_cross_encoder_model_manager_load_failure():
    CrossEncoderModelManager.reset()
    mgr = CrossEncoderModelManager.get_instance()
    mgr.settings = Settings(CROSS_ENCODER_MODEL_ID="nonexistent/model-xyz-123")

    with patch("sentence_transformers.CrossEncoder", side_effect=Exception("Model not found")):
        with pytest.raises(ModelLoadError) as exc_info:
            mgr.get_model()
        assert "nonexistent/model-xyz-123" in str(exc_info.value)

    CrossEncoderModelManager.reset()


def test_cross_encoder_reranker_scoring_and_batching():
    fake_model = FakeCrossEncoder()
    mgr = CrossEncoderModelManager.get_instance()
    mgr.set_model(fake_model)

    reranker = CrossEncoderReranker(manager=mgr)
    pairs = [
        ["TCP handshake", "TCP manages connection establishment via three-way handshake."],
        ["quantum entanglement", "Mitochondrial oxidative phosphorylation generates ATP."],
    ]
    scores = reranker.score_pairs(pairs)
    assert len(scores) == 2
    # The first pair shares TCP and handshake -> higher logit than unrelated second pair
    assert scores[0] > scores[1]


def test_cross_encoder_reranker_rejects_nan_and_inf():
    mock_model = MagicMock()
    mock_model.predict.return_value = [float("nan"), 1.5]

    mgr = CrossEncoderModelManager.get_instance()
    mgr.set_model(mock_model)

    reranker = CrossEncoderReranker(manager=mgr)
    with pytest.raises(InvalidScoreError):
        reranker.score_pairs([["q", "p1"], ["q", "p2"]])

    mock_model.predict.return_value = [float("inf")]
    with pytest.raises(InvalidScoreError):
        reranker.score_pairs([["q", "p"]])


def test_cross_encoder_reranker_deterministic_sorting():
    mock_model = MagicMock()
    # Return scores: cand1 -> 2.0, cand2 -> 5.0, cand3 -> 5.0 (tie), cand4 -> 0.5
    mock_model.predict.return_value = [2.0, 5.0, 5.0, 0.5]

    mgr = CrossEncoderModelManager.get_instance()
    mgr.set_model(mock_model)

    reranker = CrossEncoderReranker(manager=mgr)

    cand1 = DummyCandidate("c1", "text 1", rank=1)
    cand2 = DummyCandidate("c2", "text 2", rank=2)
    cand3 = DummyCandidate("c3", "text 3", rank=3)
    cand4 = DummyCandidate("c4", "text 4", rank=4)

    candidates = [cand1, cand2, cand3, cand4]

    reranked, was_reranked = reranker.rerank_candidates(
        query="query",
        candidates=candidates,
        get_content=lambda c: c.content,
        get_section_title=lambda c: c.section_title,
        get_rrf_rank=lambda c: c.rank,
        get_chunk_id=lambda c: c.chunk_id,
        top_k=3,
    )

    assert was_reranked is True
    assert len(reranked) == 3
    # cand2 and cand3 tied at score 5.0. cand2 had rank 2 < rank 3, so cand2 is first, cand3 is second
    assert reranked[0][0].chunk_id == "c2"
    assert reranked[0][1] == 5.0
    assert reranked[0][2] == 1

    assert reranked[1][0].chunk_id == "c3"
    assert reranked[1][1] == 5.0
    assert reranked[1][2] == 2

    # cand1 had score 2.0
    assert reranked[2][0].chunk_id == "c1"
    assert reranked[2][1] == 2.0
    assert reranked[2][2] == 3


def test_cross_encoder_failure_policy_rrf_only():
    mock_model = MagicMock()
    mock_model.predict.side_effect = RuntimeError("GPU out of memory")

    mgr = CrossEncoderModelManager.get_instance()
    mgr.set_model(mock_model)

    settings = Settings(RERANKER_FAILURE_POLICY="rrf_only")
    reranker = CrossEncoderReranker(manager=mgr, settings=settings)

    cand1 = DummyCandidate("c1", "text 1", rank=1)
    cand2 = DummyCandidate("c2", "text 2", rank=2)

    results, was_reranked = reranker.rerank_candidates(
        query="query",
        candidates=[cand1, cand2],
        get_content=lambda c: c.content,
        get_section_title=lambda c: c.section_title,
        get_rrf_rank=lambda c: c.rank,
        get_chunk_id=lambda c: c.chunk_id,
    )

    assert was_reranked is False
    assert len(results) == 2
    assert results[0][0].chunk_id == "c1"
    assert results[1][0].chunk_id == "c2"


def test_cross_encoder_failure_policy_error():
    mock_model = MagicMock()
    mock_model.predict.side_effect = RuntimeError("Inference crash")

    mgr = CrossEncoderModelManager.get_instance()
    mgr.set_model(mock_model)

    settings = Settings(RERANKER_FAILURE_POLICY="error")
    reranker = CrossEncoderReranker(manager=mgr, settings=settings)

    cand1 = DummyCandidate("c1", "text 1", rank=1)

    with pytest.raises(InferenceError):
        reranker.rerank_candidates(
            query="query",
            candidates=[cand1],
            get_content=lambda c: c.content,
        )
