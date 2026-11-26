"""Entity Normalisation Service for Knovera Knowledge Graph (Phase 7 C7.2).

Deduplicates and normalizes entity and concept mentions into canonical identities.
Preserves critical technical punctuation (C++, C#, Node.js, TF-IDF, .NET),
applies a high-accuracy domain alias table, and performs context-aware disambiguation.
"""

import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.ml.knowledge_graph.ontology import (
    ConceptType,
    EntityType,
    infer_node_type,
    is_valid_category,
)
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedConcept,
    ExtractedMention,
    NormalizedNode,
)

# Punctuation-sensitive tokens that must be preserved exactly
PROTECTED_TERMS = {
    "c++": "C++",
    "c#": "C#",
    "node.js": "Node.js",
    "tf-idf": "TF-IDF",
    ".net": ".NET",
    "bm25": "BM25",
    "bm25+": "BM25+",
    "f1-score": "F1-Score",
    "recall@k": "Recall@K",
    "mrr@k": "MRR@K",
    "ndcg@k": "nDCG@K",
}

# Domain alias registry: alias (lowercase) -> canonical name
DOMAIN_ALIAS_TABLE: Dict[str, str] = {
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "ir": "Information Retrieval",
    "information retrieval": "Information Retrieval",
    "svm": "Support Vector Machine",
    "support vector machine": "Support Vector Machine",
    "support vector machines": "Support Vector Machine",
    "rrf": "Reciprocal Rank Fusion",
    "reciprocal rank fusion": "Reciprocal Rank Fusion",
    "bm25": "BM25",
    "bert": "BERT",
    "roberta": "RoBERTa",
    "llm": "Large Language Model",
    "large language model": "Large Language Model",
    "large language models": "Large Language Model",
    "bkt": "Bayesian Knowledge Tracing",
    "bayesian knowledge tracing": "Bayesian Knowledge Tracing",
    "sgd": "Stochastic Gradient Descent",
    "stochastic gradient descent": "Stochastic Gradient Descent",
    "knn": "K-Nearest Neighbors",
    "k-nearest neighbors": "K-Nearest Neighbors",
    "k-nearest neighbours": "K-Nearest Neighbors",
    "pca": "Principal Component Analysis",
    "principal component analysis": "Principal Component Analysis",
    "cnn": "Convolutional Neural Network",
    "convolutional neural network": "Convolutional Neural Network",
    "convolutional neural networks": "Convolutional Neural Network",
    "rnn": "Recurrent Neural Network",
    "recurrent neural network": "Recurrent Neural Network",
    "recurrent neural networks": "Recurrent Neural Network",
    "lstm": "Long Short-Term Memory",
    "long short-term memory": "Long Short-Term Memory",
    "gnn": "Graph Neural Network",
    "graph neural network": "Graph Neural Network",
    "graph neural networks": "Graph Neural Network",
    "kg": "Knowledge Graph",
    "knowledge graph": "Knowledge Graph",
    "knowledge graphs": "Knowledge Graph",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "api": "API",
    "apis": "API",
    "transformer": "Transformer",
    "transformers": "Transformer",
    "vector embedding": "Vector Embedding",
    "vector embeddings": "Vector Embedding",
    "dense embedding": "Dense Embedding",
    "dense embeddings": "Dense Embedding",
    "cosine similarity": "Cosine Similarity",
    "k-means": "K-Means",
    "kmeans": "K-Means",
    "k-means clustering": "K-Means",
    "kmeans clustering": "K-Means",
}

# Homonym disambiguation rules:
# Maps term lower -> dict of disambiguation keys and their context keywords
HOMONYM_DISAMBIGUATION: Dict[str, Dict[str, Dict[str, Any]]] = {
    "apple": {
        "company": {
            "canonical": "Apple Inc.",
            "category": EntityType.ORGANIZATION.value,
            "keywords": {"company", "tech", "iphone", "mac", "ios", "cupertino", "stock", "corporation"},
        },
        "fruit": {
            "canonical": "Apple (fruit)",
            "category": ConceptType.TECHNICAL_CONCEPT.value,
            "keywords": {"fruit", "tree", "eat", "orchard", "cider", "food", "nutrition"},
        },
    },
    "transformer": {
        "ml": {
            "canonical": "Transformer",
            "category": EntityType.MODEL.value,
            "keywords": {"attention", "self-attention", "bert", "gpt", "tokens", "encoder", "decoder", "nlp", "sequence"},
        },
        "electrical": {
            "canonical": "Electrical Transformer",
            "category": EntityType.TECHNOLOGY.value,
            "keywords": {"voltage", "current", "grid", "electrical", "winding", "power", "alternating", "induction"},
        },
    },
}


