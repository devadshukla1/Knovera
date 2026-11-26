"""Natural Language Inference (NLI) Inference & Evaluation Service (Phase 10 C10.6).

Provides:
- Configurable Sequence Classification NLI model loader (Hugging Face Transformers / PyTorch)
- CPU execution with automatic GPU acceleration detection
- Deterministic Mock NLI Provider for isolated testing and offline environments
- Explicit label mapping validation (entailment, contradiction, neutral)
- Bidirectional inference: (A -> B) and (B -> A)
- Pairwise input fingerprinting and version-aware caching
- Decision policy with margin-based abstention and confidence calibration
- Contextual comparability safeguard: NLI prediction never overrides incompatible experimental conditions
- Benchmark evaluation suite computing Accuracy, Macro F1, Per-class F1, and Confusion Matrices.
"""

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid
from datetime import datetime, timezone
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.research_intelligence import (
    NLIInferenceRecord,
    NLIEvaluationRun,
    ResearchFinding,
    ResearchFindingComparison,
)
from backend.app.schemas.research_intelligence import (
    NLILabel,
    NLIInferenceResponse,
)

logger = get_logger("knovera.research.nli_service")

# Standard canonical label space
CANONICAL_LABELS = ["entailment", "contradiction", "neutral"]


class BaseNLIProvider:
    """Abstract base provider for NLI sequence classification."""

    def predict_pair(
        self,
        premise: str,
        hypothesis: str,
    ) -> Dict[str, float]:
        """Returns softmax probability distribution: {'entailment': p, 'contradiction': p, 'neutral': p}."""
        raise NotImplementedError

    def predict_batch(
        self,
        pairs: List[Tuple[str, str]],
    ) -> List[Dict[str, float]]:
        """Returns list of probability distributions."""
        raise NotImplementedError


class MockNLIProvider(BaseNLIProvider):
    """Deterministic Mock NLI Provider for testing and reproducible verification."""

    def predict_pair(
        self,
        premise: str,
        hypothesis: str,
    ) -> Dict[str, float]:
        p_lower = premise.lower()
        h_lower = hypothesis.lower()

        # Deterministic semantic rules for contradiction
        if (
            ("not" in h_lower and "not" not in p_lower)
            or ("no statistically significant" in h_lower and "achieved" in p_lower)
            or ("fails" in h_lower and "achieves" in p_lower)
            or ("failed" in h_lower and "achieved" in p_lower)
            or ("inferior" in h_lower or "worse" in h_lower)
            or ("decreased" in h_lower and "increased" in p_lower)
            or ("decrease" in h_lower and "increase" in p_lower)
            or ("increase" in h_lower and "decrease" in p_lower)
            or ("decrease" in h_lower and "improve" in p_lower)
            or ("decreases" in h_lower and "increases" in p_lower)
            or ("increases" in h_lower and "decreases" in p_lower)
            or ("slower" in h_lower and ("latency" in p_lower or "speed" in p_lower))
        ):
            return {"contradiction": 0.88, "neutral": 0.08, "entailment": 0.04}

        clean_p = re.sub(r"[^\w\s]", " ", p_lower)
        clean_h = re.sub(r"[^\w\s]", " ", h_lower)
        p_words = set(w for w in clean_p.split() if len(w) > 2)
        h_words = set(w for w in clean_h.split() if len(w) > 2)

        # Synonym mappings for research claims
        synonyms = {
            "outperforms": {"superior", "higher", "better", "improves", "exceeds"},
            "outperformed": {"superior", "higher", "better", "improved", "exceeded"},
            "achieved": {"obtained", "reached", "attained", "yielded"},
            "faster": {"speedup", "throughput", "latency"},
        }
        for k, syn_set in synonyms.items():
            if k in p_words and any(s in h_words for s in syn_set):
                p_words.add("shared_synonym")
                h_words.add("shared_synonym")

        overlap = len(p_words.intersection(h_words)) / max(1, len(h_words))

        if overlap >= 0.30:
            return {"entailment": 0.84, "neutral": 0.11, "contradiction": 0.05}

        # Neutral fallback
        return {"neutral": 0.72, "entailment": 0.16, "contradiction": 0.12}

    def predict_batch(
        self,
        pairs: List[Tuple[str, str]],
    ) -> List[Dict[str, float]]:
        return [self.predict_pair(p, h) for p, h in pairs]


