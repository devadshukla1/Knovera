"""Structured prompts and JSON schemas for Knovera Research Intelligence (Phase 10).

Covers:
- C10.1 Bibliographic Metadata Extraction
- C10.2 Research Objectives, Questions, and Hypotheses
- C10.3 Methodology, Datasets, Variables, Setup, and Metrics
"""

import json
from typing import Any, Dict, List, Optional


def build_metadata_extraction_prompt(
    context_text: str,
    embedded_metadata: Optional[Dict[str, Any]] = None,
    filename: Optional[str] = None,
) -> str:
    """Builds prompt for C10.1 Research Document Metadata Extraction."""
    embedded_str = json.dumps(embedded_metadata or {}, indent=2)

    return f"""You are the Lead Bibliographic and Research Intelligence Specialist for the Knovera platform.
Your task is to extract structured, source-grounded bibliographic and descriptive metadata from the research document context provided below.

CRITICAL EXTRACTION RULES:
1. STRICT SOURCE GROUNDING: Extract ONLY what is explicitly stated in the document text. NEVER fabricate or guess titles, author names, affiliations, publication dates, DOIs, or venues.
2. MISSING VALUES: If a field is not present in the text, return null or empty list. DO NOT invent placeholder values.
3. TITLE & AUTHORS: Extract exact spelling of title and authors. Maintain author order (1-based). Identify affiliations and email/corresponding author status ONLY if marked.
4. DOCUMENT TYPE: Classify into one of: 'journal_article', 'conference_paper', 'preprint', 'thesis', 'dissertation', 'technical_report', 'research_proposal', 'working_paper', 'systematic_review', 'survey_paper', 'research_presentation', 'unknown'.
5. EMBEDDED METADATA RECONCILIATION:
   Embedded file metadata from the PDF/Office container is provided below:
{embedded_str}
   If the embedded metadata conflicts with the displayed document title page or header, prioritize the DISPLAYED DOCUMENT CONTENT. Note any conflict explicitly.
6. EVIDENCE: For each extracted field, provide the exact verbatim text excerpt from the context that supports it.

DOCUMENT FILENAME: {filename or 'Unknown'}

DOCUMENT CONTENT:
\"\"\"
{context_text}
\"\"\"

Return ONLY valid JSON with this exact schema:
{{
  "document_type": "journal_article | conference_paper | preprint | thesis | technical_report | etc.",
  "title": "Exact Title as printed",
  "subtitle": "Subtitle or null",
  "alternative_title": "Alternative title or null",
  "language": "en",
  "abstract": "Abstract text or null",
  "keywords": ["keyword1", "keyword2"],
  "authors": [
    {{
      "name": "Full Name",
      "order": 1,
      "affiliation": "Department / Institution",
      "department": "Department or null",
      "institution": "University / Organization or null",
      "country": "Country or null",
      "is_corresponding": false,
      "orcid": "0000-0000-0000-0000 or null"
    }}
  ],
  "publication_year": 2024,
  "publication_date": "YYYY-MM-DD or Month YYYY or null",
  "journal_name": "Journal Name or null",
  "conference_name": "Conference Name or null",
  "publisher": "Publisher or null",
  "volume": "Volume or null",
  "issue": "Issue or null",
  "page_range": "e.g. 1-15 or null",
  "doi": "10.xxxx/xxxx or null",
  "arxiv_id": "arXiv:xxxx.xxxxx or null",
  "isbn_issn": "ISSN or null",
  "publication_status": "published | preprint | under_review | null",
  "funding_organization": "Funding body or null",
  "acknowledgements": "Acknowledgements text or null",
  "grant_identifiers": ["Grant ID 1"],
  "research_domain": "e.g. Computer Science",
  "subdomain": "e.g. Information Retrieval",
  "evidence": [
    {{
      "field": "title",
      "evidence_text": "verbatim text excerpt"
    }},
    {{
      "field": "publication_year",
      "evidence_text": "verbatim text excerpt"
    }}
  ],
  "conflicts": [
    {{
      "field": "title",
      "content_value": "Title from page",
      "embedded_value": "Title from PDF metadata",
      "conflict_reason": "Embedded metadata has export filename title"
    }}
  ]
}}
"""


