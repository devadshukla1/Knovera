# Knovera — Technical Requirements Document (TRD)

| Field | Value |
|---|---|
| Product | **Knovera** |
| Version | 1.0 |
| Status | Baseline technical decision record |
| Last updated | 5 November 2026 |
| Governing product scope | [prd.md](prd.md) |

> **Purpose:** Define how Knovera is to be built. This is the technical source of truth for languages, frameworks, services, boundaries, integrations, security, deployment, and repository organisation.

---

## 1. Architecture decisions at a glance

| Concern | Decision |
|---|---|
| Product shape | Responsive web application |
| Architecture | Modular monolith; separate worker process where needed |
| Frontend | React + TypeScript + Vite |
| Styling | Tailwind CSS + shadcn/ui (Radix UI primitives) |
| Routing | React Router |
| Server-state cache | TanStack Query |
| Client state | React Context for small global state; Zustand only if a real need emerges |
| Forms | React Hook Form + Zod |
| Backend | Python 3.12.x + FastAPI |
| API schemas | Pydantic v2 |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| PostgreSQL driver | Psycopg 3 |
| Relational database | PostgreSQL |
| Vector store | ChromaDB persistent server via HTTP client |
| Embeddings | Sentence Transformers, configurable local model |
| Lexical retrieval | BM25 using a maintained Python implementation such as `rank-bm25` or an evaluated equivalent |
| Rank fusion | Reciprocal Rank Fusion (RRF) |
| Reranking | Hugging Face Cross-Encoder through Sentence Transformers |
| Query intent ML | TF-IDF + LinearSVC; Logistic Regression baseline |
| Topic discovery | Sentence embeddings + scikit-learn K-Means; PCA optional |
| Knowledge graph | NetworkX operations; PostgreSQL persistence |
| Graph UI | Cytoscape.js |
| Learning model | Bayesian Knowledge Tracing implemented with NumPy/SciPy or a small dedicated module |
| NLI | Configurable Hugging Face NLI sequence-classification model |
| File extraction | PyMuPDF, python-docx, python-pptx, standard text decoding |
| Testing | Pytest, HTTPX, Vitest, React Testing Library, Playwright E2E |
| Containers | Docker + Docker Compose |
| Local ports | Vite 5173, FastAPI 8000, PostgreSQL 5432, ChromaDB host 8001 (container port follows pinned image) |
| Initial production target | Ubuntu 24.04 LTS Docker-capable VPS, Docker Compose, Caddy reverse proxy, persistent volumes |

**Do not replace this stack with Next.js, Supabase, Firebase, MongoDB, Pinecone, or microservices unless the owner explicitly approves a change.** The agreed baseline is React + Vite, FastAPI, PostgreSQL, and ChromaDB.

### 1.1 Version policy

- Use Python **3.12.x**. Do not silently use Python 3.13 or 3.14.
- Use stable, mutually compatible frontend/backend package versions at implementation time.
- Pin backend dependencies after compatibility testing; commit `package-lock.json` for the frontend.
- Pin Docker image tags to tested versions; do not use `latest` in production.
- Record model IDs and revisions in configuration/model registry. Do not download large model weights during Phase 0.
- Upgrade dependencies deliberately and run all tests after upgrades.

---

## 2. System architecture

### 2.1 Logical architecture

```mermaid
flowchart TD
    U[Browser User] --> FE[React + TypeScript + Vite]
    FE -->|HTTPS / JSON| API[FastAPI API]
    API --> AUTH[Auth and Workspace Authorization]
    API --> SVC[Application Services]
    SVC --> PG[(PostgreSQL)]
    SVC --> CH[(ChromaDB)]
    SVC --> FS[(Original File Storage)]
    SVC --> WORK[Ingestion Worker]
    WORK --> EX[Document Extractors]
    WORK --> CHUNK[Cleaning and Chunking]
    WORK --> EMB[Embedding Model]
    EMB --> CH
    API --> RET[RAG Orchestrator]
    RET --> BM[BM25 Index]
    RET --> CH
    RET --> RR[Cross-Encoder Reranker]
    RET --> LLM[LLM Provider Adapter]
    RET --> CITE[Citation Validator]
    SVC --> ML[ML Modules]
    ML --> KG[NetworkX Graph Services]
    KG --> PG
```

### 2.2 Runtime boundaries

- **Frontend:** presentation, navigation, UX validation, query state, visualisation. It is not an authorisation boundary.
- **FastAPI API:** authentication, request validation, ownership checks, orchestration, response shaping, safe logging.
- **Application services:** use-case logic independent of HTTP details.
- **Repositories:** controlled persistence via SQLAlchemy and ChromaDB adapters.
- **Ingestion worker:** extraction, chunking, embedding, index updates, retries, cleanup.
- **ML modules:** independently testable algorithms with explicit model/configuration versions.
- **PostgreSQL:** authoritative users, workspaces, document/chunk text, conversations, quiz data, graph data, jobs, and model metadata.
- **ChromaDB:** rebuildable vector index; not the source of ownership metadata.
- **Original file storage:** local persistent storage in development/first deployment, accessed only through a storage adapter.

### 2.3 Architectural style

Use a modular monolith. Modules communicate through explicit Python service/interface boundaries, not imports of other modules' internals. A separate worker process may execute the same application package. Do not introduce Kafka, Kubernetes, Redis, or distributed service discovery unless measured requirements justify them.

---

## 3. Frontend technical requirements

### 3.1 Framework and libraries

- React with TypeScript strict mode.
- Vite for development and production bundling.
- Tailwind CSS for styling/design tokens.
- shadcn/ui based on Radix UI primitives for accessible controls.
- React Router for route definitions and protected route shells.
- TanStack Query for server state, request lifecycle, cache invalidation, and retries.
- React Hook Form + Zod for forms and client-side schema validation.
- Lucide icons for consistent iconography.
- Cytoscape.js for graph visualisation.
- Plotly only if richer charts justify its bundle size; choose a lighter charting option if sufficient.
- Fetch API as the default HTTP client. Axios is acceptable only if it provides a concrete shared-interceptor benefit; do not install both without reason.

### 3.2 Frontend structure

```text
frontend/
├── public/
├── src/
│   ├── app/                    # App.tsx, router.tsx, providers.tsx
│   ├── assets/
│   ├── components/
│   │   ├── ui/                 # shadcn/ui primitives
│   │   ├── layout/
│   │   ├── feedback/
│   │   └── shared/
│   ├── features/
│   │   ├── auth/
│   │   ├── workspaces/
│   │   ├── documents/
│   │   ├── chat/
│   │   ├── knowledge/
│   │   ├── study/
│   │   ├── research/
│   │   └── learning/
│   ├── hooks/
│   ├── lib/
│   ├── services/
│   ├── store/
│   ├── styles/
│   ├── types/
│   └── main.tsx
├── .env.example
├── package.json
└── package-lock.json
```

Feature folders own components, hooks, API functions, and types. Shared UI belongs in `components/ui` or `components/shared`.

### 3.3 Frontend environment

`frontend/.env.example`:

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Only public, browser-safe values may use `VITE_`. Never expose database credentials, LLM keys, signing secrets, or server settings through Vite variables.

### 3.4 Frontend rules

- All protected app pages require authenticated session state.
- Server data is fetched through a central typed API layer.
- Show loading, empty, success, and actionable error states.
- Hidden UI controls are not access control; backend authorization is mandatory.
- Use route-level code splitting for large areas where beneficial.
- Follow tokens in [design_brief.md](design_brief.md).

---

## 4. Backend technical requirements

### 4.1 Runtime and core packages

- Python 3.12.x, FastAPI, Uvicorn.
- Pydantic v2 and `pydantic-settings`.
- SQLAlchemy 2.x, Psycopg 3, Alembic.
- ChromaDB client.
- PyMuPDF, python-docx, python-pptx.
- Sentence Transformers and scikit-learn added in their relevant phases, not Phase 0.
- Pytest and HTTPX.
- `pwdlib` with Argon2 support or another maintained Argon2 implementation.
- A maintained JWT library; use short-lived access tokens and rotating opaque refresh tokens stored hashed in PostgreSQL.

### 4.2 Backend structure

```text
backend/
├── app/
│   ├── main.py
│   ├── api/v1/                # auth, workspaces, documents, chat, knowledge, study, research, learning
│   ├── core/                  # config, security, logging, exceptions
│   ├── db/                    # session, base, migrations
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   ├── storage/
│   ├── ingestion/
│   ├── rag/
│   ├── ml/
│   │   ├── intent_classifier/
│   │   ├── topic_discovery/
│   │   ├── retrieval_reranker/
│   │   ├── knowledge_tracing/
│   │   └── nli_validator/
│   ├── knowledge_graph/
│   ├── study/
│   ├── research/
│   └── workers/
├── tests/
├── requirements.txt
└── alembic.ini
```

### 4.3 API rules

- Prefix application routes with `/api/v1`.
- Use Pydantic request/response models; do not return raw ORM objects.
- Consistent error shape: `code`, `message`, optional `details`, `request_id`.
- Use HTTP status codes correctly: 201 create, 202 background accepted, 400 bad request, 401 unauthenticated, 403 forbidden, 404 not found, 409 conflict, 422 validation, 429 rate limited, 500/503 server/dependency failure.
- Paginate list endpoints and apply request/upload limits.
- Add request IDs and safe structured logs.
- Do not expose stack traces, file paths, raw DB errors, or secrets in public responses.