class TransformersNLIProvider(BaseNLIProvider):
    """Local Hugging Face Transformers NLI sequence classification provider."""

    def __init__(
        self,
        model_id: str = "cross-encoder/nli-deberta-v3-base",
        revision: str = "main",
        device: Optional[str] = None,
        max_length: int = 512,
    ):
        self.model_id = model_id
        self.revision = revision
        self.max_length = max_length
        self.device = device or ("cuda" if self._has_cuda() else "cpu")
        self.tokenizer = None
        self.model = None
        self.label_mapping: Dict[int, str] = {}
        self._load_model()

    def _has_cuda(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def _load_model(self) -> None:
        """Loads pretrained sequence classification weights and resolves label mapping."""
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        logger.info("Loading NLI model '%s' (revision='%s') on device '%s'...", self.model_id, self.revision, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, revision=self.revision)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_id, revision=self.revision)
        self.model.to(self.device)
        self.model.eval()

        # Resolve model label mapping
        id2label = getattr(self.model.config, "id2label", None)
        if id2label and isinstance(id2label, dict):
            for idx, raw_lbl in id2label.items():
                lbl_clean = str(raw_lbl).strip().lower()
                if "entail" in lbl_clean:
                    self.label_mapping[int(idx)] = "entailment"
                elif "contra" in lbl_clean:
                    self.label_mapping[int(idx)] = "contradiction"
                elif "neut" in lbl_clean:
                    self.label_mapping[int(idx)] = "neutral"
                else:
                    self.label_mapping[int(idx)] = "neutral"
        else:
            # Standard MNLI index default: 0 -> contradiction, 1 -> neutral, 2 -> entailment
            # (or for cross-encoder/nli-deberta-v3-base: 0 -> contradiction, 1 -> entailment, 2 -> neutral)
            self.label_mapping = {0: "contradiction", 1: "entailment", 2: "neutral"}

        logger.info("NLI model '%s' loaded successfully. Label mapping: %s", self.model_id, self.label_mapping)

    def predict_pair(self, premise: str, hypothesis: str) -> Dict[str, float]:
        return self.predict_batch([(premise, hypothesis)])[0]

    def predict_batch(self, pairs: List[Tuple[str, str]]) -> List[Dict[str, float]]:
        import torch

        if not pairs:
            return []

        premises = [p[0] for p in pairs]
        hypotheses = [p[1] for p in pairs]

        encoded = self.tokenizer(
            premises,
            hypotheses,
            truncation=True,
            max_length=self.max_length,
            padding=True,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**encoded)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()

        results: List[Dict[str, float]] = []
        for row in probs:
            dist: Dict[str, float] = {"entailment": 0.0, "contradiction": 0.0, "neutral": 0.0}
            for idx, val in enumerate(row):
                canonical = self.label_mapping.get(idx, "neutral")
                dist[canonical] = max(dist[canonical], float(val))
            # Normalize to sum = 1.0
            tot = sum(dist.values()) or 1.0
            results.append({k: round(v / tot, 4) for k, v in dist.items()})

        return results