def build_objective_extraction_prompt(
    context_text: str,
    paper_title: Optional[str] = None,
) -> str:
    """Builds prompt for C10.2 Research Objective Extraction."""
    return f"""You are the Chief Research Methodologist and Objective Analyst for Knovera.
Your task is to identify and structure the research objectives, problem statement, research questions, hypotheses, and contributions from the academic document context.

CRITICAL EXTRACTION RULES:
1. DISTINGUISH TYPES CAREFULLY:
   - Primary Objective: The overarching purpose/goal of the investigation.
   - Secondary Objectives: Sub-goals or supporting objectives.
   - Problem Statement: The specific gap, deficiency, or challenge in existing knowledge/technology.
   - Motivation: Why the authors consider solving this problem important.
   - Research Questions: Explicit questions the study sets out to answer.
   - Hypotheses: Falsifiable propositions (classify as 'null', 'alternative', 'directional', 'non_directional').
   - Scope: Target population, boundaries, time period, geographic scope, or explicit exclusions.
   - Claimed Contributions: What the authors claim they introduced, proved, built, or discovered.
2. DO NOT CONFUSE OR MERGE:
   - Do NOT turn motivation into an objective.
   - Do NOT turn an experimental finding into a research question.
   - Do NOT invent hypotheses if the authors did not state any.
3. ORIGINAL VS NORMALIZED:
   - Original text: Verbatim or near-verbatim statement from the paper.
   - Normalized text: Concise, clean formulation in standard academic style without changing the scope.
4. EVIDENCE: Every item MUST include an exact evidence_text quotation from the text below.
5. NO HALLUCINATION: If a document has no explicit hypotheses or research questions, return an empty array for that field.

PAPER TITLE CONTEXT: {paper_title or 'Research Document'}

DOCUMENT CONTENT:
\"\"\"
{context_text}
\"\"\"

Return ONLY valid JSON with this exact schema:
{{
  "primary_objective": "Main goal of the study or null",
  "problem_statement": "Specific problem addressed or null",
  "motivation": "Why this research is needed or null",
  "research_scope": {{
    "domain": "Domain or null",
    "target_population": "Target population/data or null",
    "study_environment": "Environment or null",
    "time_period": "Time period or null",
    "geographic_scope": "Geographic scope or null",
    "boundaries": ["boundary 1"],
    "exclusions": ["explicit exclusion 1"]
  }},
  "objectives": [
    {{
      "objective_type": "primary_objective | secondary_objective",
      "original_text": "Verbatim quote",
      "normalized_text": "Normalized concise statement",
      "is_primary": true,
      "evidence_text": "verbatim text excerpt from document"
    }}
  ],
  "research_questions": [
    {{
      "question_text": "What is the effect of X on Y?",
      "normalized_text": "Concise normalized question",
      "evidence_text": "verbatim text excerpt"
    }}
  ],
  "hypotheses": [
    {{
      "hypothesis_text": "Proposed hypothesis",
      "hypothesis_type": "alternative | null | directional | non_directional",
      "evidence_text": "verbatim text excerpt"
    }}
  ],
  "claimed_contributions": [
    {{
      "contribution_text": "Novel architecture proposed for Z",
      "contribution_type": "proposed | implemented | claimed | demonstrated",
      "evidence_text": "verbatim text excerpt"
    }}
  ]
}}
"""