---

## 5. Authentication and authorisation

### 5.1 Authentication decision

Use **application-managed email/password authentication** in the MVP. Do not use Supabase Auth, Firebase Auth, Clerk, or social sign-in in this baseline.

- Passwords hashed with Argon2id.
- Short-lived signed access token (initial target: 15 minutes).
- Rotating opaque refresh token (initial target: 30 days, configurable), stored as a cryptographic hash in PostgreSQL.
- Logout revokes the refresh session.
- Refresh-token reuse detection should revoke the affected token family where supported.
- Tokens are transmitted only over HTTPS in production.
- Prefer Secure, HttpOnly, SameSite cookies for refresh-token transport. If cookies are used, implement CSRF protection for state-changing requests. Do not mix cookie and localStorage strategies.
- Rate-limit login and registration; use generic login failure messages.
- Password reset and email verification are deferred until an email-delivery service is selected. Do not expose a fake flow.

### 5.2 Authorisation model

MVP supports **personal workspaces**. Each workspace has one owner. Collaboration is deferred.

Every workspace-owned request must:
1. Identify the user from a verified session.
2. Resolve the requested resource through an owner-constrained query.
3. Set the PostgreSQL transaction-local user context for RLS.
4. Apply workspace filters to ChromaDB queries.
5. Validate citation chunk IDs against the authorised retrieval set before response.

Frontend route guards are UX only. Backend ownership checks are mandatory.

### 5.3 PostgreSQL RLS

Enable and force RLS on user-owned tables. Use a transaction-local setting such as `SET LOCAL app.user_id = '<verified UUID>'` after authentication and before workspace queries. Child policies derive access through `workspaces.owner_user_id`. Use a separate, tightly controlled worker DB role for background operations; never expose it to the browser. Test connection-pool reuse to ensure user context cannot leak across requests.

RLS is defence in depth, not a substitute for application-layer authorization.

---

## 6. Database and storage architecture

### 6.1 PostgreSQL

PostgreSQL is the authoritative system of record for:

- Users and refresh sessions.
- Workspaces and document metadata.
- Extracted chunks and source locations.
- Conversations, messages, citations.
- Ingestion jobs and processing status.
- Topics, concepts, graph edges, and evidence relationships.
- Study questions, quiz sessions, attempts, mastery states, and recommendations.
- Model versions and evaluation metadata.

Use UUID keys, UTC timestamps, foreign keys, check/unique constraints, and JSONB only for genuinely variable structured settings. Keep queryable relational fields typed.

### 6.2 ChromaDB

ChromaDB is the vector index, not the authoritative metadata database.

- Use a persistent ChromaDB server and HTTP client.
- Store stable chunk IDs and embedding vectors.
- Store metadata required for safe filtering: at minimum `workspace_id`, `document_id`, model/version fields.
- Never trust a client-supplied workspace ID; derive scope from the authorised backend request.
- Store chunk text authoritatively in PostgreSQL and hydrate it by returned chunk IDs after vector search. If Chroma stores text for operational reasons, treat it as a rebuildable cache and document duplication.
- Embedding model changes require a versioned collection or re-embedding migration; never mix incompatible dimensions in one collection.
- Test rebuildability from PostgreSQL chunk records.

### 6.3 Original file storage

- Development: local persistent directory outside source-controlled files (`backend/storage/`).
- Use a `StorageService` interface (`backend/app/storage/base.py`) so an S3-compatible object store can be introduced without changing domain services.
- `LocalStorageService` implementation:
  - Generates unique storage keys server-side: `documents/{workspace_id}/{uuid}.{ext}`; never derives paths from uploaded filenames.
  - Enforces path traversal protection using strict `pathlib.Path.resolve().relative_to(root_dir)` checks.
  - Streaming chunked writes (64KB chunks) with on-the-fly SHA-256 calculation.
  - Enforces `MAX_UPLOAD_SIZE_BYTES` (25MB default) during streaming, rejecting oversized files with HTTP 413 and cleaning up immediately.
  - Atomic write strategy: writes to temporary file (`.tmp`) and renames on completion.
  - Automatic error cleanup if streaming or persistence fails.
  - Private filesystem location isolated from static/frontend public directories.

### 6.4 Background processing

Use a PostgreSQL-backed `ingestion_jobs` table and a separate worker process for the initial design. Avoid Redis/Celery/RQ until workload proves the need.

Jobs need status, stage, attempts, next retry time, timestamps, and safe error summary. Workers claim jobs safely (for example, transactional row locking), are idempotent, and use bounded retries. A worker cannot mark a document `ready` until extraction, chunk persistence, vector indexing, and verification succeed.

---

## 7. Document ingestion pipeline

```mermaid
flowchart LR
    A[Upload] --> B[Validate type, size, signature]
    B --> C[Store original file]
    C --> D[Create document + job records]
    D --> E[Extract text and page/slide metadata]
    E --> F[Clean and normalise]
    F --> G[Structure-aware chunking]
    G --> H[Persist chunks and provenance]
    H --> I[Generate embeddings]
    I --> J[Upsert vectors + metadata]
    J --> K[Mark document ready]
```

Supported first-release types: PDF, DOCX, PPTX (implemented in Phase 2 C2.1–C2.5). TXT is pending.

Validation rules:
- Supported formats: PDF (`.pdf`), Word (`.docx`), PowerPoint (`.pptx`).
- Header magic signatures: `%PDF-` for PDF, `PK\x03\x04` ZIP container for DOCX/PPTX.
- 0-byte files rejected with HTTP 400 (`empty_file`).
- Files exceeding `MAX_UPLOAD_SIZE_BYTES` (default 25MB) rejected with HTTP 413 (`file_too_large`).
- Non-matching signatures rejected with HTTP 415 (`invalid_pdf_signature`, `invalid_zip_signature`).

Extraction architecture (C2.3):
- Common unified representation: `ExtractedDocument` composed of ordered `ExtractedBlock`s.
- PDF: PyMuPDF (`PyMuPDFExtractor`) layout-sorted text extraction (`sort=True`) preserving 1-based page numbers in `document_pages`.
- DOCX: `python-docx` (`DOCXExtractor`) preserving heading hierarchy (levels 1–9, `section_path`), paragraphs, and markdown/pipe-formatted tables.
- PPTX: `python-pptx` (`PPTXExtractor`) preserving 1-based `slide_number`, slide titles, reading-ordered shapes, bullet hierarchy, and slide tables.
- Error handling: encrypted documents rejected (`pdf_encrypted`, `docx_encrypted`, `pptx_encrypted`), empty/scanned documents rejected (`no_extractable_text`), corrupted containers rejected (`invalid_pdf`, `invalid_docx`, `invalid_pptx`).
- Safety bounds: `MAX_PDF_PAGES=500`, `MAX_PPTX_SLIDES=500`, `MAX_DOCX_PARAGRAPHS=10000`, `MAX_EXTRACTED_TEXT_CHARS=20,000,000`.

Text Cleaning & Normalisation (C2.4):
- Unified non-destructive normalizer (`TextNormalizer`):
  - Unicode NFC normalisation (`unicodedata.normalize('NFC', ...)`).
  - Normalisation of line endings (`\r\n` and `\r` to `\n`).
  - Removal of NUL and unsafe control characters (`[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]`), retaining `\n`, `\t`.
  - Conservative line-break dehyphenation (`learn-\ning` -> `learning`), preserving legitimate hyphenated prefixes (`self-`, `multi-`, `cross-`), code, and math symbols.
  - Collapse redundant horizontal spaces and vertical blank lines (`\n{3,}` -> `\n\n`).
  - Conservative repeated header/footer detection (`BoilerplateDetector`).
  - Absolute preservation: Accents, Greek letters, math symbols (`∑`, `∫`, `≤`, `≥`, `≠`), currency, code syntax, technical terms, and stop-words (zero stemming/lowercasing).
  - Telemetry: `CleaningMetadata` tracks character counts, control char count, dehyphenation count, and warnings.

Semantic Chunking (C2.5):
- Structure-aware, content-aware semantic chunker (`SemanticChunker`):
  - Target budget: 500 tokens (configurable via `CHUNK_TARGET_TOKENS`).
  - Maximum budget: 700 tokens (configurable via `CHUNK_MAX_TOKENS`).
  - Minimum budget: 80 tokens (configurable via `CHUNK_MIN_TOKENS`).
  - Overlap budget: 75 tokens (configurable via `CHUNK_OVERLAP_TOKENS`).
  - Algorithm version: `semantic-v1`.
- Token counter abstraction (`EstimateTokenCounter`): Fast, reproducible heuristic explicitly labeled `estimate_v1` without heavyweight dependencies.
- Sentence boundary detector (`SentenceBoundaryDetector`): Segments paragraphs at sentence boundaries while preserving abbreviations (`e.g.`, `i.e.`, `et al.`, `Dr.`), decimals (`3.14`), URLs, and math notation.
- Context-preserving overlap (`OverlapManager`): Extracts complete trailing sentences up to overlap budget; resets across distinct major section/slide boundaries.
- Boundary preservation:
  - Tables: Kept intact if within budget; oversized tables split at row boundaries with repeated column headers.
  - PPTX: Chunks strictly bounded by slide; oversized slides split with same `slide_number`.
  - PDF: Page boundaries tracked with `page_start` and `page_end`.
  - DOCX: Preserves heading hierarchy and section context.
