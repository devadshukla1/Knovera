# Knovera — System Architecture & Technical Design

| Field | Value |
|---|---|
| Product | **Knovera** |
| Tagline | **Turn Information into Intelligence.** |
| Architecture Style | **Modular Monolith** |
| Current Milestone | **Phase 0 — Technical Foundation & Architecture** |
| Document Version | 1.0.0 |
| Last Updated | 2026-11-05 |
| Reference Specifications | `docs/trd.md`, `docs/schema.md`, `docs/prd.md`, `docs/app_flow.md`, `docs/design_brief.md` |

---

## 1. Executive Overview

**Knovera** is an AI-powered knowledge intelligence platform designed for students and researchers. It transforms disparate study materials, lecture slides, research publications, and personal notes into an interconnected, evidence-traceable, and verifiable knowledge ecosystem.

To maximize operational reliability, developer velocity, and maintainability while avoiding premature infrastructure complexity, Knovera is architected as a **Modular Monolith**. Rather than distributing functionality across disparate microservices requiring distributed transactions, service discovery, or messaging buses (e.g., Kafka, Redis, Kubernetes), Knovera organizes backend business domains into cohesive, decoupled Python modules communicating through explicit service interfaces within a single FastAPI application.

```mermaid
flowchart TD
    subgraph Client [Client Presentation Layer - Localhost]
        FE[React 18 + TypeScript + Vite SPA<br/>Port: 5173<br/>Tailwind CSS + Dark/Light Theme]
    end

    subgraph BackendHost [FastAPI Modular Monolith - Localhost:8000]
        API_GATEWAY[FastAPI Application Instance<br/>CORS Middleware & Structured Logging]
        
        subgraph VersionedRouter [/api/v1 Router Aggregator]
            HEALTH_ROUTES[Health & Readiness Probes<br/>/health & /health/ready]
            FUTURE_ROUTES[Planned Phase 1-10 Domain Modules<br/>Auth, Workspaces, Documents, RAG, Graph]
        end
        
        subgraph CoreSubsystem [Core Infrastructure & Utilities]
            CONFIG[Pydantic Settings<br/>Environment & Safe Validation]
            LOGGER[Structured Logger<br/>Credential Masking]
        end
        
        subgraph DataAccessLayer [Data Access & Integration Layer]
            DB_SESSION[PostgreSQL Session Manager<br/>SQLAlchemy 2.x + Psycopg 3]
            CHROMA_CLIENT[ChromaDB Client Wrapper<br/>chromadb.HttpClient]
        end
    end

    subgraph DataServices [Containerized Data Services via Docker Compose]
        POSTGRES[(PostgreSQL 16+ Database<br/>Port: 5432<br/>Persistent Volume: postgres_data<br/>System of Record)]
        CHROMADB[(ChromaDB Vector Store<br/>Port: 8001:8000<br/>Persistent Volume: chroma_data<br/>Rebuildable Vector Index)]
    end

    FE -->|HTTP / JSON via VITE_API_BASE_URL| API_GATEWAY
    API_GATEWAY --> CONFIG
    API_GATEWAY --> LOGGER
    API_GATEWAY --> VersionedRouter
    
    HEALTH_ROUTES -->|SELECT 1 Ping| DB_SESSION
    HEALTH_ROUTES -->|client.heartbeat() Ping| CHROMA_CLIENT
    
    DB_SESSION -->|TCP / postgresql+psycopg| POSTGRES
    CHROMA_CLIENT -->|HTTP REST /heartbeat| CHROMADB

    classDef client fill:#191F31,stroke:#8B7CFF,stroke-width:2px,color:#F4F5FB;
    classDef backend fill:#121625,stroke:#58D6C7,stroke-width:2px,color:#F4F5FB;
    classDef data fill:#0B0D14,stroke:#42C98A,stroke-width:2px,color:#F4F5FB;
    class FE client;
    class API_GATEWAY,HEALTH_ROUTES,FUTURE_ROUTES,CONFIG,LOGGER,DB_SESSION,CHROMA_CLIENT backend;
    class POSTGRES,CHROMADB data;
```

