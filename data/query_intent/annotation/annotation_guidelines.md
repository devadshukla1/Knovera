# Knovera Query Intent Annotation Guidelines

**Version:** 1.0.0  
**Phase:** 5 — Query Intelligence & Intent Classification (C5.1 / C5.2)  
**Authoritative Reference:** `backend/app/ml/query_intent/taxonomy.py`

---

## 1. Overview & Purpose

Knovera is an AI-powered Knowledge Intelligence Platform for students and researchers. In order to route user queries to the optimal retrieval and synthesis strategies (e.g. dense semantic search, BM25 keyword search, hybrid fusion, citation tracking, or multi-hop reasoning), Knovera classifies each query into **exactly one primary intent**.

These guidelines instruct annotators and reviewers on how to label queries consistently, resolve ambiguous multi-intent cases, and assign auxiliary query attributes.

---

## 2. Intent Taxonomy (Version 1.0.0)

Knovera recognizes 13 mutually exclusive primary intent categories.

| Intent ID | Display Name | Core Purpose |
|---|---|---|
| `factual_lookup` | Factual Lookup | Retrieve a discrete fact, date, value, name, or isolated data point. |
| `definition` | Definition | Clarify the terminological definition or expansion of a concept or acronym. |
| `explanation` | Explanation | Understand how or why a concept, algorithm, or mechanism functions. |
| `comparison` | Comparison | Contrast two or more entities, algorithms, papers, or methodologies. |
| `summarization` | Summarization | Condense a document, chapter, section, or collection into a synthesized overview. |
| `procedural_guidance` | Procedural Guidance | Provide actionable steps, configuration instructions, or implementation recipes. |
| `analytical_reasoning` | Analytical Reasoning | Evaluate results, deduce causes, critique methodology, or draw inferences. |
| `information_extraction` | Information Extraction | Extract and list structured entities, parameters, datasets, or metrics. |
| `source_evidence` | Source Evidence | Locate citations, quotations, verifiable references, or exact page numbers. |
| `recommendation` | Recommendation | Prescribe the best method, model, or paper based on document evidence. |
| `general_conversation` | General Conversation | Social pleasantries, greetings, farewells, or acknowledgements. |
| `unsupported_action` | Unsupported Action | Requests for external actions beyond Knovera's software boundary. |
| `ambiguous` | Ambiguous | Query is too fragmented or context-deprived to determine a clear intent. |

---

## 3. Detailed Category Rules & Positive/Borderline Examples

### 3.1 `factual_lookup`
- **Inclusion**: Single, bounded facts, numbers, dates, author names, or reported metrics.
- **Exclusion**: Long explanations of *why* (use `explanation`), lists of multiple entities (use `information_extraction`), or explicit page requests (use `source_evidence`).
- **Positive Examples**:
  - *"When was the paper published?"*
  - *"What was the reported test accuracy on ImageNet?"*
  - *"Which optimization algorithm did the authors use?"*
- **Borderline Cases**:
  - *"What are all the hyperparameters used in table 3?"* $\to$ `information_extraction` (requests extraction of a structured set).
  - *"Why did the accuracy drop on dataset B?"* $\to$ `analytical_reasoning` (causal inquiry).

### 3.2 `definition`
- **Inclusion**: "What is X?", "Define X", "What does X stand for?".
- **Exclusion**: Deep mechanistic breakdowns of how X operates under the hood (use `explanation`).
- **Positive Examples**:
  - *"What is BM25?"*
  - *"Define reciprocal rank fusion."*
  - *"What does RAG stand for?"*
- **Borderline Cases**:
  - *"How does BM25 calculate term saturation?"* $\to$ `explanation` (mechanistic mathematical breakdown).
  - *"What is the difference between BM25 and TF-IDF?"* $\to$ `comparison` (contrast between two concepts).

### 3.3 `explanation`
- **Inclusion**: "How does X work?", "Why does Y occur?", conceptual and mechanistic walkthroughs.
- **Exclusion**: Actionable step-by-step user implementation commands (use `procedural_guidance`), comparative analysis (use `comparison`).
- **Positive Examples**:
  - *"How does gradient descent update model weights?"*
  - *"Why does overfitting occur in high-capacity models?"*
  - *"Explain how the self-attention mechanism works in transformers."*