- Deterministic chunk identity: UUID5 generated from `(document_id, chunking_version, chunk_index, content_hash)`.
- Source provenance: Each chunk records `source_segments` JSONB array linking chunk spans to exact source blocks, pages/slides, and character offsets.
- Lifecycle State: Successfully chunked documents transition to `processing_status = 'queued'` and `processing_stage = 'awaiting_embeddings'`. Documents are **never** marked `ready` in Phase 2 (status `ready` is reserved for vector indexing and verification in Phase 3).

---

## 8. RAG and ML architecture

### 8.1 Query pipeline

```mermaid
flowchart TD
    Q[User query] --> AUTH[Auth + workspace scope]
    AUTH --> INT[Intent classifier]
    INT --> V[Vector retrieval]
    INT --> B[BM25 retrieval]
    V --> F[RRF fusion]
    B --> F
    F --> R[Cross-Encoder reranking]
    R --> C[Context selection]
    C --> G[LLM provider adapter]
    G --> N[NLI / evidence checks where enabled]
    N --> CV[Backend citation and access validation]
    CV --> OUT[Answer + source references + limitations]
```

Initial configurable parameters (tune by evaluation): retrieve 20–30 candidates per active retrieval channel, fuse with RRF, rerank, then send approximately 5–8 passages to answer generation subject to context budget and source diversity. These are starting values, not performance guarantees.

### 8.2 Embeddings and Vector Retrieval (Phase 3 C3.1–C3.3)

- **Embedding Model Architecture (C3.1)**:
  - Local Sentence Transformers provider (`SentenceTransformerEmbeddingProvider`) using `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, CPU default, normalized $L_2$ vectors).
  - Deterministic fake provider (`DeterministicFakeEmbeddingProvider`) for millisecond unit testing and offline automated CI without external network access.
  - Thread-safe singleton lifecycle manager (`EmbeddingModelManager`) providing lazy initialization and health check readiness verification.
  - Dynamic dimension and model ID inspection; zero hardcoded dimension assumptions.
  - Configurable model cache directory (`./storage/model_cache`).

- **ChromaDB Vector Store Integration (C3.2)**:
  - Resilient HTTP client wrapper (`get_chroma_client`) connecting to persistent ChromaDB service.
  - Deterministic collection naming: `knovera_chunks_{model_part}_{dimension}` with sanitized characters and cosine metric (`hnsw:space: "cosine"`).
  - Batch vector upsert with automatic batch splitting (`CHROMA_INSERT_BATCH_SIZE=100`) and idempotency via stable chunk UUIDs.
  - Metadata indexing with server-enforced workspace and document scalar filters.
  - Full lifecycle cleanup: `delete_by_document` and `delete_by_workspace` purges.
  - Vector index reconciliation comparing PostgreSQL chunk counts with Chroma collection vector counts.

- **Semantic Vector Retrieval (C3.3)**:
  - `SemanticRetriever` coordinating validation, query embedding, dense vector search, and PostgreSQL source hydration.
  - Query validation (`QueryValidator`) enforcing non-empty/non-whitespace query rules and length limits (`EMBEDDING_QUERY_MAX_LENGTH=256`).
  - Document scope validation verifying all requested document IDs belong to the active workspace.
  - Authoritative PostgreSQL hydration (`ResultHydrator`): Chunks retrieved from Chroma are hydrated directly from the relational database, guaranteeing citation text is verified against active, non-deleted records and preserving vector cosine ranking.
  - Soft-deleted documents (`deleted_at IS NOT NULL`) and deleted workspaces are strictly excluded from retrieval.
  - Telemetry: Retrieval returns detailed duration metrics (`query_validation_ms`, `query_encoding_ms`, `vector_search_ms`, `hydration_ms`, `total_duration_ms`).
  - Baseline evaluation benchmark achieved 100% Recall@5, 100% Recall@10, and 12.18ms average latency.

### 8.2.1 LLM Provider Abstraction, Context Construction & Prompt Engineering (Phase 3 C3.4–C3.6)

- **LLM Provider Abstraction Layer (C3.4)**:
  - Architecture: Strict zero-cloud-SDK constraint. Implemented directly via standard Python libraries and `httpx` (`backend/app/llm/`).
  - Provider Adapters:
    - `MockLLMProvider`: Deterministic, zero-network adapter for automated tests, simulating latencies, JSON mode, and specific failure modes (`auth`, `rate_limit`, `timeout`, `unavailable`).
    - `GeminiProvider`: REST client targeting Google Generative Language API (`v1beta/models/{model}:generateContent`) with `systemInstruction` and `generationConfig` mapping.
    - `GroqProvider`: Ultra-low-latency provider inheriting from OpenAI-compatible REST API targeting `https://api.groq.com/openai/v1`.
    - `OpenAICompatibleProvider`: Generic REST client for Ollama, vLLM, and OpenAI-compatible inference servers, equipped with anti-SSRF IP/host validation.
  - Lifecycle & Reliability:
    - Thread-safe `LLMProviderRegistry` supporting modular registration and lookup.
    - Central `LLMManager` orchestrating generation with bounded exponential backoff retries and randomized jitter.
    - Strict Security Policy: Never silently fallback between providers on failures (preserves billing, privacy, and sovereignty guarantees).
    - Model Capabilities: Per-model tracking of context window token budgets (`max_context_tokens`) and max output limits (`max_output_tokens`).

- **Context Construction & Token Budgeting (C3.5)**:
  - Pipeline: `ContextBuilder` (`backend/app/rag/context/`) transforms raw semantic retrieval results into a compact, relevant, well-structured `ContextPackage`.
  - Authoritative PostgreSQL Revalidation: Re-queries PostgreSQL joining `document_chunks` and `documents` to guarantee that all chunks belong to the active workspace and that parent documents have not been soft-deleted. Attempted cross-workspace chunk injection strictly raises `ContextScopeError`.
  - Evidence Deduplication (`EvidenceDeduplicator`): Prunes identical chunk IDs and identical text SHA-256 hashes, keeping the highest-ranked chunk.
  - Conservative Token Budgeting (`TokenBudgetCalculator`): Computes net available evidence budget:
    $$E_{\text{budget}} = T_{\text{max\_context}} - T_{\text{reserved\_output}} - T_{\text{system}} - T_{\text{query}} - T_{\text{history}} - T_{\text{safety\_margin}}$$
  - Diversity Selection (`EvidenceSelector`): Enforces max chunks (`CONTEXT_MAX_CHUNKS=8`) and max chunks per document (`CONTEXT_MAX_CHUNKS_PER_DOCUMENT=4`) to prevent a single document from starving context diversity. Truncates oversized final chunks cleanly at sentence boundaries.
  - Source ID Attribution: Assigns compact prompt-local source IDs (`[S1]`, `[S2]`, ...) and generates unified citation headers for PDF pages, PPTX slides, and DOCX sections.

- **Prompt Engineering & Structured Output (C3.6)**:
  - Reusable Versioned Prompt (`GeneralQAPrompt` version `general-qa-v1`):
    - System Instruction (`CORE_SYSTEM_PROMPT`): Strict grounding rules enforcing evidence-based answers, explicit source ID attribution, prohibition of external extrapolation, and mandatory abstention if evidence is insufficient.
    - Anti-Prompt-Injection Safeguards: Delimits untrusted document passages within `<document_evidence>` XML-style tags and explicitly instructs the model that text inside document evidence has zero authority to alter system rules or user tasks.
    - Safe Interpolation: Clean non-brace string assembly preventing syntax collisions with curly braces in code or JSON snippets.
  - Structured Output Parser (`StructuredOutputParser`):
    - Parses structured JSON response into `StructuredAnswerDraft`.
    - Handles markdown code fences (````json ... ````) and surrounding conversational text.
    - Extracts granular `FactClaim` records with associated source IDs.
    - Sanitizes citations: Replaces unknown or hallucinated source IDs not present in the authoritative `source_mapping`.
    - Detects explicit `insufficient_evidence` flags for downstream abstention workflows.

### 8.2.2 Grounded Orchestration, Citations & Conversation History (Phase 3 C3.7–C3.9)

- **Source-Grounded Orchestration (`GroundedAnswerService`) (C3.7)**:
  - Architecture: End-to-end RAG orchestrator (`backend/app/rag/orchestration/`) integrating semantic retrieval, context assembly, prompt engineering, LLM generation, and citation resolution.
  - Strict Abstention Policy (`AbstentionPolicy`):
    - Zero active document chunks in workspace: Immediately returns deterministic abstention notice without querying vector index or calling LLM.
    - Zero retrieval matches above cosine distance threshold: Immediately returns transparent abstention stating available documents lack sufficient evidence, saving token usage and eliminating hallucination risk.
  - Telemetry: Collects retrieval latency, generation latency, total duration, prompt tokens, completion tokens, and model identifier metadata.

- **Citation & Location Mapping Subsystem (`backend/app/citations/`) (C3.8)**:
  - Provenance Validation (`CitationValidator`): Re-verifies every extracted source ID against the active `ContextPackage.source_mapping` and PostgreSQL `document_chunks`.
  - Multi-Format Location Mapping (`CitationMapper`):
    - PDF: Maps chunk coordinates to 1-based page numbers (`page_start`, `page_end`).
    - DOCX: Maps chunk coordinates to hierarchical section paths and headings (`section_title`, `section_path`), strictly prohibiting fabricated page numbers.
    - PPTX: Maps chunk coordinates to 1-based slide numbers (`slide_number`).
  - Secure Citation Detail Endpoint (`GET /api/v1/citations/{citation_id}`):
    - Returns full provenance, document metadata, source coordinates, and contextual quote excerpts.
    - Enforces workspace ownership verification, preventing cross-tenant information disclosure.