---

## 2. Component Responsibilities & Boundaries

The Knovera system establishes strict separation of concerns across its four foundational components:

| Component | Technology Stack | Primary Responsibilities | Operational Boundary & Constraints | Default Port / Binding |
|---|---|---|---|---|
| **Frontend Presentation Layer** | React 18+, TypeScript (strict mode), Vite 5+, Tailwind CSS 3.4+, React Router | • User interface rendering and responsive design.<br/>• Presentation of product identity and value proposition.<br/>• Dynamic real-time backend connectivity monitoring (Loading, Success, Degraded, and Error states).<br/>• Standardized, typed API consumption via native `fetch`. | • Never communicates directly with PostgreSQL or ChromaDB.<br/>• Holds zero application secrets, database credentials, or server signing keys.<br/>• Consumes backend API exclusively via the browser-safe environment variable `VITE_API_BASE_URL`. | Host Port `5173`<br/>(`http://localhost:5173`) |
| **Backend Modular Monolith** | Python 3.12, FastAPI, Uvicorn, Pydantic v2, Pydantic Settings | • HTTP request routing and payload validation.<br/>• API versioning under `/api/v1`.<br/>• Application liveness probe (`/health`) and dependency readiness probe (`/health/ready`).<br/>• Centralized structured logging with credential and sensitive DSN masking.<br/>• Cross-Origin Resource Sharing (CORS) enforcement.<br/>• Resilient database session pooling and vector client abstraction. | • Modular monolith architecture (single deployable runtime).<br/>• In Phase 0: strictly provides technical foundation and health probes; zero ML dependencies or domain business logic.<br/>• Must boot and remain operable even when PostgreSQL or ChromaDB is offline. | Host Port `8000`<br/>(`http://localhost:8000`) |
| **Relational Database** | PostgreSQL 16+ (Docker container), SQLAlchemy 2.x, Psycopg 3, Alembic | • Authoritative system of record for all persistent application data (users, workspaces, documents, metadata, study activities, graph entities).<br/>• Enforces referential integrity, cascading deletions, and transactional consistency.<br/>• Alembic schema migration baseline. | • Direct TCP access restricted strictly to backend application code.<br/>• In Phase 0: accepts database health check query (`SELECT 1`); contains zero business tables. | Host Port `5432`<br/>(Docker bridge) |
| **Vector Store** | ChromaDB (pinned official Docker image `chromadb/chroma`), `chromadb.HttpClient` | • High-performance vector similarity search over document chunk embeddings.<br/>• Workspace-scoped vector collection indexing.<br/>• Rebuildable derived index; never the authoritative owner of documents. | • In Phase 0: verified via HTTP heartbeat/liveness probe.<br/>• Contains zero embeddings, collections, or model weights in Phase 0. | Host Port `8001`<br/>(Container Port `8000`) |

---

## 3. Communication Flow & Network Topology

### 3.1 Local Development Topology

During local development, components interact over local host network bindings:
1. **Frontend to Backend**:
   - The React client initiates asynchronous HTTP requests using `fetch` directed to the URL defined by `VITE_API_BASE_URL` (default: `http://localhost:8000/api/v1`).
   - The backend validates the incoming `Origin` header against `FRONTEND_ORIGIN` (default: `http://localhost:5173`) using `fastapi.middleware.cors.CORSMiddleware`.
2. **Backend to PostgreSQL**:
   - The backend connects via TCP over `postgresql+psycopg://` using SQLAlchemy 2.x with lazy connection pooling and `pool_pre_ping=True`.
   - The connection pool does not block backend startup if PostgreSQL is unavailable.
3. **Backend to ChromaDB**:
   - The backend communicates with ChromaDB via HTTP REST calls managed by `chromadb.HttpClient` pointing to `CHROMA_HOST` (default: `localhost`) and `CHROMA_PORT` (default: `8001`).
   - Health is probed using `client.heartbeat()`.

