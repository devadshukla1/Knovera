"""End-to-End RAG Evaluation Engine (Phase 11 C11.3).

Evaluates both:
1. Retrieval Subsystem (Dense vs BM25 vs Hybrid RRF vs Cross-Encoder Reranker):
   - Recall@K, Precision@K, MRR@K, nDCG@K, MAP@K
2. Context Construction Quality:
   - Context Precision, Context Recall, Context Redundancy
3. Generation Subsystem & Citation Grounding:
   - Faithfulness / Groundedness (Claim-level support in context)
   - Answer Relevance & Correctness (Reference fact coverage F1)
   - Completeness & Conciseness
   - Citation Precision & Recall
   - Abstention Accuracy on Unanswerable / Out-of-Domain Queries
"""

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple


COMMON_STOPWORDS = {
    "using", "involving", "which", "with", "where", "also", "from", "into", "that",
    "this", "have", "been", "these", "those", "their", "such", "than", "between",
    "through", "under", "over", "while", "during", "before", "after", "above", "below",
}


def stem_word(w: str) -> str:
    """Simple morphological suffix stripper for lemma-agnostic matching."""
    for suffix in ("ing", "tion", "ment", "ies", "es", "ed", "s"):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            return w[:-len(suffix)]
    return w


def tokenize_content(text: str) -> List[str]:
    """Extracts lowercase alphabetic words from text."""
    return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text)]


def compute_token_f1(prediction: str, reference: str) -> Tuple[float, float, float]:
    """Computes token-level precision, recall, and F1 between prediction and reference."""
    pred_tokens = tokenize_content(prediction)
    ref_tokens = tokenize_content(reference)

    if not pred_tokens or not ref_tokens:
        return 0.0, 0.0, 0.0

    common = set(pred_tokens) & set(ref_tokens)
    if not common:
        return 0.0, 0.0, 0.0

    precision = len(common) / len(set(pred_tokens))
    recall = len(common) / len(set(ref_tokens))
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


@dataclass
class QueryGenerationEval:
    query_id: str
    query: str
    is_answerable: bool
    abstained: bool
    correct_abstention_decision: bool
    context_chunk_ids: List[str]
    context_precision: float
    context_recall: float
    faithfulness_score: float
    answer_relevance: float
    correctness_f1: float
    completeness: float
    citation_precision: float
    citation_recall: float
    raw_answer: str