- **Conversation History & Concurrency Safety (`backend/app/conversations/`) (C3.9)**:
  - Relational Schema: PostgreSQL tables `conversations` (workspace-scoped threads), `messages` (user and assistant chat turns with metadata), and `citations` (relational fact citations linked to chunks).
  - Client Request Idempotency: Unique partial index on `(conversation_id, client_request_id)` returning previously committed turns without duplicate generation or charges.
  - Generation Concurrency Guard: Prevents concurrent message generation in the same conversation; automatically clears stale pending locks older than 300 seconds.
  - Auto-Title Generation: Derives clean conversational title from the initial user query.
  - Message Chronology & Ordering: Deterministic message retrieval ordering using microsecond offsets and role priority (`user` before `assistant`).
  - API Endpoints:
    - `POST /api/v1/workspaces/{workspace_id}/conversations`: Thread creation.
    - `GET /api/v1/workspaces/{workspace_id}/conversations`: Thread listing with pagination.
    - `GET /api/v1/conversations/{conversation_id}`: Full thread retrieval with chronologically sorted message history.
    - `POST /api/v1/conversations/{conversation_id}/messages`: Message submission executing retrieval, grounded generation, and citation persistence.

- **Future Reranker Integration (Phase 4)**:
  - Initial reranker candidate: `cross-encoder/ms-marco-MiniLM-L-6-v2`; validate domain performance in Phase 4.
- Do not claim a model is best without evaluation.

### 8.3 Hybrid retrieval (Phase 4 C4.1–C4.3)

- **BM25 Lexical Retrieval (`backend/app/rag/retrieval/bm25/`) (C4.1)**:
  - Algorithm: Standard BM25 Okapi formulation:
    $$BM25(D, Q) = \sum_{t \in Q} IDF(t) \cdot \frac{f(t, D) \cdot (k_1 + 1)}{f(t, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{avgdl}\right)}$$
    with defaults $k_1 = 1.5$ and $b = 0.75$.
  - Smoothed Okapi IDF Formulation:
    $$IDF(t) = \ln\left(1.0 + \frac{N - n(t) + 0.5}{n(t) + 0.5}\right)$$
    guaranteeing non-negative IDF values ($IDF(t) \ge 0$) even for high-frequency terms.
  - Dedicated Tokenizer (`BM25Tokenizer`): Unicode NFKC normalization, case folding, and strict preservation of technical terms, acronyms, and compound symbols (e.g. `C++`, `C#`, `TCP/IP`, `PostgreSQL`, `FastAPI`, `BM25`, `GPT-4`, `Machine Learning`, `RAG`). No aggressive stemming or stopword removal.
  - Workspace-Scoped In-Memory Index (`BM25WorkspaceIndex`): Built directly from PostgreSQL `document_chunks` (excluding soft-deleted documents).
  - Thread-Safe Bounded Cache (`BM25IndexCache`): Double-checked locking per workspace preventing concurrent builds, LRU capacity eviction bounded by `BM25_INDEX_CACHE_MAX_WORKSPACES=50`.
  - Invalidation Lifecycle: Automatically invalidated upon document upload completion (Stage 8 `ready`), document deletion, or reprocessing.

- **Reciprocal Rank Fusion (`backend/app/rag/retrieval/rrf.py`) (C4.3)**:
  - Formulation:
    $$RRF(d) = \sum_{r \in R} \frac{1}{k + rank_r(d)}$$
    where $rank_r(d) \ge 1$ is the 1-based ranking position in retriever list $r$, and default $k = 60$ (`RRF_K=60`).
  - Deduplication: By stable `chunk_id` UUID; accumulates reciprocal rank contributions for chunks retrieved across multiple systems.
  - Deterministic Sorting: Primary sort by descending `rrf_score`, secondary tie-breaker by `str(chunk_id)` ascending.
  - Candidate Metadata: Preserves `dense_rank`, `bm25_rank`, `vector_distance`, `bm25_score`, and `retrieval_sources`.

- **Hybrid Retrieval Orchestration (`HybridRetriever`) (C4.2)**:
  - Flow:
    1. Query & document scope validation via `QueryValidator`.
    2. Dense semantic candidate retrieval (top `DENSE_RETRIEVAL_TOP_K=20`) via ChromaDB.
    3. Lexical keyword candidate retrieval (top `BM25_RETRIEVAL_TOP_K=20`) via in-memory BM25 inverted index.
    4. Rank fusion via `ReciprocalRankFusion` extracting top `HYBRID_RETRIEVAL_TOP_K=10`.
    5. Single authoritative PostgreSQL hydration via `ResultHydrator.hydrate_hybrid_results`, preserving fused ranking and excluding soft-deleted documents or cross-workspace chunks.
  - Pluggable Modes: Supports `hybrid` (default), `semantic`, and `bm25`.
  - Seamless Context Integration: `HybridSearchResult` adheres to the field structure consumed by `ContextBuilder`, enabling direct end-to-end integration into `GroundedAnswerService`.
  - API Endpoints:
    - `POST /api/v1/workspaces/{workspace_id}/search/hybrid`
    - `POST /api/v1/workspaces/{workspace_id}/search/bm25`
    - `POST /api/v1/workspaces/{workspace_id}/search/semantic` (maintained for backward compatibility)

- **Cross-Encoder Model Lifecycle & Reranker Service (`CrossEncoderReranker`) (C4.4)**:
  - Model: `cross-encoder/ms-marco-MiniLM-L-6-v2` via `sentence_transformers.CrossEncoder`.
  - Lifecycle: `CrossEncoderModelManager` thread-safe singleton with lazy loading, hardware device detection (`cpu`, `cuda`, `auto`), and model caching.
  - Scoring: Batched inference over query-passage pairs emitting uncalibrated raw logit relevance scores (`reranker_score`). Non-finite values (NaN/Inf) are detected and rejected.
  - Resilience: Pluggable failure policy (`RERANKER_FAILURE_POLICY="error"` or `"rrf_only"`) ensuring graceful fallback to RRF rankings without system degradation.

- **Candidate Selection & Reranking Pipeline (C4.5)**:
  - Architecture: Bounded 2-stage retrieval (`RERANKER_CANDIDATE_K=50` candidates fused from RRF -> reranked down to `RERANKER_FINAL_K=10`).
  - Passage Context: Input formatting prepends section titles (`f"{section_title}\n{content}"`) if present for richer contextual alignment.
  - Deterministic Sorting: Primary sort by descending `reranker_score`, secondary tie-breaker by original `rrf_rank`, tertiary by `str(chunk_id)`.
  - Relational Authority: Single PostgreSQL hydration preserves reranked order and injects `reranker_score` and `reranker_rank` into `HybridSearchResult`.

- **Retrieval Evaluation Benchmark & Metrics Suite (C4.6 & C4.7)**:
  - Dataset: Standardized benchmark in `data/retrieval_eval/` comprising `manifest.json`, 24 academic chunks across Computer Science, Biology, and Physics (`corpus.jsonl`), 16 queries in 4 categories (`queries.jsonl`), and graded relevance judgments 0–3 (`qrels.tsv`).
  - Dataset Integrity Validation (`backend/app/rag/evaluation/validation.py`): Validates 10 structural rules (unique queries/corpus chunks, qrels referential integrity, grade bounds 0–3, non-empty text, valid split memberships `dev`/`test`).
  - Deduplication: Strict order-preserving deduplication (`deduplicate_preserve_order`) on retrieved chunk IDs prior to metric evaluation.
  - Relevance Thresholding: Configurable binary threshold (`RETRIEVAL_EVAL_RELEVANCE_THRESHOLD=2`, separating not-relevant/marginal from relevant/highly-relevant) for binary metrics (Recall@K, MRR@K).
  - Metrics Suite (`backend/app/rag/evaluation/metrics.py`):
    - Recall@K: Proportion of relevant chunks retrieved within cutoff $K \in \{5, 10, 20, 50\}$.
    - Mean Reciprocal Rank (MRR@K): Reciprocal rank $\frac{1}{\text{rank}}$ of first relevant result if $\text{rank} \le K$, otherwise 0.
    - Normalized Discounted Cumulative Gain (nDCG@K): Exponential gain formulation:
      $$DCG@K = \sum_{i=1}^K \frac{2^{rel_i} - 1}{\log_2(i + 1)}, \quad nDCG@K = \frac{DCG@K}{IDCG@K}$$
    - Two-stage evaluation: Distinguishes candidate-stage recall (before reranker truncation) from final-stage recall (after reranker).
    - Query Eligibility Accounting: Queries with zero relevant judgments are excluded from macro Recall and nDCG denominators and tracked as `queries_no_relevant`.
  - Evaluation Runner CLI (`backend/scripts/evaluate_retrieval.py`): Multi-system benchmark comparing Dense, BM25, Hybrid RRF, and Hybrid+Reranker across `dev` and `test` splits with automated JSON reporting in `eval/results/`.