### 3.2 Production Deployment Topology (Target)

In target production deployment (Phase 11):
- A reverse proxy (Caddy / Nginx) handles public ingress on ports `80` (HTTP) and `443` (HTTPS with automated TLS).
- The reverse proxy serves the compiled static frontend bundle and forwards `/api/` and `/health` requests to the internal FastAPI container on port `8000`.
- PostgreSQL and ChromaDB containers reside on an isolated internal Docker bridge network (`knovera_internal_network`) and do not publish host ports to the public Internet.

---

## 4. Modular Monolith Architecture Rationale

Knovera explicitly rejects a distributed microservices pattern for Phase 0 and the core application roadmap.

### 4.1 Why a Modular Monolith?

1. **Elimination of Distributed System Overhead**:
   Microservices introduce substantial complexity: network latency, serialisation overhead, distributed tracing requirements, eventual consistency anomalies, complex deployment pipelines, and failure modes such as network partitions. For Knovera, a modular monolith provides full logical separation without these operational burdens.
2. **Single Transaction Boundary**:
   In Knovera, document ingestion and deletion require synchronised updates across metadata, chunks, citations, and relational entities. In a monolithic database topology, PostgreSQL transactions guarantee atomicity without two-phase commit protocols or complex saga orchestration.
3. **Explicit Python Module Boundaries**:
   Modular monolithic code organisation enforces separation of concerns through explicit Python interfaces, service classes, and Pydantic schemas:
   - Modules reside in dedicated directories under `backend/app/` (e.g., `core/`, `db/`, and future modules `auth/`, `workspaces/`, `documents/`, `rag/`, `graph/`).
   - Cross-module communication occurs strictly through public service functions, schemas, or dependency injection—never through internal private functions or direct ORM coupling.
4. **No Premature Middleware**:
   Knovera explicitly excludes external message brokers (Apache Kafka, RabbitMQ) and distributed memory stores (Redis) in Phase 0. Asynchronous background tasks are handled via PostgreSQL job tables and internal Python concurrency utilities until high-throughput requirements genuinely demand dedicated infrastructure.
5. **No Kubernetes Overhead**:
   Orchestration in development and initial VPS deployment relies on standard `docker-compose.yml`, which is predictable, lightweight, and debuggable on any standard developer workstation or single-node Linux server.

---

## 5. Resilience & Health Check Contract

A critical requirement of Knovera is **graceful degradation**: the FastAPI application must start, remain alive, and serve public requests even when external database dependencies are offline.

### 5.1 Liveness Probe (`GET /health` or `GET /api/v1/health`)
- **Purpose**: Verifies that the FastAPI process is running, responsive, and able to process HTTP requests.
- **Access**: Public (no authentication required).
- **HTTP Status**: Always `200 OK`.
- **Response Format**:
  ```json
  {
    "status": "ok",
    "app": "Knovera",
    "version": "1.0.0",
    "environment": "development"
  }
  ```

### 5.2 Readiness Probe (`GET /health/ready` or `GET /api/v1/health/ready`)
- **Purpose**: Evaluates live connectivity to PostgreSQL and ChromaDB to verify system readiness for functional workloads.
- **Access**: Public (no authentication required; diagnostic output is strictly masked).
- **HTTP Status**:
  - `200 OK`: Both PostgreSQL and ChromaDB respond affirmatively.
  - `503 Service Unavailable`: Either or both dependencies fail to respond or return an error.
- **Degraded Operation Behavior**:
  - The application process does not terminate or enter crash loops if Docker containers are offline.
  - The frontend dynamically reflects the degraded connectivity state, informing the user while keeping the interface interactive.
- **Healthy Response (200 OK)**:
  ```json
  {
    "status": "ready",
    "services": {
      "database": {
        "status": "connected",
        "latency_ms": 1.25
      },
      "vector_store": {
        "status": "connected",
        "latency_ms": 2.10
      }
    }
  }
  ```
