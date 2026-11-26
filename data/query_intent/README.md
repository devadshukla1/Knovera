# Knovera Query Intent Classification Dataset & Benchmark

**Taxonomy Version:** 1.0.0  
**Preprocessing Version:** 1.0.0  
**Phase:** Phase 5 — Query Intelligence & Intent Classification (C5.1 / C5.2 / C5.3)  
**Location:** `data/query_intent/`

---

## 1. Overview & Objective

This dataset provides the supervised learning benchmark for Knovera's upcoming Query Intent Classification system. The platform uses intent classification to route user research questions to adaptive retrieval pipelines (e.g. dense semantic search, lexical BM25, hybrid fusion, citation tracking, or multi-document synthesis).

The dataset formalizes a mutually exclusive 13-category primary intent taxonomy, conservative text preprocessing preserving technical terminology, and reproducible stratified train/dev/test splits.

> **Important Provenance Notice**: This initial seed dataset consists of curated `synthetic_seed` records designed to validate data pipelines and train initial supervised baselines. It does **not** represent production user queries, nor should it be described as human-reviewed ground truth.

---

## 2. Directory Layout

```text
data/query_intent/
├── README.md                              # This specification and usage guide
├── manifest.json                          # Dataset manifest, class counts, and split metadata
├── taxonomy.json                          # Exported machine-readable taxonomy registry
├── raw/
│   └── query_intents.jsonl                # 455 raw seed query records (35 per category)
├── processed/
│   └── query_intents_processed.jsonl      # Sanitized and normalized records with split tags
├── splits/
│   ├── train.jsonl                        # 312 training records (24 per category, ~68.6%)
│   ├── dev.jsonl                          # 65 development records (5 per category, ~14.3%)
│   └── test.jsonl                         # 78 held-out test records (6 per category, ~17.1%)
├── schemas/
│   └── query_intent.schema.json           # JSON Schema draft 2020-12 definition
└── annotation/
    ├── annotation_guidelines.md           # Definitive annotator rules & multi-intent precedence
    └── review_template.jsonl              # Template for human review & adjudication
```

---

## 3. Taxonomy Categories (Version 1.0.0)

| Intent ID | Display Name | Category Purpose | Count (Train/Dev/Test) |
|---|---|---|---|
| `factual_lookup` | Factual Lookup | Concrete facts, numbers, dates, author names, reported values. | 35 (24 / 5 / 6) |
| `definition` | Definition | Meaning, expansion, or terminological clarification of a concept or acronym. | 35 (24 / 5 / 6) |
| `explanation` | Explanation | Mechanistic walkthroughs answering how or why something functions. | 35 (24 / 5 / 6) |
| `comparison` | Comparison | Objective contrast between two or more algorithms, methods, or papers. | 35 (24 / 5 / 6) |
| `summarization` | Summarization | Broad condensation of documents, chapters, or collections. | 35 (24 / 5 / 6) |
| `procedural_guidance` | Procedural Guidance | Step-by-step instructions, implementation recipes, or configuration guides. | 35 (24 / 5 / 6) |
| `analytical_reasoning` | Analytical Reasoning | Evaluation of results, inference, deduction, or critique of findings. | 35 (24 / 5 / 6) |
| `information_extraction` | Information Extraction | Compiling and enumerating structured lists of entities, datasets, or metrics. | 35 (24 / 5 / 6) |
| `source_evidence` | Source Evidence | Explicit requests for citations, page numbers, quotations, or text location. | 35 (24 / 5 / 6) |
| `recommendation` | Recommendation | Advice or selection guidance among alternatives based on evidence. | 35 (24 / 5 / 6) |
| `general_conversation` | General Conversation | Greetings, thanks, pleasantries, or meta-assistant conversation. | 35 (24 / 5 / 6) |
| `unsupported_action` | Unsupported Action | Operational or external actions beyond Knovera's software boundary. | 35 (24 / 5 / 6) |
| `ambiguous` | Ambiguous | Fragmented or context-deprived queries lacking discernible intent. | 35 (24 / 5 / 6) |

---

## 4. Multi-Intent Disambiguation Precedence

When a query contains overlapping task cues, annotators assign the **single primary intent** following this strict precedence hierarchy:

$$\text{source\_evidence} \succ \text{comparison} \succ \text{summarization} \succ \text{recommendation} \succ \text{information\_extraction} \succ \text{procedural\_guidance} \succ \text{analytical\_reasoning} \succ \text{definition} \succ \text{explanation} \succ \text{factual\_lookup}$$

---

## 5. Text Preprocessing Specification (Version 1.0.0)

Executed by `backend.app.ml.query_intent.preprocessing.QueryPreprocessor`:

1. **Input Validation**: Rejects `None`, non-string, or whitespace-only inputs.
2. **Length Truncation**: Configurable `max_length = 512` characters; records `was_truncated=True` if exceeded.
3. **Sensitive Data Redaction**: Automatic redaction of emails (`[EMAIL]`), phone numbers (`[PHONE]`), API keys (`[API_KEY]`), and password patterns (`[TOKEN]`).
4. **Unicode Normalization**: NFKC normalization, removal of invisible control characters (`[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]`), zero-width formatting markers (`[\u200b\u200c\u200d\u200e\u200f\ufeff]`), and typographic quote normalization.
5. **Whitespace Normalization**: Collapses repeated whitespace, newlines, and tabs into a single space.
6. **Technical Terminology Retention**: Preserves internal symbols of programming languages and technical tokens (e.g. `C++`, `C#`, `TCP/IP`, `BM25`, `TF-IDF`, `K-Means`, `GPT-4`, `PostgreSQL`, `FastAPI`).
7. **Stopword Policy**: Intent words (`what`, `why`, `how`, `compare`, `explain`, `summarize`) are strictly retained.

---

## 6. Reproducing Dataset Generation & Preprocessing

Execute the pipeline using PowerShell:

```powershell
# 1. Generate Raw Seed Dataset
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe backend\scripts\generate_raw_query_intent_dataset.py

# 2. Preprocess, Validate, and Split
.\.venv\Scripts\python.exe backend\scripts\prepare_query_intent_dataset.py --seed 42
```

---

## 7. Known Limitations & Roadmap

- **Synthetic Origin**: All 455 current records are synthetic seeds for pipeline and baseline verification. Real user feedback under informed consent will be integrated during Phase 11.
- **English Focus**: The initial seed dataset is in English; multilingual evaluation will follow in subsequent iterations.
- **Model Training**: Classifier training (TF-IDF + LinearSVC / Logistic Regression) is scoped for C5.4–C5.7 and is intentionally not included in this dataset foundation phase.