class EntityNormalizationService:
    """Service that normalizes, deduplicates, and resolves entity & concept mentions."""

    def normalize_term_string(self, term: str) -> str:
        """Punctuation-preserving Unicode NFKC normalization and clean string canonicalization."""
        if not term:
            return ""

        # Normalize unicode NFKC
        cleaned = unicodedata.normalize("NFKC", term).strip()

        # Check protected terms first (case-insensitive)
        lower_term = cleaned.lower()
        if lower_term in PROTECTED_TERMS:
            return PROTECTED_TERMS[lower_term]

        # Check domain alias table
        if lower_term in DOMAIN_ALIAS_TABLE:
            return DOMAIN_ALIAS_TABLE[lower_term]

        # Standard clean-up: collapse multiple whitespaces
        words = cleaned.split()
        return " ".join(words)

    def get_canonical_key(self, term: str) -> str:
        """Computes a normalized matching key for fast clustering comparison."""
        canonical_name = self.normalize_term_string(term)
        lower = canonical_name.lower()
        if lower in PROTECTED_TERMS:
            return lower
        # Standardize hyphens vs spaces
        return lower.replace("-", " ")

    def disambiguate_homonym(
        self,
        surface_term: str,
        context_text: str,
        extracted_category: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """Disambiguates terms with multiple meanings based on local context and category.

        Returns (canonical_name, refined_category).
        """
        lower = surface_term.lower().strip()
        if lower in HOMONYM_DISAMBIGUATION:
            options = HOMONYM_DISAMBIGUATION[lower]
            context_lower = (context_text or "").lower()

            best_match = None
            max_keyword_matches = 0

            for opt_key, opt_data in options.items():
                kw_matches = sum(1 for kw in opt_data["keywords"] if kw in context_lower)
                if opt_data.get("category") == extracted_category:
                    kw_matches += 3

                if kw_matches > max_keyword_matches:
                    max_keyword_matches = kw_matches
                    best_match = opt_data

            if best_match and max_keyword_matches > 0:
                return best_match["canonical"], best_match["category"]

        # Default fallback
        canonical = self.normalize_term_string(surface_term)
        return canonical, extracted_category

    def are_compatible_categories(self, cat1: str, cat2: str) -> bool:
        """Checks whether two categories are compatible for merging into one node."""
        if cat1 == cat2:
            return True
        # Technical concept and technology are broadly compatible
        general_cats = {
            ConceptType.TECHNICAL_CONCEPT.value,
            EntityType.TECHNOLOGY.value,
            ConceptType.METHOD.value,
        }
        if cat1 in general_cats and cat2 in general_cats:
            return True
        return False

    def compute_similarity(self, s1: str, s2: str) -> float:
        """Computes safe string similarity using SequenceMatcher."""
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

    def normalize_and_deduplicate(
        self,
        concepts: List[ExtractedConcept],
        workspace_id: Optional[str] = None,
        context_snippets_by_chunk: Optional[Dict[str, str]] = None,
    ) -> List[NormalizedNode]:
        """Normalizes extracted concept candidates across a workspace into deduplicated canonical nodes."""
        if not concepts:
            return []

        # Group by canonical key
        canonical_groups: Dict[str, List[ExtractedConcept]] = {}

        for c in concepts:
            # Check context snippet if available for disambiguation
            sample_chunk_id = c.mentions[0].chunk_id if c.mentions else None
            context_snippet = context_snippets_by_chunk.get(sample_chunk_id, "") if (sample_chunk_id and context_snippets_by_chunk) else ""

            canonical_name, refined_cat = self.disambiguate_homonym(
                surface_term=c.name,
                context_text=context_snippet or c.description or "",
                extracted_category=c.category,
            )

            canonical_key = self.get_canonical_key(canonical_name)

            # Update candidate attributes
            c.name = canonical_name
            c.normalized_name = canonical_key
            if refined_cat:
                c.category = refined_cat

            if canonical_key not in canonical_groups:
                canonical_groups[canonical_key] = []
            canonical_groups[canonical_key].append(c)

        # Merge groups into NormalizedNodes
        normalized_nodes: List[NormalizedNode] = []

        for key, group in canonical_groups.items():
            primary = group[0]
            # Choose best display name: prefer capitalized / title-cased or domain table canonical
            display_name = primary.name
            for item in group:
                if item.name != item.name.lower() and len(item.name) >= len(display_name):
                    display_name = item.name

            # Collect all mentions and deduplicate by (chunk_id, start_offset, end_offset)
            all_mentions: List[ExtractedMention] = []
            seen_mentions = set()
            all_aliases: Set[str] = set()
            descriptions: List[str] = []

            # Determine best category (prefer more specific over general)
            best_category = primary.category
            for item in group:
                all_aliases.update(item.aliases)
                if item.name.lower() != display_name.lower():
                    all_aliases.add(item.name)
                if item.description and item.description not in descriptions:
                    descriptions.append(item.description)

                for m in item.mentions:
                    m_key = (m.chunk_id, m.start_offset, m.end_offset)
                    if m_key not in seen_mentions:
                        seen_mentions.add(m_key)
                        all_mentions.append(m)

                if item.category != ConceptType.TECHNICAL_CONCEPT.value and is_valid_category(item.category):
                    best_category = item.category

            chosen_desc = descriptions[0] if descriptions else None

            node = NormalizedNode(
                workspace_id=workspace_id,
                name=display_name,
                normalized_name=key,
                category=best_category,
                node_type=infer_node_type(best_category).value,
                description=chosen_desc,
                aliases=sorted(list(all_aliases)),
                mentions=all_mentions,
            )
            normalized_nodes.append(node)

        # Second pass: Fuzzy / plural merge for close variants (e.g. "Transformer" and "Transformers")
        # only when strictly safe (similarity >= 0.92, compatible categories, not protected terms)
        merged_nodes = self._merge_close_variants(normalized_nodes)

        return merged_nodes

    def _merge_close_variants(self, nodes: List[NormalizedNode]) -> List[NormalizedNode]:
        """Merges plural forms or slight token variants with high precision."""
        if len(nodes) <= 1:
            return nodes

        retained: List[NormalizedNode] = []
        skip_indices: Set[int] = set()

        for i in range(len(nodes)):
            if i in skip_indices:
                continue

            current = nodes[i]

            for j in range(i + 1, len(nodes)):
                if j in skip_indices:
                    continue

                candidate = nodes[j]

                # Do not merge protected terms like C and C++
                if current.normalized_name in PROTECTED_TERMS or candidate.normalized_name in PROTECTED_TERMS:
                    continue

                # Check category compatibility
                if not self.are_compatible_categories(current.category, candidate.category):
                    continue

                # Check plural relationship (e.g. "embedding" vs "embeddings")
                is_plural_pair = (
                    current.normalized_name + "s" == candidate.normalized_name
                    or candidate.normalized_name + "s" == current.normalized_name
                )

                sim = self.compute_similarity(current.normalized_name, candidate.normalized_name)

                if is_plural_pair or (sim >= 0.94 and abs(len(current.name) - len(candidate.name)) <= 2):
                    # Merge candidate into current
                    # Prefer singular or shorter display name for plurals
                    if is_plural_pair:
                        if len(candidate.name) < len(current.name):
                            current.name = candidate.name
                            current.normalized_name = candidate.normalized_name

                    current.aliases = sorted(list(set(current.aliases + candidate.aliases + [candidate.name])))
                    if not current.description and candidate.description:
                        current.description = candidate.description

                    seen_mentions = {(m.chunk_id, m.start_offset, m.end_offset) for m in current.mentions}
                    for m in candidate.mentions:
                        m_key = (m.chunk_id, m.start_offset, m.end_offset)
                        if m_key not in seen_mentions:
                            seen_mentions.add(m_key)
                            current.mentions.append(m)

                    skip_indices.add(j)

            retained.append(current)

        return retained