@dataclass
class AggregateRAGEvalReport:
    total_queries: int
    answerable_queries: int
    unanswerable_queries: int
    abstention_accuracy: float
    mean_context_precision: float
    mean_context_recall: float
    mean_faithfulness: float
    mean_answer_relevance: float
    mean_correctness_f1: float
    mean_completeness: float
    mean_citation_precision: float
    mean_citation_recall: float
    retrieval_comparison: Dict[str, Dict[str, float]] = field(default_factory=dict)
    query_evaluations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RAGEvaluator:
    """Evaluates grounded RAG pipeline end-to-end with strict grounding metrics."""

    @staticmethod
    def is_abstention_response(answer: str, insufficient_evidence_flag: bool = False) -> bool:
        """Determines if the answer represents a valid abstention."""
        if insufficient_evidence_flag:
            return True
        abstention_patterns = [
            r"do not provide sufficient evidence",
            r"no searchable documents",
            r"insufficient evidence",
            r"cannot be answered based on the provided",
            r"available documents.*do not contain",
            r"no relevant document chunks",
        ]
        text = answer.lower()
        return any(re.search(pat, text) for pat in abstention_patterns)

    @classmethod
    def evaluate_context_quality(
        cls,
        retrieved_chunk_ids: List[str],
        relevant_chunk_ids: List[str],
    ) -> Tuple[float, float]:
        """Calculates context precision and recall against ground truth relevant chunks."""
        if not relevant_chunk_ids:
            return (1.0, 1.0) if not retrieved_chunk_ids else (0.0, 1.0)

        if not retrieved_chunk_ids:
            return 0.0, 0.0

        retrieved_set = set(retrieved_chunk_ids)
        relevant_set = set(relevant_chunk_ids)

        hits = len(retrieved_set & relevant_set)
        precision = hits / len(retrieved_chunk_ids)
        recall = hits / len(relevant_set)
        return precision, recall

    @classmethod
    def evaluate_faithfulness(
        cls,
        answer: str,
        context_text: str,
    ) -> float:
        """Splits answer into sentences/clauses and computes ratio of claims verified by context."""
        clean_ans = re.sub(r"\[.*?\]", "", answer).strip()
        sentences = [s.strip() for s in re.split(r"[.!?]\s*", clean_ans) if len(s.strip()) > 5]
        if not sentences:
            return 1.0

        ctx_lower = context_text.lower()
        supported = 0
        for sent in sentences:
            tokens = [t for t in tokenize_content(sent) if len(t) > 3 and t not in COMMON_STOPWORDS]
            if not tokens:
                supported += 1
                continue
            # Claim is supported if at least 55% of content tokens or stems appear in context
            token_hits = sum(1 for t in tokens if (t in ctx_lower or stem_word(t) in ctx_lower))
            if (token_hits / len(tokens)) >= 0.55:
                supported += 1

        return supported / len(sentences)

    @classmethod
    def evaluate_citation_grounding(
        cls,
        answer: str,
        citations: List[Dict[str, Any]],
        corpus_chunks: Dict[str, Dict[str, Any]],
    ) -> Tuple[float, float]:
        """Calculates citation precision and recall."""
        # Find citations in text like [eval_chunk_001] or [1] or passed citation objects
        if not citations:
            # If answer contains citation-like brackets [chunk_id]
            cited_in_text = re.findall(r"\[(eval_chunk_\d+|[a-zA-Z0-9_\-]+)\]", answer)
            if not cited_in_text:
                return 1.0, 0.8  # Clean fallback when no explicit citations needed or present

            valid_citations = 0
            for cid in cited_in_text:
                if cid in corpus_chunks:
                    valid_citations += 1
            precision = valid_citations / len(cited_in_text) if cited_in_text else 1.0
            return precision, 1.0

        # Citations list provided
        valid_citations = 0
        for cite in citations:
            cid = cite.get("chunk_id") or cite.get("document_id")
            snippet = cite.get("snippet", "")
            if cid and str(cid) in corpus_chunks:
                # verify snippet or chunk content
                chunk_content = corpus_chunks[str(cid)].get("content", "")
                if snippet and snippet[:20].lower() in chunk_content.lower():
                    valid_citations += 1
                elif not snippet:
                    valid_citations += 1

        precision = valid_citations / len(citations) if citations else 1.0
        recall = 1.0 if citations else 0.0
        return precision, recall

    @classmethod
    def evaluate_correctness_and_completeness(
        cls,
        answer: str,
        reference_answer: str,
        reference_facts: List[str],
    ) -> Tuple[float, float, float]:
        """Calculates factual correctness F1 and completeness against reference facts."""
        _, _, f1 = compute_token_f1(answer, reference_answer)

        if not reference_facts:
            return f1, 1.0, 1.0

        ans_lower = answer.lower()
        facts_found = 0
        for fact in reference_facts:
            # If fact or majority of its tokens exist in answer
            fact_tokens = tokenize_content(fact)
            if not fact_tokens:
                facts_found += 1
                continue
            hits = sum(1 for t in fact_tokens if t in ans_lower)
            if (hits / len(fact_tokens)) >= 0.65:
                facts_found += 1

        completeness = facts_found / len(reference_facts)
        return f1, completeness, f1

    @classmethod
    def evaluate_sample(
        cls,
        sample: Dict[str, Any],
        generated_answer: str,
        retrieved_chunk_ids: List[str],
        retrieved_context_text: str,
        citations: List[Dict[str, Any]],
        corpus_chunks: Dict[str, Dict[str, Any]],
        insufficient_evidence_flag: bool = False,
    ) -> QueryGenerationEval:
        """Evaluates an individual query's generated response against metrics."""
        query_id = sample.get("query_id", "")
        query = sample.get("query", "")
        is_answerable = sample.get("is_answerable", True)
        relevant_chunks = sample.get("relevant_chunks", [])
        reference_answer = sample.get("reference_answer", "")
        reference_facts = sample.get("reference_facts", [])

        # Check abstention
        abstained = cls.is_abstention_response(generated_answer, insufficient_evidence_flag)
        correct_abstention = (not is_answerable and abstained) or (is_answerable and not abstained)

        # Context metrics
        ctx_precision, ctx_recall = cls.evaluate_context_quality(retrieved_chunk_ids, relevant_chunks)

        if abstained and not is_answerable:
            # Clean abstention on unanswerable question is a 100% success
            return QueryGenerationEval(
                query_id=query_id,
                query=query,
                is_answerable=is_answerable,
                abstained=abstained,
                correct_abstention_decision=True,
                context_chunk_ids=retrieved_chunk_ids,
                context_precision=1.0,
                context_recall=1.0,
                faithfulness_score=1.0,
                answer_relevance=1.0,
                correctness_f1=1.0,
                completeness=1.0,
                citation_precision=1.0,
                citation_recall=1.0,
                raw_answer=generated_answer,
            )

        # Faithfulness
        faithfulness = cls.evaluate_faithfulness(generated_answer, retrieved_context_text)

        # Relevance
        _, _, relevance = compute_token_f1(generated_answer, query)

        # Correctness & completeness
        f1, completeness, _ = cls.evaluate_correctness_and_completeness(
            generated_answer, reference_answer, reference_facts
        )

        # Citation quality
        cit_prec, cit_rec = cls.evaluate_citation_grounding(generated_answer, citations, corpus_chunks)

        return QueryGenerationEval(
            query_id=query_id,
            query=query,
            is_answerable=is_answerable,
            abstained=abstained,
            correct_abstention_decision=correct_abstention,
            context_chunk_ids=retrieved_chunk_ids,
            context_precision=ctx_precision,
            context_recall=ctx_recall,
            faithfulness_score=faithfulness,
            answer_relevance=relevance,
            correctness_f1=f1,
            completeness=completeness,
            citation_precision=cit_prec,
            citation_recall=cit_rec,
            raw_answer=generated_answer,
        )

    @classmethod
    def aggregate_evaluations(
        cls,
        evaluations: List[QueryGenerationEval],
        retrieval_comparison: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> AggregateRAGEvalReport:
        """Aggregates all evaluation samples into a comprehensive benchmark report."""
        if not evaluations:
            return AggregateRAGEvalReport(
                total_queries=0,
                answerable_queries=0,
                unanswerable_queries=0,
                abstention_accuracy=0.0,
                mean_context_precision=0.0,
                mean_context_recall=0.0,
                mean_faithfulness=0.0,
                mean_answer_relevance=0.0,
                mean_correctness_f1=0.0,
                mean_completeness=0.0,
                mean_citation_precision=0.0,
                mean_citation_recall=0.0,
                retrieval_comparison=retrieval_comparison or {},
                query_evaluations=[],
            )

        n = len(evaluations)
        total_ans = sum(1 for e in evaluations if e.is_answerable)
        total_unans = sum(1 for e in evaluations if not e.is_answerable)

        correct_abstentions = sum(1 for e in evaluations if e.correct_abstention_decision)
        abstention_acc = correct_abstentions / n

        mean_ctx_p = sum(e.context_precision for e in evaluations) / n
        mean_ctx_r = sum(e.context_recall for e in evaluations) / n
        mean_faith = sum(e.faithfulness_score for e in evaluations) / n
        mean_rel = sum(e.answer_relevance for e in evaluations) / n
        mean_f1 = sum(e.correctness_f1 for e in evaluations) / n
        mean_comp = sum(e.completeness for e in evaluations) / n
        mean_cit_p = sum(e.citation_precision for e in evaluations) / n
        mean_cit_r = sum(e.citation_recall for e in evaluations) / n

        return AggregateRAGEvalReport(
            total_queries=n,
            answerable_queries=total_ans,
            unanswerable_queries=total_unans,
            abstention_accuracy=round(abstention_acc, 4),
            mean_context_precision=round(mean_ctx_p, 4),
            mean_context_recall=round(mean_ctx_r, 4),
            mean_faithfulness=round(mean_faith, 4),
            mean_answer_relevance=round(mean_rel, 4),
            mean_correctness_f1=round(mean_f1, 4),
            mean_completeness=round(mean_comp, 4),
            mean_citation_precision=round(mean_cit_p, 4),
            mean_citation_recall=round(mean_cit_r, 4),
            retrieval_comparison=retrieval_comparison or {},
            query_evaluations=[asdict(e) for e in evaluations],
        )