- **Degraded Response (503 Service Unavailable)**:
  ```json
  {
    "status": "not_ready",
    "services": {
      "database": {
        "status": "disconnected",
        "error": "Database service unavailable or unreachable"
      },
      "vector_store": {
        "status": "disconnected",
        "error": "Vector store service unavailable or unreachable"
      }
    }
  }
  ```

---

## 6. Security Considerations & Protections

Security in Knovera is foundational and enforced from Phase 0:

1. **Environment Secret Isolation**:
   - Application secrets, database passwords, and configuration tokens are loaded exclusively from local environment variables or a local uncommitted `.env` file via `pydantic-settings`.
   - `.env` is rigorously excluded from version control via `.gitignore`.
   - Repository templates (`.env.example` at root and `frontend/.env.example`) provide safe dummy defaults and comprehensive documentation without exposing production credentials.
2. **Frontend Information Leakage Prevention**:
   - The React frontend Vite bundle is compiled for browser execution. Only environment variables explicitly prefixed with `VITE_` are exposed to the client.
   - Private server secrets (database connection strings, encryption keys, admin credentials) must never bear the `VITE_` prefix and are strictly banned from frontend code.
3. **Diagnostic Sanitization & Credential Masking**:
   - Public health endpoints (`/health/ready`) and error handlers must never return raw database connection strings, passwords, usernames, internal IP addresses, or Python stack traces.
   - Any internal connection exceptions caught during database or vector store health checks are mapped to generic, safe status strings (e.g., `"Database service unavailable"`).
4. **Network & Service Isolation**:
   - In production topology, database and vector store ports are bound strictly to internal container networks. Public ingress is granted solely to the web reverse proxy.
5. **Non-Root Execution in Containers**:
   - Docker container configurations employ non-root service accounts where applicable to limit blast radius in containerized environments.
6. **CORS Restrictions**:
   - The FastAPI backend enforces Cross-Origin Resource Sharing rules, permitting access exclusively from authorized frontend origins (e.g., `http://localhost:5173` in development).

---

## 7. Strict Phase 0 Boundary (Non-ML Foundation)

Phase 0 establishes the engineering and architectural foundation. It deliberately and strictly bounds scope to avoid premature complexity or bloated dependencies:

### 7.1 What Phase 0 Delivers
- Repository scaffolding, Git configuration, and directory layout separating `frontend/` and `backend/`.
- Python 3.12 virtual environment (`.venv`) and clean, minimal `backend/requirements.txt`.
- FastAPI backend with Pydantic Settings, centralized logging, CORS, `/health`, and `/health/ready`.
- React + TypeScript SPA with Vite, Tailwind CSS, semantic design tokens, and a landing view with real-time connectivity status.
- Docker Compose configuration for PostgreSQL 16+ and pinned ChromaDB with persistent volumes.
- Safe environment configuration templates (`.env.example` and `frontend/.env.example`).
- Comprehensive automated test suite for backend health and settings.

### 7.2 What is Explicitly Prohibited in Phase 0
- **NO Heavyweight ML Frameworks**: Packages such as `torch`, `torchvision`, `torchaudio`, `tensorflow`, `transformers`, `sentence-transformers`, `scikit-learn`, `spacy`, or `nltk` are strictly prohibited in Phase 0 `requirements.txt`.
- **NO External AI / Paid LLM SDKs**: No dependencies on `openai`, `anthropic`, `cohere`, or `google-generativeai`. No API keys are required to run or test Phase 0.
- **NO Document Parsing Libraries**: No `PyMuPDF` (`fitz`), `python-docx`, or `python-pptx` (deferred to Phase 2).
- **NO Authentication Business Logic**: No user registration, login, JWT issuance, or password hashing logic (deferred to Phase 1).
- **NO Domain Relational Tables**: No domain tables (users, workspaces, documents, chunks) or migrations applied in PostgreSQL. Alembic is configured to an empty baseline.
- **NO Mocked or Premature AI Features**: No placeholder vector search, fake RAG answers, or dummy quiz generation.
