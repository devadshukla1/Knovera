"""Tests for Reciprocal Rank Fusion (RRF) (Phase 4 C4.3)."""

import uuid
import pytest

from backend.app.rag.retrieval.rrf import FusedCandidate, ReciprocalRankFusion


def test_rrf_formula_and_deduplication():
    # Setup candidate UUIDs
    a = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    c = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    d = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

    # Dense ranking: 1: A, 2: B, 3: C
    dense_list = [(a, 0.15), (b, 0.25), (c, 0.35)]
    # BM25 ranking: 1: B, 2: D, 3: A
    bm25_list = [(b, 12.5), (d, 8.0), (a, 5.2)]

    rrf = ReciprocalRankFusion(k=60)
    fused = rrf.fuse(
        ranked_lists={
            "semantic": dense_list,
            "bm25": bm25_list,
        },
        top_k=10,
    )

    # Expected calculations:
    # A: dense rank 1 (1/61) + bm25 rank 3 (1/63) = 0.01639344 + 0.01587301 = 0.03226646
    # B: dense rank 2 (1/62) + bm25 rank 1 (1/61) = 0.01612903 + 0.01639344 = 0.03252247
    # C: dense rank 3 (1/63) = 0.01587301
    # D: bm25 rank 2 (1/62) = 0.01612903
    #
    # Expected ordering:
    # 1. B (~0.03252)
    # 2. A (~0.03227)
    # 3. D (~0.01613)
    # 4. C (~0.01587)

    assert len(fused) == 4
    assert fused[0].chunk_id == b
    assert fused[0].rank == 1
    assert fused[0].dense_rank == 2
    assert fused[0].bm25_rank == 1
    assert fused[0].vector_distance == 0.25
    assert fused[0].bm25_score == 12.5
    assert "semantic" in fused[0].retrieval_sources and "bm25" in fused[0].retrieval_sources
    assert pytest.approx(fused[0].rrf_score, rel=1e-5) == (1 / 62) + (1 / 61)

    assert fused[1].chunk_id == a
    assert fused[1].rank == 2
    assert fused[1].dense_rank == 1
    assert fused[1].bm25_rank == 3
    assert pytest.approx(fused[1].rrf_score, rel=1e-5) == (1 / 61) + (1 / 63)

    assert fused[2].chunk_id == d
    assert fused[2].rank == 3
    assert fused[2].dense_rank is None
    assert fused[2].bm25_rank == 2
    assert pytest.approx(fused[2].rrf_score, rel=1e-5) == (1 / 62)

    assert fused[3].chunk_id == c
    assert fused[3].rank == 4
    assert fused[3].dense_rank == 3
    assert fused[3].bm25_rank is None
    assert pytest.approx(fused[3].rrf_score, rel=1e-5) == (1 / 63)


def test_rrf_custom_k_parameter():
    a = uuid.uuid4()
    b = uuid.uuid4()

    dense_list = [(a, 0.1)]
    bm25_list = [(b, 10.0)]

    rrf = ReciprocalRankFusion(k=10)
    fused = rrf.fuse(
        ranked_lists={
            "semantic": dense_list,
            "bm25": bm25_list,
        },
        top_k=2,
    )
    # Both are rank 1 in their respective lists: 1 / (10 + 1) = 1/11
    assert pytest.approx(fused[0].rrf_score, rel=1e-5) == 1 / 11
    assert pytest.approx(fused[1].rrf_score, rel=1e-5) == 1 / 11


def test_rrf_deterministic_tie_breaking():
    # Two chunks with identical score: tie broken by str(chunk_id) ascending
    c1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
    c2 = uuid.UUID("22222222-2222-2222-2222-222222222222")

    # Both rank 1 in different single-retriever runs
    fused = ReciprocalRankFusion(k=60).fuse(
        ranked_lists={
            "retriever1": [(c2, 1.0)],
            "retriever2": [(c1, 1.0)],
        },
        top_k=10,
    )
    assert len(fused) == 2
    # Both have score 1/61. Tied. c1 < c2 lexicographically, so c1 must come first.
    assert fused[0].chunk_id == c1
    assert fused[1].chunk_id == c2


def test_rrf_top_k_truncation():
    chunks = [(uuid.uuid4(), float(i)) for i in range(1, 20)]
    fused = ReciprocalRankFusion(k=60).fuse(
        ranked_lists={"semantic": chunks},
        top_k=5,
    )
    assert len(fused) == 5
    assert [f.rank for f in fused] == [1, 2, 3, 4, 5]


def test_rrf_empty_lists():
    rrf = ReciprocalRankFusion(k=60)
    assert rrf.fuse(ranked_lists={}, top_k=10) == []
    assert rrf.fuse(ranked_lists={"semantic": [], "bm25": []}, top_k=10) == []
