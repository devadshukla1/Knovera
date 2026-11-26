"""Relationship Extraction Service for Knovera Knowledge Graph (Phase 7 C7.3).

Extracts typed, directional subject-predicate-object triples between normalized nodes.
Enforces strict co-occurrence rejection, exact textual evidence span verification,
negation detection, epistemic modality classification, and multi-source evidence consolidation.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.llm.manager import LLMManager
from backend.app.ml.knowledge_graph.relationships import (
    ALL_PREDICATES,
    RelationPredicate,
    get_inverse_predicate,
    is_valid_predicate,
)
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedRelationship,
    ExtractionMethod,
    Modality,
    NormalizedNode,
    RelationshipEvidenceRecord,
)
from backend.app.ml.knowledge_graph.validation import (
    detect_prompt_injection,
    locate_all_spans,
    sanitize_text_for_extraction,
    verify_span,
)

logger = logging.getLogger(__name__)

# Deterministic relational patterns: (compiled_regex, predicate, is_source_first)
# Pattern expects group("subj") and group("obj"), or matches intermediate text
RELATION_PATTERNS = [
    # Structural
    (re.compile(r"\b(?:is|are)\s+(?:an?|the)\s+(?:type|subclass|kind)\s+of\b", re.IGNORECASE), RelationPredicate.SUBCLASS_OF.value, True),
    (re.compile(r"\b(?:is|are)\s+(?:an?|the)\s+instance\s+of\b", re.IGNORECASE), RelationPredicate.INSTANCE_OF.value, True),
    (re.compile(r"\b(?:is|are)\s+part\s+of\b", re.IGNORECASE), RelationPredicate.PART_OF.value, True),
    (re.compile(r"\b(?:contains|comprises|consists\s+of|includes)\b", re.IGNORECASE), RelationPredicate.CONTAINS.value, True),
    (re.compile(r"\b(?:is|are)\s+(?:an?|the)\b", re.IGNORECASE), RelationPredicate.IS_A.value, True),

    # Functional
    (re.compile(r"\b(?:use|uses|used|utilize|utilizes|utilized|employ|employs|employed|leverage|leverages|leveraged|leveraging|adopt|adopts|adopted)\b", re.IGNORECASE), RelationPredicate.USES.value, True),
    (re.compile(r"\b(?:implement|implements|implemented)(?:\s+the)?\b", re.IGNORECASE), RelationPredicate.IMPLEMENTS.value, True),
    (re.compile(r"\b(?:is|are|was|were)\s+based\s+on\b", re.IGNORECASE), RelationPredicate.BASED_ON.value, True),
    (re.compile(r"\b(?:depend|depends|depended)\s+on|reliant\s+on\b", re.IGNORECASE), RelationPredicate.DEPENDS_ON.value, True),
    (re.compile(r"\b(?:require|requires|required|necessitate|necessitates)\b", re.IGNORECASE), RelationPredicate.REQUIRES.value, True),
    (re.compile(r"\b(?:produce|produces|produced|generate|generates|generated|yield|yields|yielded)\b", re.IGNORECASE), RelationPredicate.PRODUCES.value, True),
    (re.compile(r"\b(?:is|are|was|were)\s+applied\s+to\b", re.IGNORECASE), RelationPredicate.APPLIED_TO.value, True),
    (re.compile(r"\b(?:support|supports|supported|enable|enables|enabled)\b", re.IGNORECASE), RelationPredicate.SUPPORTS.value, True),

    # Provenance
    (re.compile(r"\b(?:was|were|is|are)?\s*(?:propose|proposes|proposed)\s+by\b", re.IGNORECASE), RelationPredicate.PROPOSED_BY.value, True),
    (re.compile(r"\b(?:was|were|is|are)?\s*(?:introduce|introduces|introduced)\s+by\b", re.IGNORECASE), RelationPredicate.INTRODUCED_BY.value, True),
    (re.compile(r"\b(?:was|were|is|are)?\s*(?:develop|develops|developed)\s+by\b", re.IGNORECASE), RelationPredicate.DEVELOPED_BY.value, True),
    (re.compile(r"\b(?:is|are|was|were)\s+evaluated\s+on\b", re.IGNORECASE), RelationPredicate.EVALUATED_ON.value, True),
    (re.compile(r"\b(?:is|are|was|were)\s+compared\s+(?:with|to|against)\b", re.IGNORECASE), RelationPredicate.COMPARED_WITH.value, True),

    # Comparative & Causality
    (re.compile(r"\b(?:improve|improves|improved|outperform|outperforms|outperformed|enhance|enhances|enhanced)\b", re.IGNORECASE), RelationPredicate.IMPROVES.value, True),
    (re.compile(r"\b(?:extend|extends|extended|builds?\s+upon|builds?\s+on)\b", re.IGNORECASE), RelationPredicate.EXTENDS.value, True),
    (re.compile(r"\b(?:cause|causes|caused|lead\s+to|leads\s+to|led\s+to|result\s+in|results\s+in)\b", re.IGNORECASE), RelationPredicate.CAUSES.value, True),
    (re.compile(r"\b(?:reduce|reduces|reduced|decrease|decreases|decreased|minimize|minimizes|minimized)\b", re.IGNORECASE), RelationPredicate.REDUCES.value, True),
    (re.compile(r"\b(?:increase|increases|increased|boost|boosts|boosted|maximize|maximizes|maximized)\b", re.IGNORECASE), RelationPredicate.INCREASES.value, True),

    # Data / Model
    (re.compile(r"\b(?:was|is|are|were)\s+trained\s+on\b", re.IGNORECASE), RelationPredicate.TRAINED_ON.value, True),
    (re.compile(r"\b(?:was|is|are|were)\s+tested\s+on\b", re.IGNORECASE), RelationPredicate.TESTED_ON.value, True),
    (re.compile(r"\b(?:predict|predicts|predicted|estimate|estimates|estimated|infer|infers|inferred)\b", re.IGNORECASE), RelationPredicate.PREDICTS.value, True),
    (re.compile(r"\b(?:output|outputs|outputted|return|returns|returned|emit|emits|emitted)\b", re.IGNORECASE), RelationPredicate.OUTPUTS.value, True),
]

NEGATION_TERMS = {"not", "never", "no", "fails to", "without", "does not", "cannot", "hardly", "unlikely"}
HYPOTHETICAL_TERMS = {"if", "would", "could", "might", "hypothesized", "proposed to", "assumed"}
UNCERTAIN_TERMS = {"possibly", "perhaps", "likely", "probably", "appears to", "seems to", "suggests that"}


class RelationshipExtractionService:
    """Service responsible for extracting verifiable typed relationships between nodes."""

    def __init__(self, llm_manager: Optional[LLMManager] = None):
        self.llm_manager = llm_manager

    def extract_relationships(
        self,
        chunks: List[Dict[str, Any]],  # [{id: str, content: str}]
        nodes: List[NormalizedNode],
        use_llm: bool = False,
    ) -> List[ExtractedRelationship]:
        """Extracts and consolidates relationships across chunks connecting recognized nodes."""
        if not chunks or not nodes or len(nodes) < 2:
            return []

        # Build alias and lookup map: normalized_form -> NormalizedNode
        name_to_node: Dict[str, NormalizedNode] = {}
        alias_to_node: Dict[str, NormalizedNode] = {}

        for node in nodes:
            name_to_node[node.name.lower()] = node
            alias_to_node[node.name.lower()] = node
            for alias in node.aliases:
                alias_to_node[alias.lower()] = node

        raw_relationships: List[ExtractedRelationship] = []

        # 1. Deterministic Extraction per chunk
        for chunk in chunks:
            chunk_id = chunk.get("id", "")
            chunk_text = sanitize_text_for_extraction(chunk.get("content", ""))
            if not chunk_text:
                continue

            rels = self._extract_deterministic_from_chunk(
                chunk_id=chunk_id,
                chunk_text=chunk_text,
                nodes=nodes,
                alias_to_node=alias_to_node,
            )
            raw_relationships.extend(rels)

        # 2. Optional LLM-assisted extraction
        if use_llm:
            for chunk in chunks:
                chunk_id = chunk.get("id", "")
                chunk_text = sanitize_text_for_extraction(chunk.get("content", ""))
                if not chunk_text or detect_prompt_injection(chunk_text):
                    continue
                try:
                    llm_rels = self._extract_llm_from_chunk(
                        chunk_id=chunk_id,
                        chunk_text=chunk_text,
                        nodes=nodes,
                        alias_to_node=alias_to_node,
                    )
                    raw_relationships.extend(llm_rels)
                except Exception as e:
                    logger.warning("LLM relationship extraction skipped for chunk %s: %s", chunk_id, e)

        # 3. Consolidate and deduplicate relationships across all chunks
        consolidated = self._consolidate_relationships(raw_relationships, name_to_node)

        return consolidated

    def _extract_deterministic_from_chunk(
        self,
        chunk_id: str,
        chunk_text: str,
        nodes: List[NormalizedNode],
        alias_to_node: Dict[str, NormalizedNode],
    ) -> List[ExtractedRelationship]:
        """Extracts relationships deterministically from sentences in a single chunk."""
        # Split into sentences while tracking sentence start offsets
        sentence_spans = self._split_sentences_with_offsets(chunk_text)
        chunk_rels: List[ExtractedRelationship] = []

        for sent_text, sent_start, sent_end in sentence_spans:
            # Find which nodes are mentioned in this sentence
            mentioned_nodes_in_sent: List[Tuple[NormalizedNode, int, int, str]] = []

            for alias_str, node in alias_to_node.items():
                if len(alias_str) < 2:
                    continue
                spans = locate_all_spans(sent_text, alias_str, whole_word=True)
                for s, e in spans:
                    surface_matched = sent_text[s:e]
                    mentioned_nodes_in_sent.append((node, s, e, surface_matched))

            # Deduplicate multiple mentions of same node in sentence, keep sorted by start
            # If two mentions overlap (e.g. "BERT" and "BERT model"), keep longer
            clean_mentions = self._filter_overlapping_mentions(mentioned_nodes_in_sent)

            # Need at least two distinct nodes to form a relationship
            distinct_nodes = {m[0].name for m in clean_mentions}
            if len(distinct_nodes) < 2:
                # Reject co-occurrence when less than 2 distinct nodes
                continue

            # Compare adjacent and near pairs in the sentence
            for i in range(len(clean_mentions)):
                node_a, a_start, a_end, a_surf = clean_mentions[i]
                for j in range(len(clean_mentions)):
                    if i == j:
                        continue
                    node_b, b_start, b_end, b_surf = clean_mentions[j]

                    if node_a.name == node_b.name:
                        # Reject self-loop
                        continue

                    # Only check forward directed span between a and b
                    if a_end < b_start:
                        inter_text = sent_text[a_end:b_start].strip()

                        # Scan for explicit relation predicate in connecting text
                        matched_pred = None
                        for pat, pred, is_src_first in RELATION_PATTERNS:
                            m = pat.search(inter_text)
                            if m:
                                matched_pred = pred
                                break

                        if matched_pred:
                            # Verify explicit syntactic connection: inter_text must not contain full sentence boundary
                            is_negated = any(neg in inter_text.lower() for neg in NEGATION_TERMS)
                            modality = Modality.CERTAIN.value
                            if any(hyp in sent_text.lower() for hyp in HYPOTHETICAL_TERMS):
                                modality = Modality.HYPOTHETICAL.value
                            elif any(unc in sent_text.lower() for unc in UNCERTAIN_TERMS):
                                modality = Modality.UNCERTAIN.value

                            # Exact evidence span is the containing sentence or minimal spanning slice
                            ev_start = sent_start
                            ev_end = sent_end
                            ev_text = chunk_text[ev_start:ev_end]

                            evidence_rec = RelationshipEvidenceRecord(
                                chunk_id=chunk_id,
                                evidence_text=ev_text,
                                start_offset=ev_start,
                                end_offset=ev_end,
                                confidence=0.92,
                            )

                            rel = ExtractedRelationship(
                                source_node_name=node_a.name,
                                target_node_name=node_b.name,
                                source_node_id=node_a.id,
                                target_node_id=node_b.id,
                                predicate=matched_pred,
                                inverse_predicate=get_inverse_predicate(matched_pred),
                                is_negated=is_negated,
                                modality=modality,
                                evidence=[evidence_rec],
                                confidence=0.90,
                                extraction_method=ExtractionMethod.DETERMINISTIC.value,
                            )
                            chunk_rels.append(rel)

        return chunk_rels

    def _extract_llm_from_chunk(
        self,
        chunk_id: str,
        chunk_text: str,
        nodes: List[NormalizedNode],
        alias_to_node: Dict[str, NormalizedNode],
    ) -> List[ExtractedRelationship]:
        """Extracts relationships using LLM assistance and strict evidence verification."""
        manager = self.llm_manager or LLMManager.get_instance()
        if not manager:
            return []

        node_names = [n.name for n in nodes[:50]]
        prompt = (
            "You are an academic knowledge extraction specialist.\n"
            "Given the following text and recognized entities, extract explicit factual relationships between them.\n"
            "CRITICAL: Do NOT infer relationships from mere co-occurrence. Every relation MUST be explicitly asserted.\n"
            "Every relation MUST include an exact verbatim 'evidence_quote' from the text.\n"
            "Allowed predicates: " + ", ".join(sorted(list(ALL_PREDICATES))) + "\n"
            "Recognized entities: " + ", ".join(node_names) + "\n\n"
            "Output ONLY a valid JSON array adhering to this schema:\n"
            "[\n"
            "  {\n"
            '    "source": "exact entity name from list",\n'
            '    "target": "exact entity name from list",\n'
            '    "predicate": "one of allowed predicates",\n'
            '    "is_negated": false,\n'
            '    "modality": "certain | hypothetical | uncertain",\n'
            '    "evidence_quote": "exact verbatim substring from text"\n'
            "  }\n"
            "]\n\n"
            f"TEXT:\n\"\"\"{chunk_text[:2000]}\"\"\"\n"
        )

        response = manager.complete(prompt=prompt, temperature=0.0, max_tokens=600)
        if not response or not response.strip():
            return []

        json_str = response.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        data = json.loads(json_str)
        if not isinstance(data, list):
            return []

        results: List[ExtractedRelationship] = []
        for item in data:
            src = item.get("source", "").strip()
            tgt = item.get("target", "").strip()
            pred = item.get("predicate", "").strip().lower()
            ev_quote = item.get("evidence_quote", "").strip()
            is_negated = bool(item.get("is_negated", False))
            modality = item.get("modality", Modality.CERTAIN.value)

            if not src or not tgt or src.lower() == tgt.lower() or not is_valid_predicate(pred):
                continue

            node_a = alias_to_node.get(src.lower())
            node_b = alias_to_node.get(tgt.lower())
            if not node_a or not node_b:
                continue

            # Verify evidence quote against chunk text
            spans = locate_all_spans(chunk_text, ev_quote, whole_word=False)
            if not spans:
                continue

            start_off, end_off = spans[0]
            evidence_rec = RelationshipEvidenceRecord(
                chunk_id=chunk_id,
                evidence_text=chunk_text[start_off:end_off],
                start_offset=start_off,
                end_offset=end_off,
                confidence=0.88,
            )

            rel = ExtractedRelationship(
                source_node_name=node_a.name,
                target_node_name=node_b.name,
                source_node_id=node_a.id,
                target_node_id=node_b.id,
                predicate=pred,
                inverse_predicate=get_inverse_predicate(pred),
                is_negated=is_negated,
                modality=modality if modality in {"certain", "hypothetical", "uncertain"} else Modality.CERTAIN.value,
                evidence=[evidence_rec],
                confidence=0.85,
                extraction_method=ExtractionMethod.LLM.value,
            )
            results.append(rel)

        return results

    def _consolidate_relationships(
        self,
        raw_relationships: List[ExtractedRelationship],
        name_to_node: Dict[str, NormalizedNode],
    ) -> List[ExtractedRelationship]:
        """Consolidates identical (source, predicate, target, is_negated) triples and aggregates evidence."""
        consolidated_map: Dict[Tuple[str, str, str, bool], ExtractedRelationship] = {}

        for rel in raw_relationships:
            src_norm = rel.source_node_name.strip()
            tgt_norm = rel.target_node_name.strip()
            key = (src_norm.lower(), rel.predicate.lower(), tgt_norm.lower(), rel.is_negated)

            if key in consolidated_map:
                existing = consolidated_map[key]
                # Aggregate evidence spans without duplicates
                seen_evidence = {(e.chunk_id, e.start_offset, e.end_offset) for e in existing.evidence}
                for ev in rel.evidence:
                    ev_key = (ev.chunk_id, ev.start_offset, ev.end_offset)
                    if ev_key not in seen_evidence:
                        seen_evidence.add(ev_key)
                        existing.evidence.append(ev)
                # Boost confidence slightly if multiple independent sources
                existing.confidence = min(1.0, existing.confidence + 0.05)
            else:
                # Ensure IDs are mapped if available
                node_a = name_to_node.get(src_norm.lower())
                node_b = name_to_node.get(tgt_norm.lower())
                if node_a and node_a.id:
                    rel.source_node_id = node_a.id
                if node_b and node_b.id:
                    rel.target_node_id = node_b.id

                consolidated_map[key] = rel

        return list(consolidated_map.values())

    def _split_sentences_with_offsets(self, text: str) -> List[Tuple[str, int, int]]:
        """Splits text into sentences along with their start and end character offsets."""
        sentences: List[Tuple[str, int, int]] = []
        if not text:
            return sentences

        # Regex pattern matching sentence terminators followed by whitespace or end of string
        pattern = re.compile(r"([^.!?\n]+(?:[.!?]+|\n+|$))")
        for match in pattern.finditer(text):
            sent = match.group(0)
            if sent and sent.strip():
                # Trim leading/trailing spaces while adjusting offsets
                strip_start = match.start() + (len(sent) - len(sent.lstrip()))
                strip_end = match.end() - (len(sent) - len(sent.rstrip()))
                if strip_start < strip_end:
                    sentences.append((text[strip_start:strip_end], strip_start, strip_end))

        return sentences

    def _filter_overlapping_mentions(
        self,
        mentions: List[Tuple[NormalizedNode, int, int, str]],
    ) -> List[Tuple[NormalizedNode, int, int, str]]:
        """Removes overlapping mentions, keeping the longer span."""
        if not mentions:
            return []

        # Sort by start offset ascending, length descending
        sorted_m = sorted(mentions, key=lambda m: (m[1], -(m[2] - m[1])))
        filtered: List[Tuple[NormalizedNode, int, int, str]] = []

        for m in sorted_m:
            node, s, e, surf = m
            # Check overlap with last added
            if not filtered:
                filtered.append(m)
                continue

            last_node, last_s, last_e, last_surf = filtered[-1]
            if s < last_e:
                # Overlaps! Keep the longer one (which is last_m since sorted by length desc)
                if (e - s) > (last_e - last_s):
                    filtered[-1] = m
            else:
                filtered.append(m)

        return filtered
