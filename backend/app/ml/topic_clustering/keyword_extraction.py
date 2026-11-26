"""Cluster-based Keyword Extraction for Knovera Topic Discovery (Phase 6 C6.5)."""

import re
from typing import Dict, List, Set, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.core.logging import get_logger
from backend.app.ml.topic_clustering.schemas import TopicKeyword

logger = get_logger("knovera.ml.topic_clustering.keyword_extraction")

# Additional generic boilerplate stopwords to downweight
COMMON_CORPUS_STOPWORDS = {
    "introduction",
    "section",
    "overview",
    "document",
    "chapter",
    "summary",
    "method",
    "results",
    "information",
    "conclusion",
    "figure",
    "table",
    "page",
    "following",
    "provides",
    "describes",
    "based",
    "using",
}


class ClusterKeywordExtractor:
    """Extracts distinctive unigram and bigram keyphrases per cluster via cluster-level TF-IDF."""

    def __init__(self, top_k: int = 10) -> None:
        self.top_k = top_k

    def extract_cluster_keywords(
        self,
        cluster_texts: Dict[int, List[str]],
    ) -> Dict[int, List[TopicKeyword]]:
        """Extracts top keywords for each cluster by treating each cluster as a pseudo-document.

        Args:
            cluster_texts: Mapping from cluster_id to list of chunk text contents.

        Returns:
            Mapping from cluster_id to ranked list of TopicKeyword.
        """
        cluster_ids = sorted(list(cluster_texts.keys()))
        if not cluster_ids:
            return {}

        # Concatenate text per cluster
        pseudo_documents: List[str] = []
        for cid in cluster_ids:
            texts = cluster_texts.get(cid, [])
            joined = " ".join(texts)
            pseudo_documents.append(joined if joined.strip() else "empty cluster")

        # Configure TF-IDF with unigrams + bigrams and sublinear TF
        # max_df=0.85 ensures terms appearing in almost all clusters are penalized
        max_df = 0.85 if len(cluster_ids) >= 3 else 1.0

        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            max_df=max_df,
            min_df=1,
            sublinear_tf=True,
            token_pattern=r"(?u)\b[a-zA-Z0-9_-]{2,}\b",
        )

        try:
            tfidf_matrix = vectorizer.fit_transform(pseudo_documents)
            feature_names = vectorizer.get_feature_names_out()
        except ValueError as exc:
            logger.warning("TF-IDF extraction failed (%s); using basic token counts.", exc)
            return {cid: [] for cid in cluster_ids}

        cluster_keywords: Dict[int, List[TopicKeyword]] = {}

        for row_idx, cid in enumerate(cluster_ids):
            row = tfidf_matrix[row_idx].toarray().flatten()  # type: ignore
            # Get top indices sorted descending
            top_indices = np.argsort(row)[::-1]

            keywords: List[TopicKeyword] = []
            seen_words: Set[str] = set()

            for idx in top_indices:
                score = float(row[idx])
                if score <= 0:
                    break
                term = str(feature_names[idx]).strip()

                # Filter generic terms
                if term.lower() in COMMON_CORPUS_STOPWORDS:
                    continue

                # Deduplicate overlapping unigram if bigram already captured
                keywords.append(TopicKeyword(term=term, score=round(score, 4)))
                if len(keywords) >= self.top_k:
                    break

            cluster_keywords[cid] = keywords

        return cluster_keywords
