# Knovera — Product Requirements Document (PRD)

| Field | Value |
|---|---|
| Product | **Knovera** |
| Tagline | **Turn Information into Intelligence.** |
| Version | 1.0 |
| Status | Baseline specification for implementation |
| Last updated | 5 November 2026 |
| Platform | Responsive web application |
| Audience | Students and researchers |

> **Purpose:** Define what Knovera must do and why. This is the product-scope authority. Implementation agents must not invent features, change priorities, or reinterpret deferred capabilities without an approved change to this document.

---

## 1. Product overview

Knovera is an AI-powered Knowledge Intelligence Platform that turns a user's collection of learning and research documents into a searchable, connected, evidence-traceable workspace.

Users upload documents, ask questions across multiple sources, inspect cited evidence, discover topics and concept relationships, compare research papers, and convert source material into learning resources. Quiz interactions can later inform concept-level mastery estimates and revision recommendations.

Knovera is not a general-purpose chatbot, a replacement for academic databases, or a system that establishes scientific truth. Answers must be grounded in documents available to the current user and workspace. Its research-gap feature identifies **coverage gaps within the user's uploaded corpus**, not proven gaps in all published research.

### 1.1 Product statement

For students and researchers who work with multiple documents, Knovera provides one evidence-linked environment to understand, organise, compare, and learn from those documents. Unlike a basic document chatbot, Knovera combines retrieval, topic discovery, knowledge relationships, research comparison, and adaptive study analytics.

### 1.2 Core value proposition

**Move from finding information to understanding how information connects.**

1. **Document intelligence:** extract, index, search, and cite information across uploaded documents.
2. **Knowledge intelligence:** discover topics, concepts, and evidence-backed relationships.
3. **Research intelligence:** compare objectives, methods, datasets, and findings across papers.
4. **Adaptive learning:** turn source material into study resources and use quiz history to recommend what to revisit.

---

## 2. Problem statement

Students and researchers commonly work across PDFs, lecture notes, papers, presentations, and text files. Their workflow is fragmented:

- Information is distributed across documents and is difficult to retrieve consistently.
- Keyword search misses semantically related passages; semantic search alone can miss exact technical terms.
- Answers without reliable source references are difficult to verify.
- Comparing methods, findings, and assumptions across papers requires repeated manual reading.
- Notes, quizzes, and flashcards are often created separately from the sources they should represent.
- Learners may know which questions they answered incorrectly but not which underlying concepts need more practice.
- Users lack an inspectable view of how concepts connect across a private document collection.

Knovera addresses these problems through one source-aware workspace and a measurable ML pipeline.

---

## 3. Target users and use cases

### 3.1 Primary personas

| Persona | Needs | Typical workflow |
|---|---|---|
| Student | Understand course material, revise efficiently, practise exam-style questions, identify weak concepts | Upload lecture PDFs/slides → ask questions → generate revision notes and quizzes → review weak concepts |
| Researcher | Understand and compare papers, trace claims to evidence, organise themes and methods | Upload papers → compare objectives/methods/results → inspect citations and concept graph → identify under-covered themes in the collection |

### 3.2 Secondary users

- Independent learners with a personal document library.
- Academic groups in a future collaborative release. Collaboration is not part of the first release.

### 3.3 Core use cases

1. Ask a question and receive an answer supported by passages from multiple uploaded documents.
2. Open a citation and inspect the exact source document and page/slide/section.
3. Compare documents on objectives, methods, datasets, results, or limitations.
4. Discover recurring topics across a workspace.
5. Explore concepts and evidence-backed relationships in a knowledge graph.
6. Generate revision notes, MCQs, fill-in-the-blanks, true/false questions, and flashcards.
7. Complete quizzes and see which concepts appear strong or weak over time.
8. Receive revision recommendations based on observed quiz performance and a probabilistic mastery model.

---

## 4. Product goals and non-goals

### 4.1 Goals

- Make multi-document knowledge retrieval practical and verifiable.
- Preserve document, page, and chunk provenance through ingestion, retrieval, and answer generation.
- Combine semantic and lexical retrieval.
- Provide inspectable topic and concept relationships.
- Convert source documents into useful learning and research workflows.
- Include genuine, measurable ML components beyond calls to a generative model.
- Keep the platform modular and provider-independent.
- Provide a responsive web application with workspace-level data isolation.

