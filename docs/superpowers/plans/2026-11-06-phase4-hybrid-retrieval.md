# Phase 4: Hybrid Retrieval & Reciprocal Rank Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 4 retrieval improvements: C4.1 BM25 Lexical Retrieval, C4.2 Hybrid Retrieval, and C4.3 Reciprocal Rank Fusion (RRF), integrating them into Knovera's core RAG engine while preserving PostgreSQL authority, workspace isolation, and citation mapping.

**Architecture:** Pure Python Okapi BM25 index built directly from PostgreSQL chunks with bounded LRU workspace caching and thread-safe build locks; generic Reciprocal Rank Fusion component with deterministic tie-breaking; and a parallel HybridRetriever combining dense and lexical candidate pools into an authoritative PostgreSQL-hydrated context for GroundedAnswerService.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2, ChromaDB, Sentence Transformers, NumPy / Python standard math, Pytest.

---

## File Structure

- Create: `backend/app/rag/retrieval/bm25/__init__.py`
- Create: `backend/app/rag/retrieval/bm25/tokenizer.py` (Lexical tokenizer preserving technical acronyms, symbols, C++, C#, TCP/IP)
- Create: `backend/app/rag/retrieval/bm25/index.py` (BM25 Okapi in-memory inverted index with exact formulas)
- Create: `backend/app/rag/retrieval/bm25/cache.py` (Thread-safe LRU workspace index cache with invalidation hooks)
- Create: `backend/app/rag/retrieval/bm25/retriever.py` (BM25Retriever service with PostgreSQL hydration)
- Create: `backend/app/rag/retrieval/rrf.py` (ReciprocalRankFusion algorithm with deterministic tie-breaking)
- Create: `backend/app/rag/retrieval/hybrid_retriever.py` (HybridRetriever orchestrator combining dense + BM25)
- Modify: `backend/app/rag/retrieval/schemas.py` (Add BM25 and Hybrid search request/result/response schemas)
- Modify: `backend/app/core/config.py` (Add RETRIEVAL_MODE, BM25_*, RRF_*, DENSE_RETRIEVAL_TOP_K settings)
- Modify: `.env.example` (Document new retrieval parameters)
- Modify: `backend/app/rag/orchestration/answer_generator.py` (Plug hybrid retrieval into GroundedAnswerService)
- Modify: `backend/app/ingestion/pipeline/orchestrator.py` (Add BM25 cache invalidation hook on document ready)
- Modify: `backend/app/api/v1/endpoints/documents.py` (Add BM25 cache invalidation hook on document delete)
- Modify: `backend/app/api/v1/endpoints/search.py` (Add /search/hybrid and /search/bm25 endpoints)
- Create: `backend/tests/test_bm25_retrieval.py`
- Create: `backend/tests/test_rrf.py`
- Create: `backend/tests/test_hybrid_retrieval.py`
- Create: `backend/tests/test_e2e_hybrid_rag.py`
- Create: `progress/PHASE_04_REPORT.md`

---

### Task 1: Configuration & Schemas (C4.1, C4.2, C4.3)

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Modify: `backend/app/rag/retrieval/schemas.py`

- [ ] **Step 1: Write schemas and configuration settings**
  Add `RETRIEVAL_MODE`, `DENSE_RETRIEVAL_TOP_K`, `BM25_RETRIEVAL_TOP_K`, `BM25_K1`, `BM25_B`, `BM25_INDEX_CACHE_MAX_WORKSPACES`, `HYBRID_RETRIEVAL_TOP_K`, `RRF_K` to `Settings`.
  Add `BM25SearchResult`, `BM25SearchResponse`, `HybridSearchResult`, `HybridSearchRequest`, `HybridSearchResponse` to `schemas.py`.
- [ ] **Step 2: Run existing tests to verify zero regressions**
  Run: `.\.venv\Scripts\python -m pytest backend/tests/test_config.py`
- [ ] **Step 3: Commit / Checkpoint**

---

### Task 2: C4.1 — Dedicated Lexical Tokenizer & Preprocessor

**Files:**
- Create: `backend/app/rag/retrieval/bm25/tokenizer.py`
- Create: `backend/tests/test_bm25_retrieval.py`

- [ ] **Step 1: Write failing tests for BM25Tokenizer**
  Test technical terms (`C++`, `C#`, `FastAPI`, `PostgreSQL`, `BM25`, `TCP/IP`, `GPT-4`, `Machine Learning`), case folding, unicode normalization, repeated terms.
- [ ] **Step 2: Run test to verify failure**
  Run: `.\.venv\Scripts\python -m pytest backend/tests/test_bm25_retrieval.py::test_tokenizer_technical_terms`
- [ ] **Step 3: Implement BM25Tokenizer**
  Implement regex matching tokens with technical symbol preservation and Unicode NFKC normalization.
- [ ] **Step 4: Run tests to verify they pass**
  Run: `.\.venv\Scripts\python -m pytest backend/tests/test_bm25_retrieval.py`

---

### Task 3: C4.1 — BM25 Okapi Inverted Index & Math

**Files:**
- Create: `backend/app/rag/retrieval/bm25/index.py`
- Test: `backend/tests/test_bm25_retrieval.py`

- [ ] **Step 1: Write failing tests for BM25WorkspaceIndex**
  Test exact Okapi scores against manual calculations, term frequency saturation ($k_1$), document length normalization ($b$), empty corpus, rare vs common term IDF.
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement BM25WorkspaceIndex**
  Inverted index structure, document lengths, average document length $avgdl$, smoothed Okapi IDF:
  `idf = math.log(1.0 + (N - n_t + 0.5) / (n_t + 0.5))`
  Document filtering support.
- [ ] **Step 4: Run tests to verify they pass**

---

### Task 4: C4.1 — BM25 Cache & Invalidation Lifecycle

**Files:**
- Create: `backend/app/rag/retrieval/bm25/cache.py`
- Create: `backend/app/rag/retrieval/bm25/retriever.py`
- Modify: `backend/app/ingestion/pipeline/orchestrator.py`
- Modify: `backend/app/api/v1/endpoints/documents.py`
- Test: `backend/tests/test_bm25_retrieval.py`

- [ ] **Step 1: Write failing tests for cache lifecycle, concurrency lock, and invalidation**
  Test index caching, LRU eviction, invalidation on document additions/deletions, and PostgreSQL hydration.
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement BM25IndexCache and BM25Retriever**
  Thread-safe lock per workspace, LRU bound, PostgreSQL query for chunks, ResultHydrator integration.
  Wire invalidation hooks into `orchestrator.py` and `documents.py`.
- [ ] **Step 4: Run tests to verify they pass**

---

### Task 5: C4.3 — Reciprocal Rank Fusion (RRF)

**Files:**
- Create: `backend/app/rag/retrieval/rrf.py`
- Create: `backend/tests/test_rrf.py`

- [ ] **Step 1: Write failing tests for ReciprocalRankFusion**
  Test standard formula: $RRF(d) = \sum \frac{1}{k + rank_r(d)}$, deduplication across dense and BM25, deterministic tie-breaking on `chunk_id`, custom $k$, top-k limit.
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement ReciprocalRankFusion**
  Deduplication, 1-based ranks, score accumulation, deterministic secondary sort key, candidate provenance.
- [ ] **Step 4: Run tests to verify they pass**

---

### Task 6: C4.2 — Hybrid Retrieval Orchestration

**Files:**
- Create: `backend/app/rag/retrieval/hybrid_retriever.py`
- Modify: `backend/app/api/v1/endpoints/search.py`
- Create: `backend/tests/test_hybrid_retrieval.py`

- [ ] **Step 1: Write failing tests for HybridRetriever**
  Test parallel execution, candidate pool merging, RRF invocation, PostgreSQL hydration with ranking preservation, fallback when one retriever is empty, retrieval modes (`hybrid`, `semantic`, `bm25`).
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement HybridRetriever & Search Endpoints**
  Orchestrate dense + BM25 retrieval, apply RRF, hydrate via PostgreSQL, expose `/search/hybrid` and `/search/bm25`.
- [ ] **Step 4: Run tests to verify they pass**

---

### Task 7: Full System Integration (GroundedAnswerService & E2E RAG)

**Files:**
- Modify: `backend/app/rag/orchestration/answer_generator.py`
- Create: `backend/tests/test_e2e_hybrid_rag.py`

- [ ] **Step 1: Integrate HybridRetriever into GroundedAnswerService**
  Use `HybridRetriever` by default (respecting `settings.RETRIEVAL_MODE`), passing fused candidates into `ContextBuilder`.
- [ ] **Step 2: Write and execute end-to-end integration test**
  Verify keyword-specific queries retrieve exact acronyms via BM25 and semantic queries retrieve concepts via dense retrieval, citations map accurately to source pages, and conversation history is preserved.
- [ ] **Step 3: Run full regression test suite**
  Run: `.\.venv\Scripts\python -m pytest backend/tests tests/e2e -v`

---

### Task 8: Documentation & Phase 4 Report

**Files:**
- Modify: `docs/trd.md`
- Modify: `docs/implementation_plan.md`
- Create: `progress/PHASE_04_REPORT.md`

- [ ] **Step 1: Update technical documentation**
- [ ] **Step 2: Write complete PHASE_04_REPORT.md**
- [ ] **Step 3: Final verification and return control**
