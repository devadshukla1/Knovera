# Knovera Synthetic Smoke-Test Retrieval Dataset (Phase 4 C4.6)

## 1. Overview
The `knovera_synthetic_smoke_test` dataset is an authoritative benchmark for evaluating information retrieval (IR) and reranking pipelines across the Knovera platform. It enables standardized, reproducible comparisons among:
1. **Dense Semantic Retrieval**: Bi-encoder vector search in ChromaDB (`all-MiniLM-L6-v2`)
2. **Lexical Retrieval**: BM25 Okapi inverted index (`k1=1.5, b=0.75`)
3. **Hybrid RRF Retrieval**: Reciprocal Rank Fusion of Dense + BM25 (`k=60`)
4. **Hybrid RRF + Cross-Encoder Reranking**: Full pipeline with `ms-marco-MiniLM-L-6-v2`

## 2. Directory Structure
```
data/retrieval_eval/
├── manifest.json            # Dataset metadata, version, splits, and grading rubric
├── corpus.jsonl             # 24 academic chunks across CS, Biology, and Physics
├── queries.jsonl            # 16 queries (8 dev, 8 test) across 4 query categories
├── qrels.tsv                # Graded ground-truth relevance judgments (0 to 3)
├── schemas/
│   ├── corpus.schema.json   # JSON schema for corpus chunks
│   ├── query.schema.json    # JSON schema for queries
│   └── qrels.schema.json    # Schema for relevance judgments
└── README.md                # Dataset documentation and annotation guidelines
```

## 3. Dataset Splits
- **`dev` (8 queries)**: Query IDs `q_001` through `q_008`. Used for parameter tuning (BM25 parameters `k1` and `b`, RRF parameter `k`, and reranker candidate depth `candidate_k`).
- **`test` (8 queries)**: Query IDs `q_009` through `q_016`. Held-out test split for evaluating generalized retrieval performance.

## 4. Query Categories
1. **Technical Acronym**: Queries containing domain acronyms (e.g., `TCP`, `CRISPR-Cas9`, `PAM`, `BCS`, `SSA`). Tests lexical matching vs semantic understanding.
2. **Exact Keyword**: Queries with highly specific terminology (e.g., `MemTable`, `SSTables`, `Phosphofructokinase-1`).
3. **Conceptual**: Queries seeking functional mechanisms without exact keywords (e.g., consensus mechanisms, Bell's theorem, oxidative phosphorylation).
4. **Comparative**: Queries requiring multiple entity comparisons (e.g., CD4+ vs CD8+ T cells, UDP vs TCP, Carnot cycle efficiency).

## 5. Relevance Grading Rubric
- **Grade 3 (Highly Relevant)**: Directly answers the query with authoritative technical evidence.
- **Grade 2 (Relevant)**: Addresses major facets of the query or provides essential prerequisite context.
- **Grade 1 (Marginal)**: Related domain or topical background, but does not directly answer the specific question.
- **Grade 0 (Not Relevant)**: Irrelevant content outside the query scope.