- **Retrieval Optimisation & Hyperparameter Tuning (C4.8)**:
  - Parameter Search Space: Bounded grid across `dense_top_k` [10, 20, 30], `bm25_top_k` [10, 20, 30], `bm25_k1` [1.2, 1.5, 1.8], `bm25_b` [0.65, 0.75, 0.85], `rrf_k` [20, 40, 60, 80], `reranker_candidate_k` [15, 30, 50], and `final_k` [8, 10].
  - Quality Regression Protection: Automatic rejection if Recall@10 drops by $>0.05$, nDCG@10 drops by $>0.05$, or p95 latency exceeds 500ms.
  - Multi-Objective Pareto Frontier: Identifies non-dominated configurations balancing (nDCG@10, Recall@10, p95 latency).
  - Lexicographic Selection Strategy: Transparent tie-breaking (no recall regression $\to$ highest nDCG@10 $\to$ highest MRR@10 $\to$ lowest p95 latency).
  - Optimization Runner CLI (`backend/scripts/optimize_retrieval.py`): Explores configuration subspace, tunes exclusively on `dev` split, writes candidate results to `eval/optimization_results/`, and optionally evaluates the selected winner on the frozen `test` split (`--test-eval`).
  - Production Config Safety: Never mutates production configuration automatically; outputs recommendation to `selected_config.json`.

### 8.4 SVM intent classifier & Query Intelligence (Phase 5)

- **Query Intent Taxonomy (`backend/app/ml/query_intent/taxonomy.py`) (C5.1)**:
  - Version: `1.0.0`
  - Core Categories (13 primary intents):
    1. `factual_lookup`: Single discrete factual answers, dates, numbers, author names, or isolated values.
    2. `definition`: Meaning, acronym expansions, or terminological clarification.
    3. `explanation`: Mechanistic how/why conceptual understanding.
    4. `comparison`: Contrasting two or more algorithms, methods, papers, or systems.
    5. `summarization`: Condensation of documents, chapters, or collections.
    6. `procedural_guidance`: Step-by-step instructions, recipes, or configuration guides.
    7. `analytical_reasoning`: Inference, deduction, critique, or evaluation of findings.
    8. `information_extraction`: Compiling and enumerating structured lists of entities or metrics.
    9. `source_evidence`: Explicit requests for citations, page numbers, or quotations.
    10. `recommendation`: Selection advice or prescriptive guidance among alternatives.
    11. `general_conversation`: Greetings, thanks, pleasantries, or meta-assistant dialogue.
    12. `unsupported_action`: External actions beyond Knovera's software boundary.
    13. `ambiguous`: Fragmented or context-deprived queries lacking discernible intent.
  - Multi-Intent Precedence Hierarchy:
    $$\text{source\_evidence} \succ \text{comparison} \succ \text{summarization} \succ \text{recommendation} \succ \text{information\_extraction} \succ \text{procedural\_guidance} \succ \text{analytical\_reasoning} \succ \text{definition} \succ \text{explanation} \succ \text{factual\_lookup}$$
  - Auxiliary Query Attributes:
    `requires_conversation_context`, `requires_multi_source_evidence`, `requests_explicit_citations`, `contains_ambiguous_reference`.

- **Labelled Dataset & Stratified Splits (`data/query_intent/`) (C5.2)**:
  - Dataset Directory Structure: `manifest.json`, `taxonomy.json`, `raw/query_intents.jsonl`, `processed/query_intents_processed.jsonl`, `splits/train.jsonl`, `dev.jsonl`, `test.jsonl`, `schemas/query_intent.schema.json`, `annotation/annotation_guidelines.md`.
  - Initial Dataset Scale: 455 synthetic seed records evenly balanced across all 13 categories (35 examples per category).
  - Provenance & Review Status: Fully documented provenance (`synthetic_seed`, `pending_human_review`). No claims of human ground truth for synthetic data.
  - Stratified Splitting: Deterministic split using random seed 42 (Train: 312 records / 68.6%, Dev: 65 records / 14.3%, Test: 78 records / 17.1%) with grouped near-duplicates preventing train/test leakage.
  - Dataset Validation Engine (`backend/app/ml/query_intent/dataset_validator.py`): Enforces schema validity, taxonomy referential integrity, duplicate detection, conflicting label checks, and produces distribution reports.

- **Text Preprocessing Pipeline (`backend/app/ml/query_intent/preprocessing.py`) (C5.3)**:
  - Version: `1.0.0`
  - Input Validation: Empty/whitespace rejection, configurable `max_length = 512` with truncation flag `was_truncated`.
  - Unicode Normalization: NFKC normalization, control character removal, zero-width space stripping, typographic smart quote normalization.
  - Whitespace Normalization: Collapses multi-spaces, tabs, and newlines to a single space.
  - Sensitive Data Redaction: Safe redaction of emails (`[EMAIL]`), phone numbers (`[PHONE]`), API keys (`[API_KEY]`), and password patterns (`[TOKEN]`) with `was_redacted` tracking.
  - Technical Token Preservation: Regex-based token preservation for programming languages and technical identifiers (`C++`, `C#`, `TCP/IP`, `BM25`, `TF-IDF`, `K-Means`, `GPT-4`, `PostgreSQL`, `FastAPI`).
  - Stopword Policy: Strict retention of question/intent words (`what`, `why`, `how`, `compare`, `explain`, `summarize`).
  - Stemming/Lemmatization: No aggressive stemming or lemmatization.

- **TF-IDF Feature Extraction Pipeline (`backend/app/ml/query_intent/features.py`) (C5.4)**:
  - Technical Token Regex: `[a-zA-Z0-9]+(?:\+\+|#)?(?:[./_-][a-zA-Z0-9]+(?:\+\+|#)?)*|[a-zA-Z0-9]+(?:\+\+|#)` preserving programming languages (`C++`, `C#`), acronyms (`TCP/IP`, `BM25`, `TF-IDF`, `RAG`, `SVM`), and model names (`GPT-4`, `GPT-4o`).
  - Word-Level Vectorizer: `TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True, norm="l2")` generating 3,164 training features.
  - Character-Level Vectorizer: `TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True, norm="l2")` generating 9,910 training features.
  - Combined Feature Union: `FeatureUnion([('word', word_vec), ('char', char_vec)])` producing 13,074-dimensional sparse representations with ~1.06% density.
  - Strict Leakage Prevention: Fitted strictly on the `train` split (312 queries); `dev` (65) and `test` (78) splits use only fitted transformations.

- **Logistic Regression Baseline (`backend/app/ml/query_intent/logistic_model.py`) (C5.5)**:
  - Architecture: Multiclass regularized `LogisticRegression(solver="lbfgs", max_iter=2000, random_state=42)`.
  - Hyperparameter Search: Bounded grid across feature types (`word`, `char`, `combined`), regularization $C \in \{0.1, 1.0, 10.0\}$, and class weighting (`None`, `balanced`).
  - Best Dev Configuration: `combined` features, $C = 10.0$, `class_weight = None`.
  - Development Performance: **Accuracy = 0.8923**, **Macro F1 = 0.8941**, **Macro Precision = 0.9114**, **Macro Recall = 0.8923**, **Weighted F1 = 0.8941**.
  - Probabilistic Output: Native class probability estimates via `predict_proba()`.
  - Artifact Path: `models/query_intent/logistic_regression/` (`model.joblib`, `manifest.json`).

- **Linear Support Vector Machine (`backend/app/ml/query_intent/svm_model.py`) (C5.6)**:
  - Architecture: Multiclass `LinearSVC(max_iter=5000, random_state=42, dual="auto")`.
  - Hyperparameter Search: Evaluated across feature types, $C \in \{0.1, 1.0, 10.0\}$, and class weighting.
  - Best Dev Configuration: `word` features, $C = 1.0$, `class_weight = None`.
  - Development Performance: **Accuracy = 0.8923**, **Macro F1 = 0.8920**, **Macro Precision = 0.8974**, **Macro Recall = 0.8923**, **Weighted F1 = 0.8920**.
  - Decision Output: Uncalibrated margins via `decision_function()`.
  - Artifact Path: `models/query_intent/linear_svm/` (`model.joblib`, `manifest.json`).

- **Model Comparison & Selection (C5.7)**:
  - Evaluation Metrics: Accuracy, Macro/Weighted Precision, Recall, F1 across all 13 categories, and 13x13 confusion matrices.
  - Probability Calibration Analysis:
    - Logistic Regression evaluated on development split: Multiclass Cross-Entropy Log Loss = **0.7516**, Multiclass Brier Score = **0.3080**, Expected Calibration Error (ECE) = **0.3203**, Maximum Calibration Error (MCE) = **0.8503**.
    - Confidence Output Type: Explicitly documented as `uncalibrated_probability` (softmax output), avoiding misleading claims of post-hoc Platt/Isotonic calibration.
    - Linear SVM: Outputs signed geometric margin distances (`decision_score`), not probabilities.
  - Selection Decision: **Logistic Regression** selected as primary model due to higher Macro F1 (0.8941 vs 0.8920), higher Macro Precision (0.9114 vs 0.8974), and native well-behaved class probability distributions required for uncertainty routing.
  - Promoted Artifact: Serialized to `models/query_intent/selected_model/` (`model.joblib`, `manifest.json`).
  - Frozen Holdout Test Evaluation: Single unbiased evaluation on `test` split (78 queries) yielding **Test Accuracy = 0.8333**, **Test Macro F1 = 0.8330**, **Test Log Loss = 0.8711**, **Test Brier Score = 0.3278**, **Test ECE = 0.2874**.