### 4.2 Non-goals

- Training a foundation language model from scratch.
- Replacing Google Scholar, Semantic Scholar, PubMed, arXiv, or institutional library catalogues.
- Claiming an uploaded-corpus comparison proves novelty or identifies all literature gaps.
- Generating citations to sources that were not retrieved and verified by the backend.
- Guaranteeing every generated answer, summary, or question is correct.
- Building a social network, public publishing platform, or collaborative organisation suite in the first release.
- Building native Android/iOS applications in the first release.
- Generating or transcribing audio/video in the first release.

---

## 5. Scope and release definition

“MVP” means a usable first release, not every advanced capability in the long-term vision.

### 5.1 Core MVP — Knowledge Workbench

The first usable MVP must provide:

- Account registration, login, logout, and authenticated sessions.
- Personal workspaces and workspace-level isolation.
- Upload and processing of PDF, DOCX, PPTX, and TXT documents.
- Clear processing states and actionable processing errors.
- Multi-document question answering within a workspace.
- Page-level or best-available source-location citations.
- Conversation history.
- Basic document search and management.
- Safe document deletion, including derived chunks and vector records.

The core MVP is not complete if a response can display a citation that does not resolve to an authorised, stored source chunk.

### 5.2 Capability expansion

After the core MVP is stable, add:

- Hybrid BM25 + vector retrieval with Reciprocal Rank Fusion (RRF) and Cross-Encoder reranking.
- SVM intent classification and intent-aware routing.
- K-Means topic discovery and an interactive topic explorer.
- An evidence-backed knowledge graph.
- Source-linked revision notes, quizzes, and flashcards.
- Quiz analytics and Bayesian Knowledge Tracing (BKT).
- Research-paper comparison and NLI-based evidence validation.
- Corpus coverage-gap analysis.

### 5.3 Priorities

| Priority | Meaning |
|---|---|
| P0 — Required | Necessary for the first usable MVP or data/security integrity |
| P1 — Important | Differentiated capability; implement after core flows are stable |
| P2 — Later | Valuable enhancement, not required to validate the core product |

| Feature | Priority | Notes |
|---|---:|---|
| Accounts, sessions, workspaces | P0 | Personal workspace model; no collaboration |
| PDF/DOCX/PPTX/TXT ingestion | P0 | Text-based files; scanned OCR deferred |
| Processing status and retry | P0 | Never silently fail ingestion |
| Multi-document RAG chat | P0 | Workspace-scoped retrieval |
| Page/source-location citations and source viewer | P0 | Server-validated citation IDs |
| Conversation history | P0 | Stored per workspace/user |
| Vector retrieval | P0 | Baseline semantic retrieval |
| BM25 + RRF + Cross-Encoder | P1 | Evaluated against baseline |
| SVM intent classifier | P1 | Trained/evaluated on labelled data |
| K-Means topic discovery | P1 | Cluster quality must be evaluated |
| Knowledge graph | P1 | Relationships link to evidence chunks |
| Revision notes and question generation | P1 | Generated from selected sources |
| Quiz history and explanations | P1 | Source-linked feedback |
| BKT mastery estimates | P1 | Probabilistic estimates, not fixed ability labels |
| Paper comparison | P1 | Only compare information present in sources |
| NLI evidence validator | P1 | Validation signal, not a truth oracle |
| Corpus coverage-gap analysis | P1 | Within-library analysis only |
| PDF/Markdown/CSV exports | P2 | After core flows |
| Collaboration/shared workspaces | P2 | Requires explicit membership/permissions |
| OCR for scanned PDFs | P2 | Optional pipeline with quality reporting |
| Public web/academic search | P2 | Separate source acquisition/licensing design |
| Native mobile application | P2 | Web-first release |

---

## 6. Functional requirements

Preserve these IDs in tests or traceability notes.

### 6.1 Identity and workspace management

