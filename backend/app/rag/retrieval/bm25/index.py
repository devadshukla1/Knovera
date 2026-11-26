"""BM25 Okapi Inverted Index for Workspace Lexical Retrieval (Phase 4 C4.1)."""

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Sequence, Set, Tuple
import uuid

from backend.app.rag.retrieval.bm25.tokenizer import BM25Tokenizer


@dataclass(frozen=True)
class BM25ChunkDocument:
    """Minimal chunk container required for lexical indexing and document scoping."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    workspace_id: uuid.UUID
    content: str


class BM25WorkspaceIndex:
    """In-memory Okapi BM25 inverted index for a single workspace corpus.

    Formulation:
        BM25(D, Q) = sum_{t in Q} IDF(t) * (f(t, D) * (k1 + 1)) / (f(t, D) + k1 * (1 - b + b * (|D| / avgdl)))

    IDF Formulation:
        IDF(t) = ln(1.0 + (N - n(t) + 0.5) / (n(t) + 0.5))
        Where N is corpus size and n(t) is document frequency.
        This smoothed Robertson/Spärck Jones Okapi formulation strictly guarantees IDF(t) >= 0,
        preventing negative term weighting on high-frequency terms while preserving exact rank properties.
    """

    def __init__(
        self,
        workspace_id: uuid.UUID,
        chunks: Sequence[BM25ChunkDocument],
        k1: float = 1.5,
        b: float = 0.75,
        tokenizer: Optional[BM25Tokenizer] = None,
    ) -> None:
        if k1 < 0:
            raise ValueError(f"BM25 parameter k1 must be >= 0, got {k1}")
        if not (0.0 <= b <= 1.0):
            raise ValueError(f"BM25 parameter b must be between 0.0 and 1.0, got {b}")

        self.workspace_id = workspace_id
        self.k1 = k1
        self.b = b
        self.tokenizer = tokenizer or BM25Tokenizer()

        self.corpus_size = len(chunks)
        self.doc_lengths: Dict[uuid.UUID, int] = {}
        self.doc_map: Dict[uuid.UUID, BM25ChunkDocument] = {}
        self.inverted_index: Dict[str, Dict[uuid.UUID, int]] = defaultdict(dict)
        self.doc_frequencies: Dict[str, int] = defaultdict(int)
        self.idf_cache: Dict[str, float] = {}

        total_length = 0
        for chunk in chunks:
            self.doc_map[chunk.chunk_id] = chunk
            tokens = self.tokenizer.tokenize(chunk.content)
            doc_len = len(tokens)
            self.doc_lengths[chunk.chunk_id] = doc_len
            total_length += doc_len

            term_counts = Counter(tokens)
            for term, count in term_counts.items():
                self.inverted_index[term][chunk.chunk_id] = count
                self.doc_frequencies[term] += 1

        self.avgdl = (total_length / self.corpus_size) if self.corpus_size > 0 else 0.0

        # Precompute IDF for all terms in corpus
        for term, n_t in self.doc_frequencies.items():
            self.idf_cache[term] = self._compute_idf(n_t)

    def _compute_idf(self, n_t: int) -> float:
        """Computes smoothed Okapi IDF guaranteeing non-negative value."""
        if self.corpus_size == 0:
            return 0.0
        # Smoothed Okapi formula: ln(1.0 + (N - n(t) + 0.5) / (n(t) + 0.5))
        numerator = self.corpus_size - n_t + 0.5
        denominator = n_t + 0.5
        return math.log(1.0 + max(0.0, numerator / denominator))

    def search(
        self,
        query: str,
        top_k: int = 10,
        document_ids: Optional[Sequence[uuid.UUID]] = None,
    ) -> List[Tuple[uuid.UUID, float]]:
        """Scores and ranks corpus chunks against query terms.

        Args:
            query: Natural language or keyword query string.
            top_k: Maximum number of top-scoring candidates to return.
            document_ids: Optional set of document IDs to restrict search to.

        Returns:
            List of (chunk_id, bm25_score) sorted descending by score with deterministic tie-breaking.
        """
        if self.corpus_size == 0 or not query or top_k <= 0:
            return []

        query_tokens = self.tokenizer.tokenize(query)
        if not query_tokens:
            return []

        allowed_docs: Optional[Set[uuid.UUID]] = set(document_ids) if document_ids else None
        scores: Dict[uuid.UUID, float] = defaultdict(float)

        # Count frequencies in query to support repeated query terms
        query_term_freqs = Counter(query_tokens)

        for term, q_freq in query_term_freqs.items():
            if term not in self.inverted_index:
                continue

            idf = self.idf_cache.get(term, self._compute_idf(self.doc_frequencies.get(term, 0)))
            postings = self.inverted_index[term]

            for chunk_id, f_td in postings.items():
                chunk_doc = self.doc_map[chunk_id]
                if allowed_docs is not None and chunk_doc.document_id not in allowed_docs:
                    continue

                doc_len = self.doc_lengths[chunk_id]
                len_norm = 1.0 - self.b + self.b * (doc_len / self.avgdl) if self.avgdl > 0 else 1.0
                tf_part = (f_td * (self.k1 + 1.0)) / (f_td + self.k1 * len_norm)

                # Query term weight contribution: idf * tf * q_freq
                scores[chunk_id] += idf * tf_part * q_freq

        # Filter strictly positive matches
        positive_matches = [(cid, score) for cid, score in scores.items() if score > 0.0]

        # Deterministic sorting: primary score descending, secondary chunk_id string ascending
        positive_matches.sort(key=lambda item: (-item[1], str(item[0])))

        return positive_matches[:top_k]
