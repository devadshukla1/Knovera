"""Concept Extraction Service for Knovera Knowledge Graph (Phase 7 C7.1).

Extracts academic concepts, technical terms, algorithms, models, datasets,
and metrics from document chunks using high-precision deterministic rules
and optional LLM assistance, with exact Unicode character offsets.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.llm.manager import LLMManager
from backend.app.ml.knowledge_graph.ontology import (
    ConceptType,
    EntityType,
    infer_node_type,
    is_valid_category,
)
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedConcept,
    ExtractedMention,
    ExtractionMethod,
)
from backend.app.ml.knowledge_graph.validation import (
    detect_prompt_injection,
    locate_all_spans,
    sanitize_text_for_extraction,
    verify_span,
)

logger = logging.getLogger(__name__)

# Common non-technical stopwords / generic nouns to reject when appearing alone
GENERIC_STOPWORDS: Set[str] = {
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "they", "their",
    "system", "systems", "approach", "approaches", "method", "methods", "model", "models",
    "paper", "study", "analysis", "data", "information", "result", "results", "work",
    "process", "process", "technique", "techniques", "algorithm", "algorithms",
    "figure", "table", "section", "chapter", "example", "case", "problem", "solution",
    "concept", "concepts", "entity", "entities", "feature", "features", "value", "values",
    "user", "users", "document", "documents", "chunk", "chunks", "text", "query", "queries",
}

# Domain vocabulary seed patterns: (regex pattern, category, default_node_type)
DOMAIN_PATTERNS = [
    # Metrics
    (r"\b(Recall@[0-9]+|MRR@[0-9]+|MRR|nDCG@[0-9]+|nDCG|NDCG|F1[- ]score|Precision|Recall|Accuracy|Perplexity|BLEU|ROUGE|Silhouette\s+Score|Davies[- ]Bouldin)\b", ConceptType.METRIC.value),
    # Common ML / IR Algorithms & Methods
    (r"\b(BM25|BM25\+?|TF[- ]IDF|Reciprocal\s+Rank\s+Fusion|RRF|K[- ]Means(?:\s+Clustering)?|Cosine\s+Similarity|Gradient\s+Descent|Backpropagation|Stochastic\s+Gradient\s+Descent|SGD|Adam\s+Optimizer|Support\s+Vector\s+Machine|SVM|Logistic\s+Regression|Random\s+Forest|Decision\s+Tree|PageRank|Dijkstra(?:'s)?\s+Algorithm)\b", ConceptType.ALGORITHM.value),
    # Architectures & Models
    (r"\b(Transformer|BERT|RoBERTa|GPT[- ]?[0-9a-zA-Z\.]+|LLaMA|Mistral|ResNet|LSTM|RNN|CNN|Cross[- ]Encoder|Bi[- ]Encoder|Dense\s+Retriever|Autoencoder)\b", EntityType.MODEL.value),
    # Datasets
    (r"\b(ImageNet|SQuAD|GLUE|SuperGLUE|MS\s+MARCO|MNIST|CIFAR[- ]10|CIFAR[- ]100|CoNLL[- ]2003|HotpotQA|BEIR)\b", EntityType.DATASET.value),
    # Programming Languages & Technologies
    (r"\b(Python|C\+\+|C\#|JavaScript|TypeScript|Rust|Go|Java|SQL|Node\.js|\.NET|PostgreSQL|ChromaDB|Docker|Kubernetes|PyTorch|TensorFlow|FastAPI|React)\b", EntityType.TECHNOLOGY.value),
    # Core Technical Concepts
    (r"\b((?:Vector|Dense|Neural)\s+Embeddings?|Self[- ]Attention|Multi[- ]Head\s+Attention|Latent\s+Space|Hyperparameters?|Overfitting|Underfitting|Zero[- ]shot|Few[- ]shot|Prompt\s+Engineering|Cross[- ]Entropy|Knowledge\s+Graph|Ontology|Semantic\s+Search|Lexical\s+Search|Hybrid\s+Retrieval)\b", ConceptType.TECHNICAL_CONCEPT.value),
]

# Definition extraction patterns
DEFINITION_PATTERNS = [
    re.compile(r"(?P<term>[A-Z][A-Za-z0-9_\-\+ ]{2,40})\s+(?:is|are)\s+defined\s+as\s+(?P<desc>[^.\n]{10,250})", re.IGNORECASE),
    re.compile(r"(?P<term>[A-Z][A-Za-z0-9_\-\+ ]{2,40})\s+refers\s+to\s+(?P<desc>[^.\n]{10,250})", re.IGNORECASE),
    re.compile(r"(?P<term>[A-Z][A-Za-z0-9_\-\+ ]{2,40})\s+is\s+(?:an?|the)\s+(?P<desc>(?:technique|algorithm|model|method|process|metric|framework|system)[^.\n]{10,250})", re.IGNORECASE),
]

# Acronym patterns e.g. "Natural Language Processing (NLP)"
ACRONYM_EXPANSION_PATTERN = re.compile(
    r"\b(?P<full>[A-Z][A-Za-z0-9\-]+(?:\s+[A-Z][A-Za-z0-9\-]+){1,5})\s+\((?P<abbr>[A-Z0-9]{2,8})\)"
)


class ConceptExtractionService:
    """Service responsible for extracting concepts, entities, and verified mentions."""

    def __init__(self, llm_manager: Optional[LLMManager] = None):
        self.llm_manager = llm_manager

    def extract_from_chunk(
        self,
        chunk_text: str,
        chunk_id: Optional[str] = None,
        use_llm: bool = False,
    ) -> List[ExtractedConcept]:
        """Extracts concept and entity candidates from a single chunk with verified mentions.

        If use_llm is True and LLMManager is available, LLM-based extraction is executed
        and merged with deterministic extraction. Otherwise deterministic extraction runs.
        """
        clean_text = sanitize_text_for_extraction(chunk_text)
        if not clean_text or len(clean_text.strip()) < 5:
            return []

        # 1. Deterministic extraction
        candidates = self._extract_deterministic(clean_text, chunk_id=chunk_id)

        # 2. Optional LLM extraction if requested and safe
        if use_llm and not detect_prompt_injection(clean_text):
            try:
                llm_candidates = self._extract_llm(clean_text, chunk_id=chunk_id)
                candidates = self._merge_candidates(candidates, llm_candidates, clean_text)
            except Exception as e:
                logger.warning("LLM concept extraction failed or unavailable, using deterministic: %s", e)

        # 3. Final verification of offsets against chunk text
        verified_concepts = []
        for cand in candidates:
            valid_mentions = [
                m for m in cand.mentions
                if verify_span(clean_text, m.start_offset, m.end_offset, m.surface_form, case_sensitive=False)
            ]
            if valid_mentions:
                cand.mentions = valid_mentions
                verified_concepts.append(cand)

        return verified_concepts

    def _extract_deterministic(
        self,
        text: str,
        chunk_id: Optional[str] = None,
    ) -> List[ExtractedConcept]:
        """High-precision regex and rule-based candidate concept extraction."""
        candidate_map: Dict[str, ExtractedConcept] = {}

        # A. Acronym expansions: "Natural Language Processing (NLP)"
        for match in ACRONYM_EXPANSION_PATTERN.finditer(text):
            full_name = match.group("full").strip()
            abbr = match.group("abbr").strip()

            if full_name.lower() in GENERIC_STOPWORDS:
                continue

            # Record full name
            full_spans = locate_all_spans(text, full_name, whole_word=True)
            abbr_spans = locate_all_spans(text, abbr, whole_word=True)

            mentions = [
                ExtractedMention(
                    surface_form=text[s:e],
                    start_offset=s,
                    end_offset=e,
                    chunk_id=chunk_id,
                    confidence=0.98,
                    extraction_method=ExtractionMethod.DETERMINISTIC.value,
                )
                for s, e in full_spans + abbr_spans
            ]

            cand = ExtractedConcept(
                name=full_name,
                normalized_name=full_name.lower(),
                category=ConceptType.TECHNICAL_CONCEPT.value,
                node_type=infer_node_type(ConceptType.TECHNICAL_CONCEPT.value).value,
                description=f"Also known as {abbr}",
                aliases=[abbr],
                mentions=mentions,
                confidence=0.95,
                extraction_method=ExtractionMethod.DETERMINISTIC.value,
            )
            candidate_map[full_name.lower()] = cand

        # B. Domain patterns
        for pattern_str, category in DOMAIN_PATTERNS:
            for match in re.finditer(pattern_str, text, flags=re.IGNORECASE):
                matched_surface = match.group(0).strip()
                norm_key = matched_surface.lower()

                if norm_key in GENERIC_STOPWORDS or len(norm_key) < 2:
                    continue

                spans = locate_all_spans(text, matched_surface, whole_word=True)
                mentions = [
                    ExtractedMention(
                        surface_form=text[s:e],
                        start_offset=s,
                        end_offset=e,
                        chunk_id=chunk_id,
                        confidence=0.95,
                        extraction_method=ExtractionMethod.DETERMINISTIC.value,
                    )
                    for s, e in spans
                ]

                if norm_key in candidate_map:
                    # Update category if more specific
                    existing = candidate_map[norm_key]
                    existing_mentions_set = {(m.start_offset, m.end_offset) for m in existing.mentions}
                    for m in mentions:
                        if (m.start_offset, m.end_offset) not in existing_mentions_set:
                            existing.mentions.append(m)
                else:
                    node_type = infer_node_type(category).value
                    candidate_map[norm_key] = ExtractedConcept(
                        name=matched_surface,
                        normalized_name=norm_key,
                        category=category,
                        node_type=node_type,
                        mentions=mentions,
                        confidence=0.90,
                        extraction_method=ExtractionMethod.DETERMINISTIC.value,
                    )

        # C. Definition patterns
        for def_pat in DEFINITION_PATTERNS:
            for match in def_pat.finditer(text):
                term = match.group("term").strip()
                desc = match.group("desc").strip()
                norm_key = term.lower()

                if norm_key in GENERIC_STOPWORDS or len(term) < 3:
                    continue

                spans = locate_all_spans(text, term, whole_word=True)
                mentions = [
                    ExtractedMention(
                        surface_form=text[s:e],
                        start_offset=s,
                        end_offset=e,
                        chunk_id=chunk_id,
                        confidence=0.95,
                        extraction_method=ExtractionMethod.DETERMINISTIC.value,
                    )
                    for s, e in spans
                ]

                if norm_key in candidate_map:
                    if not candidate_map[norm_key].description:
                        candidate_map[norm_key].description = desc
                else:
                    candidate_map[norm_key] = ExtractedConcept(
                        name=term,
                        normalized_name=norm_key,
                        category=ConceptType.TECHNICAL_CONCEPT.value,
                        node_type=infer_node_type(ConceptType.TECHNICAL_CONCEPT.value).value,
                        description=desc,
                        mentions=mentions,
                        confidence=0.92,
                        extraction_method=ExtractionMethod.DETERMINISTIC.value,
                    )

        return list(candidate_map.values())

    def _extract_llm(
        self,
        text: str,
        chunk_id: Optional[str] = None,
    ) -> List[ExtractedConcept]:
        """Extracts candidate entities and concepts using LLM assistance if configured."""
        manager = self.llm_manager or LLMManager.get_instance()
        if not manager:
            return []

        prompt = (
            "You are an academic knowledge extraction specialist for the Knovera system.\n"
            "Extract key technical concepts, algorithms, methods, models, datasets, and metrics "
            "from the following academic text.\n"
            "Respond ONLY with a valid JSON array of objects adhering strictly to this schema:\n"
            "[\n"
            "  {\n"
            '    "name": "exact surface term as appeared in text",\n'
            '    "category": "one of [theory, method, algorithm, process, technical_concept, research_topic, metric, model, dataset, technology, software, programming_language, organization, person]",\n'
            '    "description": "brief 1-sentence definition based on text (or null)",\n'
            '    "aliases": ["optional list of synonyms or abbreviations"]\n'
            "  }\n"
            "]\n\n"
            f"TEXT TO EXTRACT:\n\"\"\"{text[:2000]}\"\"\"\n"
        )

        response = manager.complete(
            prompt=prompt,
            temperature=0.0,
            max_tokens=600,
        )

        if not response or not response.strip():
            return []

        # Parse JSON output safely
        json_str = response.strip()
        # Handle markdown fence if returned
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        data = json.loads(json_str)
        if not isinstance(data, list):
            return []

        results: List[ExtractedConcept] = []
        for item in data:
            name = item.get("name", "").strip()
            category = item.get("category", "").strip().lower()
            if not name or name.lower() in GENERIC_STOPWORDS or len(name) < 2:
                continue
            if not is_valid_category(category):
                category = ConceptType.TECHNICAL_CONCEPT.value

            spans = locate_all_spans(text, name, whole_word=True)
            if not spans:
                continue

            mentions = [
                ExtractedMention(
                    surface_form=text[s:e],
                    start_offset=s,
                    end_offset=e,
                    chunk_id=chunk_id,
                    confidence=0.88,
                    extraction_method=ExtractionMethod.LLM.value,
                )
                for s, e in spans
            ]

            aliases = item.get("aliases") or []
            desc = item.get("description")

            results.append(
                ExtractedConcept(
                    name=name,
                    normalized_name=name.lower(),
                    category=category,
                    node_type=infer_node_type(category).value,
                    description=desc,
                    aliases=aliases,
                    mentions=mentions,
                    confidence=0.88,
                    extraction_method=ExtractionMethod.LLM.value,
                )
            )

        return results

    def _merge_candidates(
        self,
        deterministic: List[ExtractedConcept],
        llm_based: List[ExtractedConcept],
        chunk_text: str,
    ) -> List[ExtractedConcept]:
        """Merges deterministic and LLM-extracted candidates without duplication."""
        merged: Dict[str, ExtractedConcept] = {c.normalized_name: c for c in deterministic}

        for llm_c in llm_based:
            key = llm_c.normalized_name
            if key in merged:
                target = merged[key]
                if not target.description and llm_c.description:
                    target.description = llm_c.description
                # Combine aliases
                target.aliases = list(set(target.aliases + llm_c.aliases))
                # Add any missing mentions
                existing_spans = {(m.start_offset, m.end_offset) for m in target.mentions}
                for m in llm_c.mentions:
                    if (m.start_offset, m.end_offset) not in existing_spans:
                        target.mentions.append(m)
            else:
                merged[key] = llm_c

        return list(merged.values())
