# Knovera Topic Discovery Dataset Repository

This directory contains versioned, unsupervised document chunk clustering datasets and snapshots for Knovera's Topic Discovery engine (Phase 6).

## Directory Structure

```text
data/topic_clustering/
├── README.md                                  # Dataset architecture and invariant documentation
├── schemas/
│   └── clustering_record.schema.json          # JSON Schema for chunk records
└── snapshots/
    └── <snapshot_id>/
        ├── embeddings.npy                     # Binary NumPy array (N, 384), float32, L2-normalized
        ├── records.jsonl                      # Aligned per-chunk metadata records (JSONL)
        └── manifest.json                      # Cryptographic provenance and metadata manifest
```

## Dataset Invariants & Rules

1. **Workspace Multi-Tenant Isolation**:
   - Every snapshot is strictly scoped to a single `workspace_id`.
   - Never mix or cluster document chunks across workspaces.

2. **Authoritative Canonical Provenance**:
   - PostgreSQL (`document_chunks` joined with `documents`) is the canonical source of truth.
   - Chunks from soft-deleted documents (`Document.deleted_at IS NOT NULL`) are strictly excluded.
   - ChromaDB serves as an acceleration cache to reuse precomputed vector embeddings; any missing vectors are dynamically generated via the registered `EmbeddingProvider`.

3. **Mathematical Normalization**:
   - Embeddings are explicitly $L_2$-unit normalized:
     $$x_{\text{norm}} = \frac{x}{\|x\|_2}$$
   - This ensures Euclidean distance in K-Means corresponds monotonically to cosine distance:
     $$\|u - v\|_2^2 = 2 - 2 \langle u, v \rangle = 2 - 2 \cos(u, v)$$
     enabling Euclidean K-Means to discover genuine directional semantic clusters.

4. **Cryptographic Reproducibility**:
   - `manifest.json` contains a SHA-256 `corpus_hash` calculated across the sorted content hashes of all member chunks:
     $$\text{corpus\_hash} = \text{SHA-256}\left(\sum_{i \in \text{sorted}} \text{content\_hash}_i\right)$$
   - Loading snapshots revalidates vector finiteness, matrix shape, and hash integrity.