- **API Integration & Prediction Service (C5.8)**:
  - Architecture: Modular monolith service `QueryIntentService` (`backend/app/ml/query_intent/service.py`) with thread-safe process-level singleton lifecycle.
  - Model Lifecycle: Validates model artifact existence, SHA-256 checksum, taxonomy version (`1.0.0`), preprocessing version (`1.0.0`), and presence of all 13 authoritative classes.
  - Non-Blocking Asynchronous Inference: Synchronous scikit-learn feature extraction and predict pipeline executed off the FastAPI event loop via `asyncio.to_thread` worker pool.
  - Fault Tolerance & Fallback Policies: Configurable `QUERY_INTENT_MODEL_FAILURE_POLICY` supporting `default_rag` (safe fallback to standard hybrid retrieval) and `controlled_error` (raises HTTP 503/500).
  - API Endpoints:
    - `POST /api/v1/query/intent` and `POST /api/v1/query-intent/predict`: Authenticated via JWT bearer token, validates optional `workspace_id` against user ownership, enforces query length boundaries (max 2000 chars), returns structured `QueryIntentResponse`.
    - `GET /api/v1/query-intent/readiness`: Returns diagnostic readiness metadata (`ready` / `unavailable`, loaded model ID, class count).

- **Intent-Based Module Routing & Chat Integration (C5.9)**:
  - Centralized Router (`IntentRouter` in `backend/app/ml/query_intent/router.py`):
    - Config Version: `1.0.0`
    - Full 13-category routing registry (`INTENT_ROUTES`) mapping intents to logical application modules and retrieval profiles:
      - `factual_lookup` $\rightarrow$ `knowledge_retrieval` (profile: `factual`, retrieval: True)
      - `definition` $\rightarrow$ `concept_explanation` (profile: `definition`, retrieval: True)
      - `explanation` $\rightarrow$ `explanatory_retrieval` (profile: `explanatory`, retrieval: True)
      - `comparison` $\rightarrow$ `comparative_retrieval` (profile: `comparative`, retrieval: True)
      - `summarization` $\rightarrow$ `summarization` (profile: `summarization`, retrieval: True)
      - `procedural_guidance` $\rightarrow$ `procedural_guidance` (profile: `procedural`, retrieval: True)
      - `analytical_reasoning` $\rightarrow$ `evidence_analysis` (profile: `analytical`, retrieval: True)
      - `information_extraction` $\rightarrow$ `structured_extraction` (profile: `extraction`, retrieval: True)
      - `source_evidence` $\rightarrow$ `citation_retrieval` (profile: `citation`, retrieval: True)
      - `recommendation` $\rightarrow$ `evidence_based_recommendation` (profile: `recommendation`, retrieval: True)
      - `general_conversation` $\rightarrow$ `general_conversation` (retrieval: False, citations: False)
      - `unsupported_action` $\rightarrow$ `capability_boundary` (retrieval: False, capability_response: True)
      - `ambiguous` $\rightarrow$ `clarification` (retrieval: False, clarification: True)
  - Empirically Calibrated Confidence Threshold: $\tau = 0.30$ (established on development data where confidence $\ge 0.30$ yields 92.73% classification accuracy; queries $< 0.30$ fall back to `default_rag`).
  - Disambiguation: Strict separation between high-confidence `ambiguous` queries (routes to clarification prompt) and low-confidence predictions (falls back to default RAG).
  - Conversation Pipeline Integration (`ConversationService.submit_message`):
    - Turn sequence: User message persisted $\rightarrow$ Non-blocking intent prediction $\rightarrow$ Routing decision resolution $\rightarrow$ Execution of selected handler $\rightarrow$ Metadata persistence $\rightarrow$ Citation resolution.
    - `general_conversation`: Generates polite response via LLM without document retrieval (prevents abstention failure on empty workspaces).
    - `unsupported_action`: Returns explicit capability boundary notice.
    - `ambiguous`: Returns clarification prompt requesting missing details.
    - Knowledge intents: Execute `GroundedAnswerService` with specialized retrieval profile.
    - Complete intent classification telemetry persisted in `assistant_message.retrieval_metadata["intent_classification"]`.
  - Security Invariant: Intent routing strictly operates after authentication and workspace ownership authorization, never granting permissions or bypassing tenant barriers.

### 8.5 K-Means topic discovery

- **Input and Normalization (C6.1)**:
  - Canonical document chunks extracted from PostgreSQL for authorized workspace, strictly excluding soft-deleted documents.
  - ChromaDB vector index reused where available; missing vectors computed via `EmbeddingProvider`.
  - Vectors validated for dimensionality (384), finiteness (no NaN/Inf), zero-norm detection, and explicitly $L_2$-unit normalized:
    $$\|u - v\|_2^2 = 2 - 2 \cos(u, v)$$
    ensuring Euclidean K-Means directly optimizes directional semantic similarity.
- **Reproducible Dataset Snapshots (C6.2)**:
  - Stored in `data/topic_clustering/snapshots/<snapshot_id>/`:
    - `embeddings.npy`: float32 normalized embedding matrix of shape $(N, 384)$.
    - `records.jsonl`: per-chunk metadata records matching schema `clustering_record.schema.json`.
    - `manifest.json`: manifest with metadata and cryptographic SHA-256 `corpus_hash`.
  - Rigorous alignment, normalization, non-leakage, and integrity validated via `ClusteringDatasetValidator`.
- **K-Means Clustering and Quality Evaluation (C6.3)**:
  - Deterministic Scikit-learn `KMeans` (`init="k-means++"`, `n_init=20`, `random_state=42`, `algorithm="lloyd"`).
  - Multi-metric candidate $K$ evaluation ($K \in \{2, 3, 4, 5, 6, 7, 8, 10\}$):
    - Inertia (WCSS)
    - Silhouette Score (Euclidean and Cosine)
    - Davies-Bouldin Index (lower is better)
    - Calinski-Harabasz Index (higher is better)
  - Multi-criteria weighted rank heuristic for automatic optimal $K$ recommendation.
  - Centroid extraction, cluster-level statistics (size, proportion, min/mean/max radius), and top-5 nearest representative chunks.
  - Model serialization in `models/topic_clustering/<snapshot_id>/<model_version>/` (`kmeans_model.joblib`, `centroids.npy`, `assignments.jsonl`, `cluster_statistics.json`, `manifest.json`).
- **K Selection and Silhouette Analysis (C6.4)**:
  - `ClusterSelectionService`: loads snapshot, evaluates valid candidate $K$ configurations ($2 \le K < N$).
  - Inertia drop and relative drop for elbow curve analysis.
  - Euclidean silhouette (`metric="euclidean"`) and Cosine silhouette (`metric="cosine"`).
  - Sample-level silhouette analysis producing per-cluster cohesion, median, min, max, negative count, and negative percentage.
  - Deterministic stratified sampling when $N > \text{sample\_size}$ (preserving cluster balance).
  - Partition stability evaluated via Adjusted Rand Index (ARI) across multiple controlled random seeds.
  - Size diagnostics (min, max, mean, std, largest cluster proportion, singleton counts).
  - Machine-readable evaluation report persisted in `eval/topic_clustering/k_selection_<snapshot_id>.json`.
- **Cluster Labelling (C6.5)**:
  - Canonical chunk hydration from PostgreSQL with workspace authorization and deleted-document filtering.
  - Cluster-level TF-IDF keyword extraction with unigrams and bigrams, penalizing generic document stopwords.
  - Deterministic title and description generation composing top distinctive keyphrases into Title Case.
  - Safe neutral fallback ("Mixed Topic Cluster X") for weakly coherent or empty clusters.
  - Optional LLM-assisted labelling with strict JSON validation and deterministic fallback.
  - Preservation of human-approved or reviewed labels across re-clustering executions.
- **Relational Persistence & Active Run Lifecycle (C6.6)**:
  - Persistent storage in PostgreSQL: `topic_clustering_runs`, `topics`, `topic_assignments` (Alembic migration `20261107_005`).
  - Strict foreign keys and unique constraints: `UNIQUE (clustering_run_id, cluster_key)` and `UNIQUE (clustering_run_id, chunk_id)`.
  - Transactional active-run lifecycle: setting a new run active transactionally deactivates prior runs.
  - Historical run preservation: previous runs and assignments remain intact for audit and rollback.
  - Idempotent execution: duplicate runs are recognized and reused without corrupting data.
- **Topic Discovery API (C6.7)**:
  - `GET /api/v1/workspaces/{id}/topics`: List topics for active or historical `run_id`, with search (`search`), pagination (`page`, `page_size`), sorting (`sort_by`, `sort_order`), and run metadata summary.
  - `GET /api/v1/workspaces/{id}/topic-runs`: Paginated history of clustering runs for the workspace.
  - `GET /api/v1/workspaces/{id}/topic-runs/{run_id}`: Full configuration, metrics, and summary counts for a specific clustering run.
  - `GET /api/v1/workspaces/{id}/topics/{topic_id}`: Single topic details with keyword weights, chunk/document counts, and parent run summary.
  - `GET /api/v1/workspaces/{id}/topics/{topic_id}/chunks`: Paginated source chunks assigned to topic with document title, snippet, source type, page/slide reference, distance to centroid, and representative flag.
  - Multi-tenant workspace isolation and automatic exclusion of soft-deleted documents.