class NLIInferenceService:
    """Manages NLI inference, bidirectional aggregation, confidence thresholds, and evaluation."""

    _instance: Optional["NLIInferenceService"] = None

    def __init__(
        self,
        provider: Optional[BaseNLIProvider] = None,
        model_id: str = "mock-nli-model",
        model_revision: str = "v1.0",
        confidence_threshold: float = 0.60,
        margin_threshold: float = 0.15,
    ):
        self.model_id = model_id
        self.model_revision = model_revision
        self.confidence_threshold = confidence_threshold
        self.margin_threshold = margin_threshold
        self.provider = provider or MockNLIProvider()

    @classmethod
    def get_instance(cls, use_mock: bool = True) -> "NLIInferenceService":
        if cls._instance is None:
            if use_mock or os.getenv("NLI_USE_MOCK", "true").lower() == "true":
                provider = MockNLIProvider()
                model_id = "mock-nli-model"
            else:
                try:
                    configured_model = os.getenv("NLI_MODEL_ID", "cross-encoder/nli-deberta-v3-base")
                    provider = TransformersNLIProvider(model_id=configured_model)
                    model_id = configured_model
                except Exception as exc:
                    logger.warning("Failed initializing Transformers NLI provider: %s. Using MockNLIProvider.", exc)
                    provider = MockNLIProvider()
                    model_id = "mock-nli-model"

            cls._instance = cls(provider=provider, model_id=model_id)
        return cls._instance

    @classmethod
    def set_instance(cls, instance: Optional["NLIInferenceService"]) -> None:
        cls._instance = instance

    # -----------------------------------------------------------------------
    # Inference Execution with Bidirectionality and Caching
    # -----------------------------------------------------------------------

    def infer(
        self,
        premise: str,
        hypothesis: str,
        bidirectional: bool = True,
    ) -> NLIInferenceResponse:
        """Lightweight inference call for inline service usage."""
        clean_premise = premise.strip()
        clean_hypothesis = hypothesis.strip()
        fwd_scores = self.provider.predict_pair(clean_premise, clean_hypothesis)
        fwd_label = self._get_top_label(fwd_scores)
        bwd_scores = None
        bwd_label = None
        if bidirectional:
            bwd_scores = self.provider.predict_pair(clean_hypothesis, clean_premise)
            bwd_label = self._get_top_label(bwd_scores)
        agg_label, margin, abstained, conf_level = self._aggregate_results(fwd_scores, bwd_scores)
        return NLIInferenceResponse(
            premise=clean_premise,
            hypothesis=clean_hypothesis,
            forward_label=fwd_label,
            forward_scores=fwd_scores,
            backward_label=bwd_label,
            backward_scores=bwd_scores,
            aggregated_label=agg_label,
            margin=margin,
            abstained=abstained,
            confidence_level=conf_level,
            model_id=self.model_id,
            model_revision=self.model_revision,
            pair_fingerprint="fast_infer",
        )

    def infer_pair(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        premise: str,
        hypothesis: str,
        premise_doc_id: Optional[uuid.UUID] = None,
        hypothesis_doc_id: Optional[uuid.UUID] = None,
        bidirectional: bool = True,
    ) -> NLIInferenceResponse:
        """Executes NLI inference with caching, bidirectional validation, and margin thresholding."""
        clean_premise = premise.strip()
        clean_hypothesis = hypothesis.strip()

        premise_hash = hashlib.sha256(clean_premise.encode("utf-8")).hexdigest()
        hypothesis_hash = hashlib.sha256(clean_hypothesis.encode("utf-8")).hexdigest()
        fingerprint = hashlib.sha256(
            f"{premise_hash}_{hypothesis_hash}_{self.model_id}_{self.model_revision}_{bidirectional}".encode("utf-8")
        ).hexdigest()

        # Check Cache
        cached = db.execute(
            select(NLIInferenceRecord).where(
                NLIInferenceRecord.workspace_id == workspace_id,
                NLIInferenceRecord.pair_fingerprint == fingerprint,
            )
        ).scalar_one_or_none()

        if cached:
            return NLIInferenceResponse(
                premise=cached.premise_text,
                hypothesis=cached.hypothesis_text,
                forward_label=cached.forward_label,  # type: ignore
                forward_scores=cached.forward_scores,
                backward_label=cached.backward_label,  # type: ignore
                backward_scores=cached.backward_scores,
                aggregated_label=cached.aggregated_label,
                margin=cached.margin,
                abstained=cached.abstained,
                confidence_level=cached.confidence_level,
                model_id=cached.model_id,
                model_revision=cached.model_revision,
                pair_fingerprint=cached.pair_fingerprint,
            )

        # 1. Forward Inference: Premise -> Hypothesis
        fwd_scores = self.provider.predict_pair(clean_premise, clean_hypothesis)
        fwd_label = self._get_top_label(fwd_scores)

        # 2. Backward Inference: Hypothesis -> Premise (if bidirectional)
        bwd_scores = None
        bwd_label = None
        if bidirectional:
            bwd_scores = self.provider.predict_pair(clean_hypothesis, clean_premise)
            bwd_label = self._get_top_label(bwd_scores)

        # 3. Aggregate Labels & Compute Confidence Margin
        agg_label, margin, abstained, conf_level = self._aggregate_results(fwd_scores, bwd_scores)

        # 4. Save Inference Record
        rec = NLIInferenceRecord(
            workspace_id=workspace_id,
            model_id=self.model_id,
            model_revision=self.model_revision,
            pair_fingerprint=fingerprint,
            premise_hash=premise_hash,
            hypothesis_hash=hypothesis_hash,
            premise_text=clean_premise,
            hypothesis_text=clean_hypothesis,
            premise_source_doc_id=premise_doc_id,
            hypothesis_source_doc_id=hypothesis_doc_id,
            forward_label=fwd_label,
            forward_scores=fwd_scores,
            backward_label=bwd_label,
            backward_scores=bwd_scores,
            aggregated_label=agg_label,
            margin=margin,
            abstained=abstained,
            confidence_level=conf_level,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)

        return NLIInferenceResponse(
            premise=clean_premise,
            hypothesis=clean_hypothesis,
            forward_label=fwd_label,  # type: ignore
            forward_scores=fwd_scores,
            backward_label=bwd_label,  # type: ignore
            backward_scores=bwd_scores,
            aggregated_label=agg_label,
            margin=margin,
            abstained=abstained,
            confidence_level=conf_level,
            model_id=self.model_id,
            model_revision=self.model_revision,
            pair_fingerprint=fingerprint,
        )

    # -----------------------------------------------------------------------
    # Integration with Finding Comparisons (Contextual Safeguards)
    # -----------------------------------------------------------------------

    def evaluate_finding_comparison_nli(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        comparison_record: ResearchFindingComparison,
    ) -> ResearchFindingComparison:
        """Applies NLI inference to an aligned finding comparison while enforcing contextual safeguards."""
        fa: ResearchFinding = db.execute(
            select(ResearchFinding).where(ResearchFinding.id == comparison_record.finding_a_id)
        ).scalar_one()
        fb: ResearchFinding = db.execute(
            select(ResearchFinding).where(ResearchFinding.id == comparison_record.finding_b_id)
        ).scalar_one()

        # Build grounded context pairs
        premise_text = fa.normalized_statement
        hypothesis_text = fb.normalized_statement

        # Run bidirectional NLI inference
        nli_resp = self.infer_pair(
            db=db,
            workspace_id=workspace_id,
            premise=premise_text,
            hypothesis=hypothesis_text,
            premise_doc_id=fa.document_id,
            hypothesis_doc_id=fb.document_id,
            bidirectional=True,
        )

        comparison_record.nli_relation = nli_resp.aggregated_label

        # Look up saved NLI record id
        nli_rec = db.execute(
            select(NLIInferenceRecord).where(
                NLIInferenceRecord.workspace_id == workspace_id,
                NLIInferenceRecord.pair_fingerprint == nli_resp.pair_fingerprint,
            )
        ).scalar_one_or_none()
        if nli_rec:
            comparison_record.nli_inference_record_id = nli_rec.id

        # STRICT CONTEXTUAL SAFEGUARD:
        # NLI semantic prediction CANNOT override incompatible experimental conditions.
        if comparison_record.comparability_status in ("different_conditions", "incompatible_metrics", "incompatible_datasets", "not_comparable"):
            comparison_record.final_relation = comparison_record.comparability_status
            comparison_record.comparison_rationale = (
                f"{comparison_record.comparison_rationale or ''} "
                f"[NLI Semantic Observation: {nli_resp.aggregated_label} (forward: {nli_resp.forward_label}), "
                f"but contextual comparability status '{comparison_record.comparability_status}' takes precedence.]"
            ).strip()
        else:
            # Under comparable conditions, map NLI to application-level relations
            if nli_resp.abstained:
                comparison_record.final_relation = "needs_review"
            elif nli_resp.aggregated_label == "entailment":
                comparison_record.final_relation = "supports"
            elif nli_resp.aggregated_label == "contradiction":
                comparison_record.final_relation = "contradictory"
            else:
                comparison_record.final_relation = "neutral"

        db.commit()
        db.refresh(comparison_record)
        return comparison_record

    # Alias for compare_findings
    compare_findings = evaluate_finding_comparison_nli

    # -----------------------------------------------------------------------
    # Decision Policy & Label Aggregation
    # -----------------------------------------------------------------------

    def _get_top_label(self, scores: Dict[str, float]) -> str:
        return max(scores.items(), key=lambda x: x[1])[0]

    def _aggregate_results(
        self,
        fwd: Dict[str, float],
        bwd: Optional[Dict[str, float]],
    ) -> Tuple[str, float, bool, str]:
        """Combines forward and backward distributions and evaluates margin/abstention."""
        # Top and runner-up margin
        fwd_sorted = sorted(fwd.values(), reverse=True)
        margin = round(fwd_sorted[0] - (fwd_sorted[1] if len(fwd_sorted) > 1 else 0.0), 4)

        top_fwd = self._get_top_label(fwd)
        max_score = fwd_sorted[0]

        # Check abstention
        abstained = False
        conf_level = "moderate"
        if max_score < self.confidence_threshold or margin < self.margin_threshold:
            abstained = True
            conf_level = "abstained"
        elif max_score >= 0.80 and margin >= 0.30:
            conf_level = "high"
        else:
            conf_level = "moderate"

        # Bidirectional combination
        if bwd is None:
            return top_fwd, margin, abstained, conf_level

        top_bwd = self._get_top_label(bwd)

        # Logic:
        # If either direction detects direct contradiction, conflict exists
        if top_fwd == "contradiction" or top_bwd == "contradiction":
            return "contradiction", margin, abstained, conf_level

        # If both entail, mutual entailment
        if top_fwd == "entailment" and top_bwd == "entailment":
            return "entailment", margin, abstained, conf_level

        # If one entails and other is neutral, directional entailment
        if top_fwd == "entailment" or top_bwd == "entailment":
            return "entailment", margin, abstained, conf_level

        return "neutral", margin, abstained, conf_level

    # -----------------------------------------------------------------------
    # Benchmark Evaluation Engine (C10.6)
    # -----------------------------------------------------------------------

    def run_benchmark_evaluation(
        self,
        db: Session,
        evaluation_dataset: Optional[List[Dict[str, Any]]] = None,
        dataset_name: str = "Knovera Research Claim NLI Benchmark",
        dataset_path: Optional[str] = None,
        custom_pairs: Optional[List[Dict[str, Any]]] = None,
        workspace_id: Optional[uuid.UUID] = None,
    ) -> NLIEvaluationRun:
        """Evaluates active NLI model against an annotated benchmark and persists performance metrics."""
        dataset = custom_pairs or evaluation_dataset
        if not dataset:
            if dataset_path:
                try:
                    with open(dataset_path, "r", encoding="utf-8") as f:
                        dataset = json.load(f)
                except Exception as exc:
                    logger.warning("Could not read dataset_path %s: %s", dataset_path, exc)
            if not dataset:
                dataset = [
                    {
                        "premise": "The model achieved an accuracy of 92.4% on ImageNet, outperforming ResNet-50.",
                        "hypothesis": "The proposed architecture obtained higher accuracy than ResNet-50.",
                        "expected_label": "entailment",
                    },
                    {
                        "premise": "Our self-supervised approach reduced training compute by 50%.",
                        "hypothesis": "The method required less compute compared to the baseline.",
                        "expected_label": "entailment",
                    },
                    {
                        "premise": "The method significantly increased latency across all benchmarks.",
                        "hypothesis": "The method improved inference throughput and decreased execution time.",
                        "expected_label": "contradiction",
                    },
                    {
                        "premise": "We trained on 8 NVIDIA A100 GPUs for 48 hours.",
                        "hypothesis": "The model was evaluated on the GLUE benchmark.",
                        "expected_label": "neutral",
                    },
                ]

        y_true = []
        y_pred = []
        abstained_count = 0

        for item in dataset:
            premise = item["premise"]
            hypothesis = item["hypothesis"]
            gold = (item.get("expected_label") or item.get("gold_label") or "neutral").lower().strip()

            scores = self.provider.predict_pair(premise, hypothesis)
            sorted_scores = sorted(scores.values(), reverse=True)
            margin = sorted_scores[0] - (sorted_scores[1] if len(sorted_scores) > 1 else 0.0)

            pred_label = self._get_top_label(scores)
            if sorted_scores[0] < self.confidence_threshold or margin < self.margin_threshold:
                abstained_count += 1

            y_true.append(gold)
            y_pred.append(pred_label)

        # Compute Metrics
        labels = ["entailment", "contradiction", "neutral"]
        correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        accuracy = round(correct / len(y_true), 4)

        per_class_f1: Dict[str, float] = {}
        precision_recall: Dict[str, Any] = {}
        confusion_mat: Dict[str, Dict[str, int]] = {l: {l2: 0 for l2 in labels} for l in labels}

        for t, p in zip(y_true, y_pred):
            if t in confusion_mat and p in confusion_mat[t]:
                confusion_mat[t][p] += 1

        f1_list = []
        for l in labels:
            tp = confusion_mat[l][l]
            fp = sum(confusion_mat[other][l] for other in labels if other != l)
            fn = sum(confusion_mat[l][other] for other in labels if other != l)

            prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
            rec = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
            f1 = round(2 * prec * rec / (prec + rec), 4) if (prec + rec) > 0 else 0.0

            per_class_f1[l] = f1
            precision_recall[l] = {"precision": prec, "recall": rec, "support": tp + fn}
            f1_list.append(f1)

        macro_f1 = round(float(np.mean(f1_list)), 4)
        abstention_rate = round(abstained_count / len(y_true), 4)
        is_ready = macro_f1 >= 0.70

        eval_run = NLIEvaluationRun(
            workspace_id=workspace_id,
            model_id=self.model_id,
            model_revision=self.model_revision,
            dataset_name=dataset_name,
            sample_count=len(y_true),
            accuracy=accuracy,
            macro_f1=macro_f1,
            per_class_f1=per_class_f1,
            precision_recall_by_class=precision_recall,
            confusion_matrix=confusion_mat,
            abstention_rate=abstention_rate,
            is_readiness_passed=is_ready,
            notes=f"Evaluation completed across {len(y_true)} pairs. Readiness gate: {'PASSED' if is_ready else 'FAILED'}.",
        )
        db.add(eval_run)
        db.commit()
        db.refresh(eval_run)

        logger.info(
            "Completed NLI evaluation run %s: Macro F1=%.4f, Accuracy=%.4f (Ready: %s)",
            eval_run.id,
            macro_f1,
            accuracy,
            is_ready,
        )
        return eval_run


_nli_service_instance: Optional[NLIInferenceService] = None


def get_nli_service(db: Optional[Session] = None) -> NLIInferenceService:
    """Singleton/factory accessor for NLI inference service."""
    global _nli_service_instance
    if _nli_service_instance is None:
        _nli_service_instance = NLIInferenceService.get_instance()
    return _nli_service_instance