- **Borderline Cases**:
  - *"How do I implement gradient descent in PyTorch?"* $\to$ `procedural_guidance` (actionable instructions for user).
  - *"Explain the difference between Adam and SGD."* $\to$ `comparison` (comparative contrast overrides 'explain').

### 3.4 `comparison`
- **Inclusion**: Contrasting two or more named concepts, methods, documents, or systems.
- **Exclusion**: Requests for a decision recommendation without objective trade-off evaluation (use `recommendation`).
- **Positive Examples**:
  - *"Compare TCP and UDP protocols."*
  - *"What is the difference between BERT and GPT?"*
  - *"Contrast the experimental findings of paper A and paper B."*
- **Borderline Cases**:
  - *"Which is better for my real-time app, TCP or UDP?"* $\to$ `recommendation` (user is asking for a decision choice).

### 3.5 `summarization`
- **Inclusion**: Broad synthesis, abstracting an entire paper, chapter, or workspace collection.
- **Exclusion**: Targeted factual questions about the summary (use `factual_lookup`).
- **Positive Examples**:
  - *"Summarize this research paper."*
  - *"Give me an executive summary of chapter 4."*
  - *"What are the overall takeaways from the uploaded documents?"*
- **Borderline Cases**:
  - *"List the three main contributions."* $\to$ `information_extraction` (requests extraction of specific enumerated items).

### 3.6 `procedural_guidance`
- **Inclusion**: "How do I...", "Steps to...", configuration instructions, command-line recipes.
- **Exclusion**: Requests for the application to execute external actions (use `unsupported_action`).
- **Positive Examples**:
  - *"How do I configure PostgreSQL connection pooling in FastAPI?"*
  - *"What are the step-by-step instructions to train the model?"*
  - *"How can I reproduce the benchmark experiment locally?"*
- **Borderline Cases**:
  - *"Run the benchmark script on your server."* $\to$ `unsupported_action` (external execution request).

### 3.7 `analytical_reasoning`
- **Inclusion**: Deductive reasoning, evaluating experimental results, interpreting statistical data, critique.
- **Exclusion**: Verbatim quote retrieval (use `source_evidence`).
- **Positive Examples**:
  - *"Why did the model fail on the out-of-distribution test set?"*
  - *"What can we infer from the ablation study in section 5?"*
  - *"Critique the authors' methodology regarding statistical significance."*
- **Borderline Cases**:
  - *"Where do the authors discuss the ablation study?"* $\to$ `source_evidence` (requests location, not analysis).

### 3.8 `information_extraction`
- **Inclusion**: Compiling, extracting, and enumerating structured lists of entities, datasets, benchmarks, or parameters.
- **Exclusion**: High-level narrative summaries (use `summarization`).
- **Positive Examples**:
  - *"List all datasets evaluated in the study."*
  - *"Extract all hyperparameter values from the appendix."*
  - *"Find every institution mentioned in the acknowledgements."*
- **Borderline Cases**:
  - *"Which dataset was used in experiment 1?"* $\to$ `factual_lookup` (single isolated fact).

### 3.9 `source_evidence`
- **Inclusion**: Explicit demands for citations, page numbers, paragraph locations, or verbatim quotations.
- **Positive Examples**:
  - *"Where in the document is the 95% accuracy claim located?"*
  - *"Provide the exact page number and quotation for this definition."*
  - *"Show me the source chunk that supports this conclusion."*
- **Borderline Cases**:
  - *"What is the accuracy claim?"* $\to$ `factual_lookup` (asks for the fact, not the location).

### 3.10 `recommendation`
- **Inclusion**: Requests for advice, selection guidance, or prescriptive choice between alternatives.
- **Positive Examples**:
  - *"Which loss function should I use for imbalanced multi-class classification based on this paper?"*
  - *"Recommend the best starting paper for a beginner in quantum computing."*
  - *"Which database architecture is best suited for write-heavy workloads according to the report?"*