- **FR-001:** A visitor can register with an email address and password.
- **FR-002:** A registered user can log in and log out.
- **FR-003:** Protected routes and API endpoints require a valid authenticated session.
- **FR-004:** A user can create, rename, list, and delete personal workspaces.
- **FR-005:** A user can access only workspaces they own.
- **FR-006:** Workspace creation must not expose the workspace to another user.
- **FR-007:** The app provides a clear empty state when a user has no workspaces.

### 6.2 Document management and ingestion

- **FR-010:** A user can upload PDF, DOCX, PPTX, and TXT files to a selected workspace.
- **FR-011:** The server validates extension, MIME type, file signature where practical, size, and filename handling.
- **FR-012:** Original files are stored under generated storage keys; user filenames are display metadata only.
- **FR-013:** A document has status `queued`, `extracting`, `chunking`, `indexing`, `ready`, or `failed`.
- **FR-014:** The user can inspect processing status and a safe error summary.
- **FR-015:** Failed processing can be retried without duplicate chunks or vectors.
- **FR-016:** The system preserves document and page/slide provenance.
- **FR-017:** Deletion invalidates chunks, embeddings, search indexes, graph links, and cached derived outputs.
- **FR-018:** The user can list and search documents in a workspace.

### 6.3 Research chat and retrieval

- **FR-020:** A user can create a conversation in a workspace.
- **FR-021:** A user can ask against all ready documents or a selected subset.
- **FR-022:** Retrieval is constrained to the authenticated user's workspace and selected document scope.
- **FR-023:** Answers are generated from retrieved context and state when evidence is insufficient.
- **FR-024:** Each citation references a stored chunk and original document location.
- **FR-025:** The backend validates each citation ID against the retrieved authorised chunk set.
- **FR-026:** A user can open a citation to inspect its source passage and location.
- **FR-027:** Conversation history preserves user messages, assistant answers, and citation references.
- **FR-028:** The system must not fabricate a page, document title, quote, or citation.
- **FR-029:** When evidence is inadequate, the system must not present an unsupported answer as fact.

### 6.4 Hybrid retrieval and query intelligence

- **FR-030:** Semantic vector retrieval is supported.
- **FR-031:** Lexical BM25 retrieval is supported.
- **FR-032:** Ranked results are combined with RRF or a documented equivalent.
- **FR-033:** A Cross-Encoder can rerank the hybrid candidate set.
- **FR-034:** Retrieval components are independently switchable and benchmarkable.
- **FR-035:** Intent classes include `explain`, `compare`, `summarize`, `quiz`, `fact_lookup`, `research`, and `gap_analysis`.
- **FR-036:** Low-confidence/unsupported intent predictions fall back to general retrieval.

### 6.5 Topic and knowledge graph

- **FR-040:** Chunk embeddings can be clustered into candidate topics using K-Means.
- **FR-041:** Algorithm/model version and cluster configuration are recorded.
- **FR-042:** Topic labels are descriptions, not ground truth; members are inspectable.
- **FR-043:** Concepts and graph relationships link to one or more evidence chunks.
- **FR-044:** Users can explore nodes/edges and open supporting sources.
- **FR-045:** Extracted/inferred relationships are distinguished from manually verified facts where provenance exists.

### 6.6 Study studio and adaptive learning

- **FR-050:** Users can generate revision notes from selected documents/topics.
- **FR-051:** Users can generate MCQs, fill-in-the-blanks, true/false questions, and flashcards.
- **FR-052:** Generated questions include answers and source-linked explanations.
- **FR-053:** Users can take and submit quizzes.
- **FR-054:** Quiz attempts are stored with question, concept, source, timestamp, and correctness data.
- **FR-055:** Concept mastery can be estimated with BKT after enough observations exist.
- **FR-056:** Recommendations are explainable and based on recorded performance.
- **FR-057:** Mastery is labelled as an estimate and limited-data conditions are communicated.

### 6.7 Research intelligence and evidence validation

- **FR-060:** Users can select multiple documents and request a comparison.
- **FR-061:** Comparison fields can include objective, methodology, dataset, evaluation, findings, and stated limitations.
- **FR-062:** Missing fields are represented as “not stated in the selected sources,” not guessed.
- **FR-063:** NLI checks can label claim/evidence pairs entailment, contradiction, or neutral.
- **FR-064:** NLI results are validation signals, not replacements for source inspection.
- **FR-065:** Coverage analysis reports under-represented/disconnected topics in the selected corpus.
- **FR-066:** Coverage-gap output explicitly states that it is not a claim about all published research.