- **Topic Explorer UI (C6.8)**:
  - Integrated React 18 routes: `/app/workspaces/:workspaceId/topics` and `/app/workspaces/:workspaceId/topics/:topicId`.
  - Sidebar navigation entry with `Layers` icon under Knowledge section.
  - Topic Explorer page: stats ribbon (topics, chunks, documents, optimal K), historical run switcher, search & sorting controls, and responsive topic card grid.
  - Topic Detail page: topic header, keyword cloud with weights, metrics summary, and paginated assigned chunks table with links to source documents.

### 8.6 Knowledge graph

- **Ontology & Taxonomies**: Centralized ontology registry (`app.ml.knowledge_graph.ontology` v1.0.0) distinguishing abstract technical concepts (`algorithm`, `method`, `metric`, `process`, `technical_concept`, etc.) and concrete entities (`model`, `dataset`, `technology`, `organization`, `person`).
- **Verifiable Mention Offsets**: Every extracted mention preserves exact Unicode code-point character offsets `[start_offset:end_offset]` within the source chunk, verified by strict slice checking (`verify_span`).
- **Punctuation-Safe Entity Normalization**: Preserves critical technical punctuation (e.g., `C++`, `C#`, `Node.js`, `TF-IDF`, `.NET`, `BM25`), applies an authoritative domain alias registry (`ML` → `Machine Learning`, `NLP` → `Natural Language Processing`, `SVM` → `Support Vector Machine`), performs plural/variant merging, and disambiguates contextual homonyms (e.g. `Apple Inc.` vs fruit, `Transformer` model vs electrical component).
- **Typed Relationship Extraction**: Extracts structured subject-predicate-object triples using an approved relationship ontology (`uses`, `is_a`, `subclass_of`, `part_of`, `contains`, `proposed_by`, `evaluated_on`, `improves`, `trained_on`, etc.).
- **Co-occurrence Rejection & Negation**: Nodes appearing in the same chunk without explicit relational syntax are strictly rejected. Negation markers (`not`, `never`, `does not use`, `without`) set `is_negated=True`.
- **Epistemic Modality**: Classifies relationship certainty into `certain` (direct factual statements), `hypothetical` (conditional statements), or `uncertain` (hedged claims).
- **Consolidation & Evidence Attribution**: Consolidates identical triples across chunks into unique edges while aggregating all underlying text spans in `relationship_evidence`.
- **Relational Persistence (C7.3/C7.7)**: Persisted in PostgreSQL via `KnowledgeGraphRepository` across 5 dedicated tables (`knowledge_extraction_runs`, `knowledge_nodes`, `knowledge_mentions`, `knowledge_relationships`, `relationship_evidence`) under Alembic migration `20261107_006`.
- **Relationship Validation Service (`RelationshipValidationService`) (C7.4)**:
  - Canonical Endpoint Validation: Verifies both subject and object resolve to registered canonical entities/concepts within the authorized workspace.
  - Ontology Domain & Range Constraints: Enforces predicate typing (e.g. `trained_on` must connect a model/system to a dataset).
  - Reflexivity & Self-Loop Guard: Rejects self-loops unless predicate is explicitly reflexive (`correlates_with`, `similar_to`).
  - Strict Source Evidence Verification: Re-checks exact Unicode slice offsets `[start_offset:end_offset]` against canonical chunk text; computes and compares SHA-256 chunk content hashes to reject stale mentions.
  - Modality & Hedging: Flags `hypothetical` or `uncertain` relationships as `needs_review`.
  - Contradiction Detection: Identifies pairwise conflicting assertions (e.g. $[A, P, B, \text{polarity}=\text{positive}]$ vs $[A, P, B, \text{polarity}=\text{negative}]$) within extraction batches, transitioning them to `needs_review` with detailed audit reasons.
- **NetworkX Graph Construction (`KnowledgeGraphBuilder`) (C7.5)**:
  - Directed Multigraph Representation: Uses `networkx.MultiDiGraph` to preserve multiple typed relationships, inverse edges, and parallel connections between node pairs.
  - Deterministic Construction: Implements strict alphanumeric sorting on nodes (`(id, name)`) and edges (`(source, predicate, target, rel_id)`), ensuring bit-for-bit identical graphs across runs.
  - Isolated Node Retention: Preserves disconnected concepts and entities to accurately portray knowledge density and coverage gaps.
  - Graph Statistics (`GraphStatisticsService`): Computes comprehensive topological metrics including node/edge counts, concept vs. entity split, degree centrality distributions, connected component counts, and self-loop/parallel-edge tallies.
- **Graph Snapshot Persistence & Lifecycle (`GraphPersistenceService`) (C7.6)**:
  - Storage Layer: Deterministic JSON node-link serialization (`SerializedGraphDocument`) with SHA-256 checksums and sidecar `manifest.json`.
  - Atomic File Promotion: Writes to temporary files (`.tmp`), validates cryptographic byte checksums, and executes atomic filesystem promotion to prevent partial or corrupted writes.
  - PostgreSQL Snapshot Registry: Tracks snapshots in `knowledge_graph_snapshots` (Alembic migration `20261107_007`) with topological statistics, artifact URIs, and single-active-snapshot enforcement per workspace.
  - Fallback Reconstruction: If disk artifacts are damaged or missing, `reconstruct_from_db` deterministically re-synthesizes the `MultiDiGraph` from authoritative PostgreSQL tables (`knowledge_nodes`, `knowledge_relationships`).
- **Knowledge Graph REST API Layer (`KnowledgeGraphService`) (C7.7)**:
  - Authenticated Workspace-Scoped Endpoints:
    - `GET /workspaces/{id}/knowledge-graph`: Overview metadata, node/edge counts, topological density, component count, capabilities, and active snapshot reference.
    - `GET /workspaces/{id}/knowledge-graph/nodes`: Paginated search and browsing across concepts and entities with query matching on canonical label, normalized name, aliases, or descriptions, sortable by degree or name.
    - `GET /workspaces/{id}/knowledge-graph/nodes/{node_id}`: Full node details, category, aliases, in/out degrees, mention counts, and supporting document counts.
    - `GET /workspaces/{id}/knowledge-graph/neighborhood`: Bounded BFS traversal around a focal node (depth 1 or 2, direction outgoing/incoming/both, predicates filter, node category filter, max_nodes <= 250, max_edges <= 500) preserving parallel edges.
    - `GET /workspaces/{id}/knowledge-graph/relationships`: Paginated and filtered relationship edges connecting nodes in the snapshot.
    - `GET /workspaces/{id}/knowledge-graph/relationships/{rel_id}`: Single relationship details, predicate, polarity, modality, and confidence.
    - `GET /workspaces/{id}/knowledge-graph/relationships/{rel_id}/evidence`: Verified source evidence records with document title, chunk ID, verified text span, and location metadata (`page_start`, `slide_number`, `section_title`).
    - `GET /workspaces/{id}/knowledge-graph/nodes/{node_id}/evidence`: Document surface mentions and text excerpts for a canonical node.
    - `GET /workspaces/{id}/knowledge-graph/paths`: Multi-hop path exploration using NetworkX `all_simple_edge_paths` (bounded depth 1–4 hops, directed/undirected, max_paths <= 25) with detailed step edges and nodes.
    - `GET /workspaces/{id}/knowledge-graph/snapshots`: Workspace snapshot version history.
  - Security & Multitenancy: Strict workspace isolation (`get_user_workspace`); cross-workspace access is rejected with `404 Not Found`; historical snapshots are strictly read-only and never mutate active snapshot state.
- **Interactive Graph Visualisation (`Cytoscape.js Canvas`) (C7.8)**:
  - Engine: Native Cytoscape.js integration (`GraphCanvas`) styled with dark mode aesthetics.
  - Visual Encoding: High-contrast node palette (Concepts in violet `#8b5cf6`, Entities in teal `#14b8a6`, algorithms `#3b82f6`, models `#8b5cf6`, datasets `#f59e0b`, software `#06b6d4`, languages `#10b981`, metrics `#ec4899`, organizations `#6366f1`, persons `#f43f5e`).
  - Directed Curved Bezier Edges: Preserves and renders parallel relations cleanly with direction arrows.
  - Layout Algorithms: Dynamic layout switching between COSE (force-directed), Concentric (centrality-based hierarchy), Breadth-First, and Grid.
  - Incremental Exploration: "Expand Neighbors" fetches 1-hop subgraphs dynamically and merges discovered nodes and edges into the canvas without full page reloads.
  - Snapshot Switching: Seamless exploration of historical snapshots with read-only badges and safety guards.
- **Source-Linked Graph Exploration & Path Reasoning (C7.9)**:
  - Slide-Over Drawers: Dedicated `GraphNodeDetails` and `GraphRelationshipDetails` panels displaying comprehensive metadata and verified source citations.
  - Canonical Document Traceability: "Open in Document" links directly navigate to `/app/workspaces/:workspaceId/documents/:documentId` with precise query parameters (`chunk_id`, `page`, `slide`, `section`), highlighting exact evidence passages.
  - Multi-Hop Path Explorer: Modal dialog discovering connection chains between any two concepts, rendering step-by-step reasoning paths with an action to highlight the entire path and dim background elements on the canvas.

### 8.7 Bayesian Knowledge Tracing

Parameters per skill/concept:
- `P(L0)`: initial probability of knowing the concept.
- `P(T)`: probability of learning after an opportunity.
- `P(G)`: probability of guessing correctly when not known.
- `P(S)`: probability of slipping (incorrect answer) when known.