def build_methodology_extraction_prompt(
    context_text: str,
    paper_title: Optional[str] = None,
    primary_objective: Optional[str] = None,
) -> str:
    """Builds prompt for C10.3 Methodology Extraction."""
    return f"""You are the Principal Scientific Methodologist for Knovera.
Your task is to perform an exhaustive, evidence-grounded extraction of the methodology, study design, datasets, variables, algorithms, experimental configuration, evaluation metrics, and author limitations from the document.

CRITICAL METHODOLOGICAL RULES:
1. PROPOSED VS EXECUTED:
   You MUST distinguish methods that were actually 'executed' or 'implemented' from those that are merely 'proposed', 'planned', or cited as 'future_work'.
2. DATASETS & SAMPLE SIZES:
   Extract exact sample sizes, numbers of observations, and feature counts. Preserve the unit (e.g. 'records', 'participants', 'samples', 'queries'). DO NOT assume training/test splits sum to 100% without verifying. If missing, leave null.
3. VARIABLES:
   Classify variables strictly as 'independent', 'dependent', 'control', 'confounding', or 'outcome' only when supported by the text.
4. METHODS & ALGORITHMS:
   Accurately distinguish algorithms (e.g. Random Forest vs XGBoost, BERT vs RoBERTa, Adam vs SGD). Keep distinct methods separate.
5. EXPERIMENTAL SETUP & HYPERPARAMETERS:
   Extract actual reported hyperparameter values, learning rates, epochs, random seeds, hardware, and baseline comparison models. DO NOT guess default values.
6. EVALUATION METRICS:
   Identify metrics (e.g., F1-score, NDCG@10, Accuracy, BLEU, MAE, AUC-ROC) separately from the achieved experimental results.
7. LIMITATIONS:
   Extract explicitly author-stated limitations and caveats (methodological, sampling, generalizability, computational).
8. EVIDENCE:
   Every single extracted component MUST include an exact evidence_text quotation.

PAPER CONTEXT:
Title: {paper_title or 'Research Document'}
Primary Objective: {primary_objective or 'Unknown'}

DOCUMENT CONTENT:
\"\"\"
{context_text}
\"\"\"

Return ONLY valid JSON with this exact schema:
{{
  "research_approaches": ["quantitative", "computational", "experimental"],
  "research_designs": ["controlled_experiment", "benchmark_evaluation", "algorithm_development"],
  "study_setting": "Laboratory / Simulation / Clinical or null",
  "datasets": [
    {{
      "name": "Dataset Name",
      "source": "Source / Repository or null",
      "collection_method": "Method or null",
      "collection_period": "Period or null",
      "sample_size": 10000,
      "sample_size_approx": false,
      "unit": "records | participants | documents | etc.",
      "features_count": 25,
      "classes_count": 2,
      "population": "Target population or null",
      "sampling_strategy": "Random / Stratified or null",
      "inclusion_criteria": ["criteria 1"],
      "exclusion_criteria": ["criteria 2"],
      "split": {{"training": "80%", "testing": "20%"}},
      "data_availability": "Publicly available at URL / on request or null",
      "execution_status": "executed | proposed | unclear",
      "evidence_text": "verbatim text excerpt"
    }}
  ],
  "variables": [
    {{
      "name": "Variable Name",
      "variable_type": "independent | dependent | control | confounding | outcome | experimental_condition",
      "measurement": "Scale or metric or null",
      "evidence_text": "verbatim text excerpt"
    }}
  ],
  "methods_and_models": [
    {{
      "name": "Algorithm / Model Name",
      "method_category": "machine_learning | deep_learning | statistical_test | optimization | preprocessing",
      "description": "Brief description",
      "execution_status": "executed | proposed | implemented | future_work",
      "evidence_text": "verbatim text excerpt"
    }}
  ],
  "tools_and_instruments": [
    {{
      "name": "PyTorch",
      "tool_type": "library | language | software | hardware | instrument",
      "version": "2.1 or null",
      "evidence_text": "verbatim text excerpt"
    }}
  ],
  "experimental_setup": {{
    "training_config": {{"optimizer": "Adam", "learning_rate": "1e-4", "batch_size": 32, "epochs": 10}},
    "validation_procedure": "5-fold cross validation or null",
    "baselines": ["BM25", "Standard BERT"],
    "hyperparameters": {{"dropout": 0.1, "warmup_steps": 500}},
    "runs_count": 5,
    "cross_validation": "5-fold",
    "random_seeds": [42],
    "hardware_config": "Single NVIDIA A100 GPU or null",
    "ablation_studies": ["Ablation without self-attention layer"],
    "evidence_text": "verbatim text excerpt"
  }},
  "evaluation_metrics": [
    {{
      "name": "NDCG@10",
      "category": "ranking | retrieval | classification",
      "definition": "Normalized Discounted Cumulative Gain at rank 10 or null",
      "purpose": "Measures ranking quality",
      "split_or_dataset": "Test set",
      "reported_value": null,
      "unit": null,
      "evidence_text": "verbatim text excerpt"
    }}
  ],
  "limitations": [
    {{
      "limitation_text": "Study was evaluated on English language only",
      "category": "generalizability | dataset | methodological | measurement",
      "is_author_stated": true,
      "evidence_text": "verbatim text excerpt"
    }}
  ]
}}
"""