---

## 7. User stories and acceptance criteria

### Student stories

**US-001 — Upload course material**  
As a student, I want to upload lecture PDFs and slides to a workspace so I can ask questions across the course material.

Acceptance:
- Supported formats are accepted; unsupported formats receive a clear explanation.
- Processing status is visible.
- Ready documents can be selected for chat.
- Failed documents show a safe reason and retry action.

**US-002 — Verify an answer**  
As a student, I want factual answers to include document and page references so I can verify them before revision.

Acceptance:
- Each citation opens the correct source location.
- The citation belongs to the current workspace.
- Lack of supporting evidence is communicated.

**US-003 — Practise a topic**  
As a student, I want to generate and attempt questions from selected material so I can test understanding.

Acceptance:
- The quiz uses selected source scope.
- Answers and explanations appear after submission.
- Explanations link to sources when available.
- The attempt is recorded once, with duplicate-submit protection.

### Researcher stories

**US-004 — Compare papers**  
As a researcher, I want to compare papers by method, dataset, and findings.

Acceptance:
- Each value has supporting references or is marked not stated.
- Similar labels are not assumed to mean equivalent methods.
- Contradictory statements remain visible.

**US-005 — Explore concepts**  
As a researcher, I want to see relationships between concepts and open their evidence.

Acceptance:
- Nodes and edges are traceable to evidence chunks.
- Unsupported edges are not presented as established facts.
- The graph is filterable by workspace/document scope.

**US-006 — Inspect corpus coverage**  
As a researcher, I want to see which topics have little coverage in my uploaded collection.

Acceptance:
- The report defines its corpus scope.
- Low coverage is described only as a property of that corpus.
- The report does not claim global novelty or a literature-wide research gap.

---

## 8. Non-functional requirements

### 8.1 Performance targets

Targets require measurement under a documented environment; they are not universal guarantees.

| Measure | Initial target |
|---|---|
| Standard RAG response | 5–10 seconds for a warmed, moderate workspace, excluding provider/network outliers |
| API health response | Under 500 ms in local development |
| Frontend initial route | Promptly usable on typical broadband |
| Document status | Updated after each ingestion stage; polling interval configurable |
| Retrieval | Candidate count and reranking depth configurable and benchmarked |

Performance reports state hardware, model, corpus size, and provider/network conditions.

### 8.2 Reliability

- Ingestion is idempotent or detects duplicate work.
- A failed task never leaves a document falsely marked ready.
- Background tasks have bounded retries and visible failure status.
- PostgreSQL and vector-index state can be reconciled.
- Document deletion invalidates derived data.

### 8.3 Security and privacy

- Workspace-owned records require owner checks in the application layer and PostgreSQL RLS as defence in depth.
- Passwords use a modern hash such as Argon2id, never plaintext/reversible encryption.
- Refresh tokens are stored hashed server-side.
- Secrets are environment-based and never committed.
- Uploaded documents are untrusted input; embedded prompt-injection text cannot override system instructions.
- Logs exclude passwords, tokens, full document text, and unnecessary personal information.
- The UI discloses when selected text is sent to an external LLM provider.
- No user can retrieve another user's chunks through vector search, citations, caches, or graph APIs.

### 8.4 Accessibility and usability

- Keyboard access for core flows and visible focus indicators.
- Semantic labels and accessible form errors.
- Sufficient contrast in both themes.
- Responsive desktop/tablet/mobile-browser layouts.
- Loading, empty, error, and success states for primary asynchronous actions.

### 8.5 Maintainability

- Modular monolith with clear API/service/repository/ingestion/RAG/ML/UI boundaries.
- API schemas and migrations are version-controlled.
- Models and providers are configurable.
- Critical business rules, access controls, citations, and deletion are tested.
- Evaluation data, model versions, and metrics are tracked separately from application code.

---

## 9. Product rules and guardrails