- **Borderline Cases**:
  - *"Compare Cross-Entropy and Focal Loss."* $\to$ `comparison` (objective comparison without prescription).

### 3.11 `general_conversation`
- **Inclusion**: Greetings, acknowledgements, thanks, meta-inquiries about Knovera.
- **Positive Examples**:
  - *"Hello!"*
  - *"Thank you for your assistance."*
  - *"What tasks can you help me with?"*
- **Borderline Cases**:
  - *"Hello, what is the learning rate used in the paper?"* $\to$ `factual_lookup` (substantive research question takes precedence).

### 3.12 `unsupported_action`
- **Inclusion**: Demands for external transactions, device control, booking, payment, email dispatch.
- **Positive Examples**:
  - *"Book a hotel room in Boston for tomorrow."*
  - *"Send an email to my advisor."*
  - *"Delete all files from my hard drive."*
- **Borderline Cases**:
  - *"How do I send an email using Python?"* $\to$ `procedural_guidance` (coding recipe, not asking Knovera to dispatch an email).

### 3.13 `ambiguous`
- **Inclusion**: Fragmented phrases lacking referents or context where no reasonable intent can be inferred.
- **Positive Examples**:
  - *"That one."*
  - *"Do it."*
  - *"What about that?"*
- **Borderline Cases**:
  - *"BM25"* $\to$ `definition` (technical concept lookup).

---

## 4. Multi-Intent Disambiguation Precedence

When a user query exhibits multiple intents (e.g. *"Explain the differences between SVM and Logistic Regression and show me the source citation"*), assign the **single primary intent** following this strict precedence hierarchy:

1. `source_evidence` (if citations, page numbers, or quote locations are explicitly requested)
2. `comparison` (if two or more items are explicitly contrasted)
3. `summarization` (if comprehensive synthesis/summary is requested)
4. `recommendation` (if actionable decision/selection advice is requested)
5. `information_extraction` (if structured entity or parameter lists are requested)
6. `procedural_guidance` (if implementation steps or actionable recipes are requested)
7. `analytical_reasoning` (if deductive evaluation or critique is requested)
8. `definition` (if terminological meaning is requested)
9. `explanation` (if how/why mechanism is requested)
10. `factual_lookup` (if a discrete fact is requested)

**Operational Exceptions**:
- `general_conversation`: Only when no substantive research inquiry is present.
- `unsupported_action`: Assigned when the user asks Knovera to perform external operations.
- `ambiguous`: Assigned only when the text is too impoverished to determine intent.

---

## 5. Auxiliary Query Attributes

Annotators may annotate these secondary boolean attributes independently of the primary intent:

1. `requires_conversation_context` (`bool`): True if resolving the query requires anaphoric reference to previous conversational turns (e.g. *"Why did it fail?"*).
2. `requires_multi_source_evidence` (`bool`): True if answering requires synthesizing information across multiple separate documents.
3. `requests_explicit_citations` (`bool`): True if the query explicitly asks for citations, quotes, or page references.
4. `contains_ambiguous_reference` (`bool`): True if pronouns or deictic references are unclear without additional context.

---

## 6. Provenance & Privacy Rules

- **Allowed Source Types**:
  - `synthetic_seed`: Generated synthetic query designed for development and testing.
  - `manually_curated`: Curated by engineering team members for specific edge cases.
  - `human_annotated`: Annotated by human subject-matter experts.
  - `anonymized_opt_in`: Real user query with explicit consent, anonymized and redacted.
- **Annotation Status**:
  - `pending_human_review`: Initial draft or synthetic state.
  - `human_reviewed`: Verified by a qualified reviewer.
  - `adjudicated`: Resolved after cross-annotator disagreement.
- **Privacy Safeguards**:
  - Never include real personal names, emails, phone numbers, API keys, passwords, or confidential proprietary snippets.
  - All sensitive tokens must be redacted to `[EMAIL]`, `[PHONE]`, `[API_KEY]`, or `[TOKEN]`.