Track concept/question mapping and ordered responses. Start with simulated data, then consent-based real quiz interactions. Evaluate log loss and Brier score against a baseline such as historical per-user accuracy. Display estimates only when sufficient attempts exist. Do not turn BKT into a permanent label of learner ability.

### 8.8 NLI evidence validation

- Split generated answers into claims.
- Compare each claim with cited evidence passages.
- Predict entailment, contradiction, or neutral.
- Flag neutral/contradictory support for review or qualification.
- Preserve claim/evidence mapping and model version.
- NLI is not a truth oracle; neutral does not mean false, and entailment does not prove the source itself is correct.

---

## 9. LLM provider integration

Use a provider adapter interface, for example:

```python
class LLMProvider:
    def generate(self, messages, *, model, temperature, max_tokens): ...
```

Provider candidates may include Gemini, Groq-hosted models, or another OpenAI-compatible provider. Select the actual provider/model through backend environment configuration after checking context length, latency, structured output, privacy terms, rate limits, and cost.

Rules:
- No provider API key is required to start the app or run non-LLM tests.
- Keys live only in backend environment variables.
- Never expose keys through `VITE_` variables.
- Send only the minimum retrieved passages necessary.
- Tell users when selected text is sent to an external provider.
- Use bounded retries and provider-neutral error types.
- Do not leak provider-specific response formats into domain services.
- Do not silently switch providers if data handling changes; fallback must be explicit.

---

## 10. API surface

All endpoints use `/api/v1`. Define payloads and pagination with Pydantic. A listed route is a target contract, not a Phase 0 implementation requirement.

### Health

| Method | Endpoint | Purpose | Auth |
|---|---|---|---|
| GET | `/health` | Liveness | No |
| GET | `/health/ready` | PostgreSQL + Chroma readiness | No; safe diagnostics only |

### Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Authenticate/create session |
| POST | `/auth/refresh` | Rotate refresh token |
| POST | `/auth/logout` | Revoke current session |
| GET | `/auth/me` | Current user profile |

### Workspaces

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/workspaces` | Create workspace |
| GET | `/workspaces` | List owned workspaces |
| GET | `/workspaces/{workspace_id}` | Get workspace |
| PATCH | `/workspaces/{workspace_id}` | Rename/update workspace |
| DELETE | `/workspaces/{workspace_id}` | Delete workspace/derived data |

### Documents

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/workspaces/{workspace_id}/documents` | Upload multipart document |
| GET | `/workspaces/{workspace_id}/documents` | List documents |
| GET | `/documents/{document_id}` | Document metadata |
| GET | `/documents/{document_id}/status` | Processing status |
| POST | `/documents/{document_id}/retry` | Retry failed processing |
| GET | `/documents/{document_id}/content` | Open authorised source/preview metadata |
| DELETE | `/documents/{document_id}` | Delete document/derived data |

### Chat and citations

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/workspaces/{workspace_id}/conversations` | Create conversation |
| GET | `/workspaces/{workspace_id}/conversations` | List conversations |
| GET | `/conversations/{conversation_id}` | Conversation/messages |
| POST | `/conversations/{conversation_id}/messages` | Submit query/create answer |
| POST | `/workspaces/{workspace_id}/chat/compare` | Compare selected documents |
| GET | `/citations/{citation_id}` | Resolve authorised source passage |

### Knowledge, study, research, learning

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/workspaces/{workspace_id}/knowledge/discover` | Start topic/concept discovery |
| GET | `/workspaces/{workspace_id}/knowledge/topics` | List topics |
| GET | `/workspaces/{workspace_id}/knowledge/graph` | Retrieve graph |
| GET | `/workspaces/{workspace_id}/knowledge/concepts/{concept_id}` | Concept/evidence details |
| POST | `/workspaces/{workspace_id}/study/notes` | Generate notes |
| POST | `/workspaces/{workspace_id}/study/questions` | Generate question set |
| POST | `/workspaces/{workspace_id}/study/flashcards` | Generate flashcards |
| POST | `/workspaces/{workspace_id}/study/quizzes` | Create quiz |
| POST | `/quizzes/{quiz_id}/attempts` | Submit quiz answers |
| GET | `/workspaces/{workspace_id}/study/history` | Study/quiz history |
| GET | `/workspaces/{workspace_id}/learning/mastery` | Mastery estimates |
| GET | `/workspaces/{workspace_id}/learning/recommendations` | Revision recommendations |
| GET | `/workspaces/{workspace_id}/learning/progress` | Learning summary |
| POST | `/workspaces/{workspace_id}/research/compare` | Compare papers |
| POST | `/workspaces/{workspace_id}/research/coverage` | Analyse corpus coverage |

All workspace-bound endpoints require authentication and owner checks.

---

## 11. Configuration and environment variables

Root `.env.example` should include safe local-development placeholders:

```dotenv
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
FRONTEND_ORIGIN=http://localhost:5173

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=knovera
POSTGRES_USER=knovera_app
POSTGRES_PASSWORD=change_me_locally
DATABASE_URL=postgresql+psycopg://knovera_app:change_me_locally@localhost:5432/knovera

CHROMA_HOST=localhost
CHROMA_PORT=8001
CHROMA_COLLECTION_PREFIX=knovera

STORAGE_BACKEND=local
STORAGE_LOCAL_PATH=./storage
MAX_UPLOAD_MB=50

AUTH_ACCESS_TOKEN_MINUTES=15
AUTH_REFRESH_TOKEN_DAYS=30
AUTH_SECRET_KEY=replace_with_random_secret

LLM_PROVIDER=
LLM_MODEL=
LLM_API_KEY=
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
NLI_MODEL=cross-encoder/nli-deberta-v3-base
```

Notes:
- Values are illustrative local defaults; generate a random secret for each environment.
- Construct `DATABASE_URL` from individual settings or validate consistency; avoid two conflicting sources of truth.
- Never commit `.env`.
- Model variables are placeholders; Phase 0 must not download model weights.
- Frontend config belongs in `frontend/.env.example` and contains only `VITE_API_BASE_URL`.

---

## 12. Repository and configuration files

```text
Knovera/
├── frontend/
├── backend/
├── docs/
│   ├── prd.md
│   ├── trd.md
│   ├── app_flow.md
│   ├── design_brief.md
│   ├── schema.md
│   └── implementation_plan.md
├── evaluation/{datasets,scripts,results,reports}/
├── models/
├── storage/                  # ignored runtime data
├── scripts/
├── progress/
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

Do not create empty files for every future module. Add code when its phase begins. Keep local storage and generated artifacts out of Git.

---

## 13. Testing strategy

**Backend:** unit tests for chunking/ranking/citation/BKT/graph; API integration for auth/RLS/workspaces/upload/chat/deletion; migration tests; worker idempotency/retry tests.

**Frontend:** component tests for forms/routes/state/citations/upload; accessibility checks; E2E register → workspace → upload → ready → cited answer → delete.

**ML:** retrieval Recall@K/MRR/nDCG/latency/citation support; intent macro F1/class metrics; clustering silhouette/Davies–Bouldin/stability/human coherence; BKT log loss/Brier/calibration; NLI per-class metrics and human review.

**Security:** cross-user/workspace access, forged resource IDs, refresh token rotation/replay, path traversal/MIME spoofing, prompt-injection documents, rate limits, and payload limits.

---

## 14. Deployment target and operations

### 14.1 Local development

- Docker Compose: PostgreSQL and ChromaDB.
- Backend: local `.venv`, Uvicorn.
- Frontend: Vite dev server.
- Uploads and Chroma persistence: ignored local directories/volumes.

### 14.2 Initial production topology

Target a single **Ubuntu 24.04 LTS Docker-capable VPS** for the first deployment:

- Caddy handles TLS and reverse proxy.
- Docker Compose runs frontend static server, FastAPI API, worker, PostgreSQL, and ChromaDB.
- Persistent volumes hold PostgreSQL, ChromaDB, and uploaded originals.
- Database and file backups are scheduled and tested.
- Only the reverse proxy is publicly exposed; database/vector ports remain private.
- Use production secrets and a non-root container user where feasible.
- Monitor API health, worker backlog, disk usage, backup success, and provider errors.

No specific VPS vendor is mandated. Select one after estimating RAM, CPU, storage, backups, and model execution requirements. Local transformer models may require more resources than a small VPS; run embeddings/reranking on a separate compute host or use an explicitly configured provider if needed. Do not assume a GPU exists.

### 14.3 Backup and recovery

- Back up PostgreSQL and uploaded originals.
- ChromaDB can be rebuilt from chunk records and embeddings, but record re-embedding cost and test restoration.
- Test restore, not only backup creation.
- Document retention and deletion policies.

---

## 15. Technical constraints and prohibited shortcuts

- Never use model-generated citation strings as canonical citation records.
- Never run vector search without workspace filters and server ownership checks.
- Never store raw passwords or refresh tokens.
- Do not use in-memory state for durable job tracking.
- Do not create a microservice per module.
- Do not commit uploaded files, model weights, secrets, or DB volumes.
- Do not mark a document ready before relational and vector indexing are consistent.
- Do not claim NLI verifies truth or BKT diagnoses ability.
- Do not start Phase 1 until Phase 0 acceptance criteria pass.

---

## 16. Technical decision change control

A change to framework, database, vector store, authentication, hosting, or data ownership must state the reason, alternatives, migration/security/cost impacts, and updates required in the PRD, app flow, schema, design brief, and implementation plan. An implementation agent must report material contradictions rather than silently selecting a different architecture.
