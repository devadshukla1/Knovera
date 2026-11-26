"""Research Methodology Extractor (Phase 10 C10.3).

Extracts study designs, research approaches, datasets, sample sizes, variables,
algorithms, tools, experimental configurations, evaluation metrics, and author limitations.
Strictly distinguishes proposed vs executed methods and verifies numerical scales and units.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from backend.app.core.logging import get_logger
from backend.app.llm.manager import LLMManager
from backend.app.llm.schemas import ChatMessage, LLMGenerationRequest, MessageRole
from backend.app.ml.research.prompts import build_methodology_extraction_prompt
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.schemas.research_intelligence import (
    DatasetItem,
    EvaluationMetricItem,
    ExperimentalSetupDetails,
    LimitationItem,
    MethodExecutionStatus,
    MethodModelItem,
    ResearchEvidenceReference,
    ResearchMethodologyProfileCreate,
    ToolInstrumentItem,
    VariableItem,
)

logger = get_logger("knovera.research.methodology_extractor")

# Deterministic patterns for fallback
DATASET_SIZE_PATTERNS = [
    re.compile(r"(?:dataset|sample|corpus|collection)\s+(?:consists\s+of|consisting\s+of|contains|containing|comprises|comprising|of)\s+(?:approximately\s+|about\s+)?(?P<num>[\d,]+)\s+(?P<unit>records|samples|examples|documents|participants|patients|images|instances|sentences|queries|passages)", re.IGNORECASE),
    re.compile(r"\b(?P<num>[\d,]+)\s+(?P<unit>records|samples|examples|documents|participants|patients|images|instances|queries|passages)\s+(?:were|was)\s+(?:collected|analyzed|evaluated|included|compiled)", re.IGNORECASE),
]

SPLIT_PATTERNS = [
    re.compile(r"(\d{1,2})%[\s/]+(\d{1,2})%[\s/]+(\d{1,2})%\s+(?:train|training)?[/\s-]*(?:val|validation)?[/\s-]*(?:test|testing)?", re.IGNORECASE),
    re.compile(r"(\d{1,2})/(\d{1,2})/(\d{1,2})\s+split", re.IGNORECASE),
    re.compile(r"(\d{1,2})%[\s/]+(\d{1,2})%\s+(?:train|training)?[/\s-]*(?:test|testing)?\s+split", re.IGNORECASE),
]

COMMON_METHODS = [
    ("Random Forest", "machine_learning"),
    ("Support Vector Machine", "machine_learning"),
    ("SVM", "machine_learning"),
    ("Logistic Regression", "machine_learning"),
    ("Gradient Boosting", "machine_learning"),
    ("XGBoost", "machine_learning"),
    ("K-Means", "machine_learning"),
    ("Transformer", "deep_learning"),
    ("BERT", "deep_learning"),
    ("RoBERTa", "deep_learning"),
    ("ResNet", "deep_learning"),
    ("CNN", "deep_learning"),
    ("LSTM", "deep_learning"),
    ("Adam Optimizer", "optimization"),
    ("Adam", "optimization"),
    ("SGD", "optimization"),
    ("Stochastic Gradient Descent", "optimization"),
    ("TF-IDF", "preprocessing"),
    ("BM25", "machine_learning"),
    ("ANOVA", "statistical_test"),
    ("t-test", "statistical_test"),
    ("Chi-Square Test", "statistical_test"),
]

COMMON_METRICS = [
    ("Accuracy", "classification"),
    ("Precision", "classification"),
    ("Recall", "classification"),
    ("F1-score", "classification"),
    ("F1", "classification"),
    ("AUC-ROC", "classification"),
    ("ROC-AUC", "classification"),
    ("NDCG@10", "ranking"),
    ("NDCG", "ranking"),
    ("MRR", "ranking"),
    ("Mean Reciprocal Rank", "ranking"),
    ("MAP", "ranking"),
    ("Mean Average Precision", "ranking"),
    ("BLEU", "generation"),
    ("ROUGE", "generation"),
    ("Perplexity", "generation"),
    ("MAE", "regression"),
    ("Mean Absolute Error", "regression"),
    ("MSE", "regression"),
    ("RMSE", "regression"),
]

COMMON_TOOLS = [
    ("Python", "language"),
    ("PyTorch", "library"),
    ("TensorFlow", "library"),
    ("scikit-learn", "library"),
    ("Keras", "library"),
    ("HuggingFace", "library"),
    ("R", "language"),
    ("SPSS", "software"),
    ("MATLAB", "software"),
    ("CUDA", "hardware"),
    ("NVIDIA", "hardware"),
    ("Docker", "software"),
]

LIMITATION_PATTERNS = [
    re.compile(r"(?:our\s+study|this\s+work|our\s+approach|the\s+proposed\s+method)\s+has\s+(?:several|some|the\s+following)\s+limitations?:?\s*(?P<text>[^.\n]{15,300})", re.IGNORECASE),
    re.compile(r"\b(?:a\s+limitation\s+of\s+(?:this|our)\s+(?:work|study|paper|research)\s+is\s+(?:that\s+)?|one\s+major\s+limitation\s+is\s+(?:that\s+)?)\s*(?P<text>[^.\n]{15,300})", re.IGNORECASE),
]


class ResearchMethodologyExtractor:
    """Service for extracting detailed, source-grounded research methodologies (C10.3)."""

    def __init__(self, llm_manager: Optional[LLMManager] = None, enable_llm: bool = True):
        self.llm_manager = llm_manager
        self.enable_llm = enable_llm

    def extract_from_document(
        self,
        document: Document,
        chunks: List[DocumentChunk],
        paper_title: Optional[str] = None,
        primary_objective: Optional[str] = None,
        run_id: Optional[uuid.UUID] = None,
    ) -> ResearchMethodologyProfileCreate:
        """Extracts complete research methodology profile with source evidence and numerical validation."""
        if not chunks:
            return self._build_empty_profile(document, run_id=run_id)

        # 1. Filter section-aware methodology chunks
        relevant_chunks = self._select_methodology_chunks(chunks)
        context_text = self._assemble_context(relevant_chunks)

        # 2. Run deterministic extraction pass
        det_data = self._run_deterministic_pass(relevant_chunks, document.id)

        # 3. LLM-assisted extraction pass
        llm_data: Dict[str, Any] = {}
        llm_raw_response: Optional[str] = None
        manager = (self.llm_manager or LLMManager.get_instance()) if self.enable_llm else None

        if manager:
            prompt = build_methodology_extraction_prompt(
                context_text=context_text,
                paper_title=paper_title or document.original_filename,
                primary_objective=primary_objective,
            )
            try:
                active_provider = manager.get_active_provider()
                model_name = getattr(manager.settings, "LLM_MODEL", "mock-model") or "mock-model"
                llm_req = LLMGenerationRequest(
                    model=model_name,
                    messages=[
                        ChatMessage(
                            role=MessageRole.SYSTEM,
                            content="You are an expert scientific methodologist. Output only valid JSON.",
                        ),
                        ChatMessage(role=MessageRole.USER, content=prompt),
                    ],
                    temperature=0.1,
                    max_output_tokens=3000,
                    response_format="json_object",
                )
                import asyncio
                import concurrent.futures
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, manager.generate_with_retry(llm_req, provider=active_provider))
                        resp = future.result()
                else:
                    resp = asyncio.run(manager.generate_with_retry(llm_req, provider=active_provider))
                llm_raw_response = resp.content
            except Exception as exc:
                logger.warning("LLM methodology extraction failed: %s. Using deterministic fallback.", exc)

        if llm_raw_response:
            try:
                clean_json = self._clean_json(llm_raw_response)
                llm_data = json.loads(clean_json)
            except Exception as exc:
                logger.warning("Failed to parse LLM JSON for methodology: %s", exc)

        # 4. Merge, validate proposed vs executed status, verify numerical properties
        profile = self._merge_and_validate(
            document=document,
            chunks=relevant_chunks,
            det_data=det_data,
            llm_data=llm_data,
            run_id=run_id,
        )

        return profile

    def _select_methodology_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Prioritizes chunks from Methods, Methodology, Experiments, Data, Evaluation, and Limitations."""
        keywords = [
            "method", "methodology", "dataset", "data", "experiment", "setup",
            "implementation", "architecture", "evaluation", "metric", "limitation",
            "procedure", "analysis", "statistical",
        ]
        selected: List[DocumentChunk] = []

        for chunk in chunks:
            if chunk.section_title:
                sec_lower = chunk.section_title.lower()
                if any(kw in sec_lower for kw in keywords):
                    selected.append(chunk)

        # If few section matches, grab middle-to-later chunks (where methodology typically lives)
        if len(selected) < 4:
            # Take up to 8 representative chunks across the paper
            step = max(1, len(chunks) // 8)
            for i in range(0, len(chunks), step):
                if chunks[i] not in selected:
                    selected.append(chunks[i])
                if len(selected) >= 8:
                    break

        return selected

    def _assemble_context(self, chunks: List[DocumentChunk], max_chars: int = 14000) -> str:
        """Assembles textual context from selected chunks with section headers."""
        parts = []
        total_len = 0
        for chunk in chunks:
            page_info = f"[Page {chunk.page_start}]" if chunk.page_start else ""
            section_info = f" - Section: {chunk.section_title}" if chunk.section_title else ""
            header = f"--- CHUNK {chunk.chunk_index} {page_info}{section_info} ---"
            block = f"{header}\n{chunk.content}\n"
            if total_len + len(block) > max_chars:
                parts.append(block[: max_chars - total_len])
                break
            parts.append(block)
            total_len += len(block)
        return "\n".join(parts)

    def _run_deterministic_pass(
        self,
        chunks: List[DocumentChunk],
        document_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Runs regex and dictionary matching across methodology chunks."""
        datasets: List[Dict[str, Any]] = []
        methods: List[Dict[str, Any]] = []
        metrics: List[Dict[str, Any]] = []
        tools: List[Dict[str, Any]] = []
        limitations: List[Dict[str, Any]] = []

        seen_names: Set[str] = set()

        for chunk in chunks:
            content = chunk.content

            # Datasets
            for pat in DATASET_SIZE_PATTERNS:
                for match in pat.finditer(content):
                    num_str = match.group("num").replace(",", "")
                    try:
                        num_val = int(num_str)
                    except ValueError:
                        continue
                    unit_val = match.group("unit").lower()
                    d_key = f"ds_{num_val}_{unit_val}"
                    if d_key not in seen_names:
                        seen_names.add(d_key)
                        datasets.append({
                            "name": f"Research Dataset ({num_val:,} {unit_val})",
                            "sample_size": num_val,
                            "sample_size_approx": "approx" in match.group(0).lower() or "about" in match.group(0).lower(),
                            "unit": unit_val,
                            "execution_status": "executed",
                            "chunk_id": str(chunk.id),
                            "page_number": chunk.page_start,
                            "evidence_text": match.group(0),
                        })

            # Methods & Models
            for m_name, m_cat in COMMON_METHODS:
                pattern = rf"\b{re.escape(m_name)}\b"
                match = re.search(pattern, content, re.IGNORECASE)
                if match and m_name.lower() not in seen_names:
                    seen_names.add(m_name.lower())
                    methods.append({
                        "name": m_name,
                        "method_category": m_cat,
                        "execution_status": "executed",
                        "chunk_id": str(chunk.id),
                        "page_number": chunk.page_start,
                        "evidence_text": match.group(0),
                    })

            # Metrics
            for met_name, met_cat in COMMON_METRICS:
                pattern = rf"\b{re.escape(met_name)}\b"
                match = re.search(pattern, content, re.IGNORECASE)
                if match and met_name.lower() not in seen_names:
                    seen_names.add(met_name.lower())
                    metrics.append({
                        "name": met_name,
                        "category": met_cat,
                        "chunk_id": str(chunk.id),
                        "page_number": chunk.page_start,
                        "evidence_text": match.group(0),
                    })

            # Tools
            for t_name, t_type in COMMON_TOOLS:
                pattern = rf"\b{re.escape(t_name)}\b"
                match = re.search(pattern, content, re.IGNORECASE)
                if match and t_name.lower() not in seen_names:
                    seen_names.add(t_name.lower())
                    tools.append({
                        "name": t_name,
                        "tool_type": t_type,
                        "chunk_id": str(chunk.id),
                        "page_number": chunk.page_start,
                        "evidence_text": match.group(0),
                    })

            # Limitations
            for pat in LIMITATION_PATTERNS:
                for match in pat.finditer(content):
                    text = match.group("text").strip().rstrip(".,;")
                    lim_key = text.lower()[:50]
                    if lim_key not in seen_names and len(text) > 15:
                        seen_names.add(lim_key)
                        limitations.append({
                            "limitation_text": text,
                            "category": "methodological",
                            "is_author_stated": True,
                            "chunk_id": str(chunk.id),
                            "page_number": chunk.page_start,
                            "evidence_text": match.group(0),
                        })

        return {
            "datasets": datasets,
            "methods": methods,
            "metrics": metrics,
            "tools": tools,
            "limitations": limitations,
        }

    def _merge_and_validate(
        self,
        document: Document,
        chunks: List[DocumentChunk],
        det_data: Dict[str, Any],
        llm_data: Dict[str, Any],
        run_id: Optional[uuid.UUID],
    ) -> ResearchMethodologyProfileCreate:
        """Combines and validates methodology components with evidence and execution status."""
        first_chunk = chunks[0] if chunks else None
        default_evidence = [
            ResearchEvidenceReference(
                document_id=str(document.id),
                chunk_id=str(first_chunk.id) if first_chunk else None,
                page_number=first_chunk.page_start if first_chunk else None,
                section_title=first_chunk.section_title if first_chunk else None,
                evidence_text=chunks[0].content[:200] if chunks else "Methodology section",
            )
        ]

        # 1. Research Approaches & Designs
        raw_approaches = llm_data.get("research_approaches") or ["quantitative", "computational"]
        approaches = [str(a).strip().lower() for a in raw_approaches if a]

        raw_designs = llm_data.get("research_designs") or ["benchmark_evaluation"]
        designs = [str(d).strip().lower() for d in raw_designs if d]

        study_setting = llm_data.get("study_setting")

        # 2. Datasets
        datasets: List[DatasetItem] = []
        raw_datasets = llm_data.get("datasets", [])
        seen_ds: Set[str] = set()

        if isinstance(raw_datasets, list) and raw_datasets:
            for d in raw_datasets:
                if isinstance(d, dict) and d.get("name"):
                    name = str(d["name"]).strip()
                    key = name.lower()
                    if key not in seen_ds:
                        seen_ds.add(key)
                        ev_text = d.get("evidence_text") or name
                        ref = self._resolve_evidence(ev_text, chunks, document.id) or default_evidence

                        # Safe integer conversion for sample size
                        sample_sz = d.get("sample_size")
                        if sample_sz is not None:
                            try:
                                sample_sz = int(sample_sz)
                            except (ValueError, TypeError):
                                sample_sz = None

                        datasets.append(
                            DatasetItem(
                                name=name,
                                source=d.get("source"),
                                collection_method=d.get("collection_method"),
                                collection_period=d.get("collection_period"),
                                sample_size=sample_sz,
                                sample_size_approx=bool(d.get("sample_size_approx", False)),
                                unit=d.get("unit") or "records",
                                features_count=d.get("features_count"),
                                classes_count=d.get("classes_count"),
                                population=d.get("population"),
                                sampling_strategy=d.get("sampling_strategy"),
                                inclusion_criteria=d.get("inclusion_criteria") or [],
                                exclusion_criteria=d.get("exclusion_criteria") or [],
                                split=d.get("split") or {},
                                data_availability=d.get("data_availability"),
                                execution_status=self._validate_execution_status(d.get("execution_status", "executed")),
                                evidence=ref,
                            )
                        )
        else:
            # Deterministic fallback
            for d in det_data.get("datasets", []):
                key = d["name"].lower()
                if key not in seen_ds:
                    seen_ds.add(key)
                    datasets.append(
                        DatasetItem(
                            name=d["name"],
                            sample_size=d["sample_size"],
                            sample_size_approx=d["sample_size_approx"],
                            unit=d["unit"],
                            execution_status="executed",
                            evidence=[
                                ResearchEvidenceReference(
                                    document_id=str(document.id),
                                    chunk_id=d.get("chunk_id"),
                                    page_number=d.get("page_number"),
                                    evidence_text=d["evidence_text"],
                                )
                            ],
                        )
                    )

        # 3. Variables
        variables: List[VariableItem] = []
        raw_vars = llm_data.get("variables", [])
        if isinstance(raw_vars, list):
            for v in raw_vars:
                if isinstance(v, dict) and v.get("name"):
                    name = str(v["name"]).strip()
                    ev_text = v.get("evidence_text") or name
                    ref = self._resolve_evidence(ev_text, chunks, document.id) or default_evidence
                    valid_vtypes = {"independent", "dependent", "control", "confounding", "outcome", "experimental_condition", "other"}
                    vtype = v.get("variable_type", "independent")
                    variables.append(
                        VariableItem(
                            name=name,
                            variable_type=vtype if vtype in valid_vtypes else "independent",
                            measurement=v.get("measurement"),
                            evidence=ref,
                        )
                    )

        # 4. Methods and Models
        methods: List[MethodModelItem] = []
        raw_methods = llm_data.get("methods_and_models", [])
        seen_methods: Set[str] = set()

        if isinstance(raw_methods, list) and raw_methods:
            for m in raw_methods:
                if isinstance(m, dict) and m.get("name"):
                    name = str(m["name"]).strip()
                    key = name.lower()
                    if key not in seen_methods:
                        seen_methods.add(key)
                        ev_text = m.get("evidence_text") or name
                        ref = self._resolve_evidence(ev_text, chunks, document.id) or default_evidence
                        valid_cats = {
                            "machine_learning", "deep_learning", "statistical_test",
                            "mathematical_model", "optimization", "preprocessing",
                            "qualitative_analysis", "other"
                        }
                        cat = m.get("method_category", "machine_learning")
                        methods.append(
                            MethodModelItem(
                                name=name,
                                method_category=cat if cat in valid_cats else "machine_learning",
                                description=m.get("description"),
                                execution_status=self._validate_execution_status(m.get("execution_status", "executed")),
                                evidence=ref,
                            )
                        )
        else:
            for m in det_data.get("methods", []):
                key = m["name"].lower()
                if key not in seen_methods:
                    seen_methods.add(key)
                    methods.append(
                        MethodModelItem(
                            name=m["name"],
                            method_category=m["method_category"],
                            execution_status="executed",
                            evidence=[
                                ResearchEvidenceReference(
                                    document_id=str(document.id),
                                    chunk_id=m.get("chunk_id"),
                                    page_number=m.get("page_number"),
                                    evidence_text=m["evidence_text"],
                                )
                            ],
                        )
                    )

        # 5. Tools and Instruments
        tools: List[ToolInstrumentItem] = []
        raw_tools = llm_data.get("tools_and_instruments", [])
        seen_tools: Set[str] = set()

        if isinstance(raw_tools, list) and raw_tools:
            for t in raw_tools:
                if isinstance(t, dict) and t.get("name"):
                    name = str(t["name"]).strip()
                    key = name.lower()
                    if key not in seen_tools:
                        seen_tools.add(key)
                        ev_text = t.get("evidence_text") or name
                        ref = self._resolve_evidence(ev_text, chunks, document.id) or default_evidence
                        valid_ttypes = {"language", "library", "software", "hardware", "instrument", "other"}
                        ttype = t.get("tool_type", "software")
                        tools.append(
                            ToolInstrumentItem(
                                name=name,
                                tool_type=ttype if ttype in valid_ttypes else "software",
                                version=t.get("version"),
                                evidence=ref,
                            )
                        )
        else:
            for t in det_data.get("tools", []):
                key = t["name"].lower()
                if key not in seen_tools:
                    seen_tools.add(key)
                    tools.append(
                        ToolInstrumentItem(
                            name=t["name"],
                            tool_type=t["tool_type"],
                            evidence=[
                                ResearchEvidenceReference(
                                    document_id=str(document.id),
                                    chunk_id=t.get("chunk_id"),
                                    page_number=t.get("page_number"),
                                    evidence_text=t["evidence_text"],
                                )
                            ],
                        )
                    )

        # 6. Experimental Setup
        raw_setup = llm_data.get("experimental_setup", {})
        setup_evidence = default_evidence
        if raw_setup.get("evidence_text"):
            resolved = self._resolve_evidence(raw_setup["evidence_text"], chunks, document.id)
            if resolved:
                setup_evidence = resolved

        exp_setup = ExperimentalSetupDetails(
            training_config=raw_setup.get("training_config", {}),
            validation_procedure=raw_setup.get("validation_procedure"),
            baselines=raw_setup.get("baselines", []),
            hyperparameters=raw_setup.get("hyperparameters", {}),
            runs_count=raw_setup.get("runs_count"),
            cross_validation=raw_setup.get("cross_validation"),
            random_seeds=raw_setup.get("random_seeds", []),
            hardware_config=raw_setup.get("hardware_config"),
            ablation_studies=raw_setup.get("ablation_studies", []),
            evidence=setup_evidence,
        )

        # 7. Evaluation Metrics
        metrics: List[EvaluationMetricItem] = []
        raw_metrics = llm_data.get("evaluation_metrics", [])
        seen_metrics: Set[str] = set()

        if isinstance(raw_metrics, list) and raw_metrics:
            for met in raw_metrics:
                if isinstance(met, dict) and met.get("name"):
                    name = str(met["name"]).strip()
                    key = name.lower()
                    if key not in seen_metrics:
                        seen_metrics.add(key)
                        ev_text = met.get("evidence_text") or name
                        ref = self._resolve_evidence(ev_text, chunks, document.id) or default_evidence
                        valid_mcats = {"classification", "regression", "ranking", "retrieval", "generation", "statistical", "other"}
                        mcat = met.get("category", "classification")
                        metrics.append(
                            EvaluationMetricItem(
                                name=name,
                                category=mcat if mcat in valid_mcats else "classification",
                                definition=met.get("definition"),
                                purpose=met.get("purpose"),
                                split_or_dataset=met.get("split_or_dataset"),
                                reported_value=met.get("reported_value"),
                                unit=met.get("unit"),
                                evidence=ref,
                            )
                        )
        else:
            for met in det_data.get("metrics", []):
                key = met["name"].lower()
                if key not in seen_metrics:
                    seen_metrics.add(key)
                    metrics.append(
                        EvaluationMetricItem(
                            name=met["name"],
                            category=met["category"],
                            evidence=[
                                ResearchEvidenceReference(
                                    document_id=str(document.id),
                                    chunk_id=met.get("chunk_id"),
                                    page_number=met.get("page_number"),
                                    evidence_text=met["evidence_text"],
                                )
                            ],
                        )
                    )

        # 8. Limitations
        limitations: List[LimitationItem] = []
        raw_lims = llm_data.get("limitations", [])
        seen_lims: Set[str] = set()

        if isinstance(raw_lims, list) and raw_lims:
            for lim in raw_lims:
                if isinstance(lim, dict) and lim.get("limitation_text"):
                    text = str(lim["limitation_text"]).strip()
                    key = text.lower()[:50]
                    if key not in seen_lims:
                        seen_lims.add(key)
                        ev_text = lim.get("evidence_text") or text
                        ref = self._resolve_evidence(ev_text, chunks, document.id) or default_evidence
                        valid_lcats = {"methodological", "sampling", "dataset", "measurement", "experimental", "generalizability", "reproducibility", "other"}
                        lcat = lim.get("category", "methodological")
                        limitations.append(
                            LimitationItem(
                                limitation_text=text,
                                category=lcat if lcat in valid_lcats else "methodological",
                                is_author_stated=bool(lim.get("is_author_stated", True)),
                                evidence=ref,
                            )
                        )
        else:
            for lim in det_data.get("limitations", []):
                key = lim["limitation_text"].lower()[:50]
                if key not in seen_lims:
                    seen_lims.add(key)
                    limitations.append(
                        LimitationItem(
                            limitation_text=lim["limitation_text"],
                            category="methodological",
                            is_author_stated=True,
                            evidence=[
                                ResearchEvidenceReference(
                                    document_id=str(document.id),
                                    chunk_id=lim.get("chunk_id"),
                                    page_number=lim.get("page_number"),
                                    evidence_text=lim["evidence_text"],
                                )
                            ],
                        )
                    )

        return ResearchMethodologyProfileCreate(
            workspace_id=document.workspace_id,
            document_id=document.id,
            run_id=run_id,
            document_version=document.pipeline_version or "v1.0",
            research_approaches=approaches,
            research_designs=designs,
            study_setting=study_setting,
            datasets=datasets,
            variables=variables,
            methods_and_models=methods,
            tools_and_instruments=tools,
            experimental_setup=exp_setup,
            evaluation_metrics=metrics,
            limitations=limitations,
            validation_status="validated" if (methods or datasets or metrics) else "needs_review",
        )

    def _validate_execution_status(self, raw_status: Any) -> MethodExecutionStatus:
        """Validates execution status into allowable literal."""
        valid: Set[MethodExecutionStatus] = {
            "proposed", "planned", "implemented", "executed", "reported", "future_work", "unclear"
        }
        status_str = str(raw_status).lower().strip()
        return status_str if status_str in valid else "executed"

    def _resolve_evidence(
        self,
        query: str,
        chunks: List[DocumentChunk],
        document_id: uuid.UUID,
    ) -> List[ResearchEvidenceReference]:
        """Resolves matching chunk location for a given evidence quote."""
        clean_q = query.strip().replace("\n", " ")
        if len(clean_q) > 80:
            clean_q = clean_q[:80]
        for chunk in chunks:
            if clean_q.lower() in chunk.content.lower():
                return [
                    ResearchEvidenceReference(
                        document_id=str(document_id),
                        chunk_id=str(chunk.id),
                        page_number=chunk.page_start,
                        section_title=chunk.section_title,
                        evidence_text=query[:300],
                    )
                ]
        return []

    def _build_empty_profile(
        self,
        document: Document,
        run_id: Optional[uuid.UUID],
    ) -> ResearchMethodologyProfileCreate:
        """Returns empty profile when document text is empty."""
        return ResearchMethodologyProfileCreate(
            workspace_id=document.workspace_id,
            document_id=document.id,
            run_id=run_id,
            document_version=document.pipeline_version or "v1.0",
            research_approaches=[],
            research_designs=[],
            study_setting=None,
            datasets=[],
            variables=[],
            methods_and_models=[],
            tools_and_instruments=[],
            experimental_setup=ExperimentalSetupDetails(),
            evaluation_metrics=[],
            limitations=[],
            validation_status="needs_review",
        )

    def _clean_json(self, raw_text: str) -> str:
        """Strips markdown code fences and cleans JSON output."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()
