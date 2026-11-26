"""Evidence deduplication for context construction (Phase 3 C3.5)."""

import hashlib
from typing import List, Set, Tuple

from backend.app.rag.retrieval.schemas import SemanticSearchResult


class EvidenceDeduplicator:
    """Removes redundant chunks while preserving highest-ranked evidence."""

    def deduplicate(
        self,
        results: List[SemanticSearchResult],
    ) -> Tuple[List[SemanticSearchResult], int]:
        """Filters duplicate chunk IDs and identical text content hashes.

        Returns:
            Tuple of (deduplicated_results, removed_duplicates_count).
        """
        seen_chunk_ids: Set[str] = set()
        seen_content_hashes: Set[str] = set()

        deduped: List[SemanticSearchResult] = []
        omitted_count = 0

        for r in results:
            c_id_str = str(r.chunk_id)
            if c_id_str in seen_chunk_ids:
                omitted_count += 1
                continue

            # Compute content hash
            norm_content = " ".join(r.content.split()).lower()
            c_hash = hashlib.sha256(norm_content.encode("utf-8")).hexdigest()

            if c_hash in seen_content_hashes:
                omitted_count += 1
                continue

            seen_chunk_ids.add(c_id_str)
            seen_content_hashes.add(c_hash)
            deduped.append(r)

        return deduped, omitted_count
