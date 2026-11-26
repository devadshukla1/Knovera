"""In-memory ChromaDB test double for isolated unit and integration tests (Phase 3 C3.2).

Implements the exact Chroma Collection API with NumPy-based cosine distance calculation
and metadata filtering ($and, $in, direct match).
"""

from typing import Any, Dict, List, Optional
import numpy as np


class InMemoryChromaCollection:
    """In-memory vector collection supporting cosine distance search and metadata filtering."""

    def __init__(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.metadata = metadata or {"hnsw:space": "cosine"}
        self._records: Dict[str, Dict[str, Any]] = {}

    def count(self) -> int:
        return len(self._records)

    def upsert(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        for idx, rec_id in enumerate(ids):
            meta = metadatas[idx] if metadatas else {}
            doc = documents[idx] if documents else None
            self._records[rec_id] = {
                "id": rec_id,
                "embedding": np.array(embeddings[idx], dtype=np.float32),
                "metadata": meta,
                "document": doc,
            }

    def _matches_filter(self, record_meta: Dict[str, Any], where: Optional[Dict[str, Any]]) -> bool:
        if not where:
            return True

        if "$and" in where:
            return all(self._matches_filter(record_meta, cond) for cond in where["$and"])

        for k, v in where.items():
            if k == "$and":
                continue
            rec_val = record_meta.get(k)
            if isinstance(v, dict) and "$in" in v:
                if rec_val not in v["$in"]:
                    return False
            else:
                if rec_val != v:
                    return False
        return True

    def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not query_embeddings or not self._records:
            return {"ids": [[]], "distances": [[]], "metadatas": [[]]}

        query_vec = np.array(query_embeddings[0], dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)

        candidates = []
        for rec_id, data in self._records.items():
            if self._matches_filter(data["metadata"], where):
                v = data["embedding"]
                v_norm = np.linalg.norm(v)
                if q_norm > 0 and v_norm > 0:
                    cos_sim = float(np.dot(query_vec, v) / (q_norm * v_norm))
                    # Cosine distance = 1 - cosine similarity
                    dist = max(0.0, 1.0 - cos_sim)
                else:
                    dist = 1.0
                candidates.append((rec_id, dist, data["metadata"]))

        # Sort by ascending distance (nearest first)
        candidates.sort(key=lambda x: x[1])
        top_candidates = candidates[:n_results]

        ids = [c[0] for c in top_candidates]
        distances = [c[1] for c in top_candidates]
        metadatas = [c[2] for c in top_candidates]

        return {
            "ids": [ids],
            "distances": [distances],
            "metadatas": [metadatas],
        }

    def get(
        self,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        matching_ids = []
        matching_meta = []
        for rec_id, data in self._records.items():
            if self._matches_filter(data["metadata"], where):
                matching_ids.append(rec_id)
                matching_meta.append(data["metadata"])
        return {"ids": matching_ids, "metadatas": matching_meta}

    def delete(self, where: Optional[Dict[str, Any]] = None) -> None:
        if not where:
            self._records.clear()
            return

        to_remove = [rec_id for rec_id, data in self._records.items() if self._matches_filter(data["metadata"], where)]
        for rec_id in to_remove:
            self._records.pop(rec_id, None)


class InMemoryChromaClient:
    """In-memory client double for chromadb.HttpClient."""

    def __init__(self) -> None:
        self._collections: Dict[str, InMemoryChromaCollection] = {}

    def get_or_create_collection(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InMemoryChromaCollection:
        if name not in self._collections:
            self._collections[name] = InMemoryChromaCollection(name=name, metadata=metadata)
        return self._collections[name]

    def get_collection(self, name: str) -> InMemoryChromaCollection:
        if name not in self._collections:
            raise ValueError(f"Collection {name} not found")
        return self._collections[name]

    def delete_collection(self, name: str) -> None:
        self._collections.pop(name, None)

    def list_collections(self) -> List[InMemoryChromaCollection]:
        return list(self._collections.values())

    def heartbeat(self) -> int:
        return 1