1. **Evidence before confidence:** an answer must not sound more certain than its evidence.
2. **Citations are backend-owned:** the model may propose markers; the backend decides which stored chunk IDs are valid and authorised.
3. **No fabricated source metadata:** page, slide, title, and quote values come from ingestion metadata.
4. **Corpus-scoped research claims:** coverage analysis is limited to selected documents.
5. **ML claims require evaluation:** every model has an evaluation dataset and baseline.
6. **NLI is not fact verification:** entailment/contradiction/neutral are model predictions.
7. **BKT is probabilistic:** mastery requires relevant response sequences and is not a fixed ability label.
8. **Provider neutrality:** business logic does not depend on one vendor's proprietary response format.
9. **Documents are data, not instructions:** retrieved content cannot change system policies or authorisation.

---

## 10. Success metrics

These are hypotheses to validate on held-out, documented test sets, not achieved metrics.

| Area | Metric | Initial target / criterion |
|---|---|---|
| Core RAG | Retrieval Recall@5 | Target ≥ 0.80 on labelled in-domain evaluation |
| Grounding | Citation support rate | Target ≥ 0.90 on human-reviewed sample |
| Retrieval ranking | nDCG@10 | Hybrid + reranker should outperform vector-only baseline |
| Intent routing | Macro F1 | Target ≥ 0.85 on held-out labelled set |
| Topic discovery | Silhouette + human coherence | Report both; 0.40 is aspirational only where data permits |
| BKT | Brier score / log loss | Beat documented historical-accuracy baseline |
| NLI | Macro F1 | Target ≥ 0.80 on domain-reviewed test set; report each class |
| Product usability | Task completion | ≥80% in a small moderated upload → cited-answer test |
| Reliability | Cross-workspace leakage | Zero tolerated in automated tests |
| Deletion | Derived-data cleanup | No retrievable chunks/vectors/graph edges after completed deletion |

Do not present targets as achieved until an evaluation report proves them.

---

## 11. Analytics events

Collect only operational events needed to understand reliability and usage. Avoid logging document content.

Suggested events: `account_registered`, `workspace_created`, `document_upload_started`, `document_processing_completed`, `document_processing_failed`, `chat_query_submitted`, `chat_answer_completed`, `citation_opened`, `quiz_generated`, `quiz_submitted`, `recommendation_opened`, `document_deleted`.

Events may include safe identifiers, event time, status, and latency. Do not include raw prompts or document passages by default.

---

## 12. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Poor extraction from complex PDFs | Missing/misleading answers | Preserve page metadata, report extraction quality, test files, defer OCR explicitly |
| Hallucinated answers/citations | Loss of trust | Grounding, backend citation validation, abstention, human-reviewed evaluation |
| Cross-user vector leakage | Critical privacy failure | Workspace filters, ownership checks, RLS, leakage tests |
| Provider outage/quota limits | Chat unavailable | Provider adapter, bounded retries, clear error, explicit fallback |
| Unstable topic clusters | Confusing explorer | Minimum data thresholds, quality metrics, transparent labels, no-result state |
| Noisy graph relationships | False connections | Confidence thresholds, evidence references, relation validation |
| Weak BKT data | Misleading mastery | Require sufficient attempts, baseline comparison, uncertainty display |
| Scope growth | Delayed usable release | Enforce MVP boundaries and phase gates |

---

## 13. Core MVP release acceptance checklist

- [ ] User can register, log in, and log out.
- [ ] User can create and manage a personal workspace.
- [ ] User can upload supported files and see processing status.
- [ ] Ready documents can be queried together.
- [ ] Chat responses show verifiable source citations.
- [ ] Citation opening displays the correct source passage.
- [ ] Insufficient evidence is handled explicitly.
- [ ] No cross-workspace data can be retrieved.
- [ ] Document deletion removes or invalidates derived data.
- [ ] Critical backend and frontend tests pass.
- [ ] Security and operational limitations are documented.

---

## 14. Change control

Changes to file types, authentication, storage, providers, workflows, ownership, or out-of-scope items must be recorded and reconciled with the TRD, app flow, schema, design brief, and implementation plan. If documents disagree, do not guess; report the conflict and follow the newest explicitly approved decision.
