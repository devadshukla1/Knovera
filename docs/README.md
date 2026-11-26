# Knovera — Project Specification Set

This folder contains the six baseline documents for the Knovera AI-powered Knowledge Intelligence Platform.

| File | Purpose |
|---|---|
| [prd.md](prd.md) | Product scope: what Knovera does, for whom, priorities, user stories, acceptance criteria, and out-of-scope items |
| [trd.md](trd.md) | Technical implementation: exact stack, architecture, authentication, integrations, security, and hosting target |
| [app_flow.md](app_flow.md) | Routes, user journeys, button behaviour, redirects, and UI states |
| [design_brief.md](design_brief.md) | Brand direction, colour tokens, typography, layout, components, themes, and accessibility |
| [schema.md](schema.md) | PostgreSQL data model, relationships, RLS policies, ChromaDB metadata, deletion, and API contract |
| [implementation_plan.md](implementation_plan.md) | Phase 0–11 roadmap, chunks, acceptance criteria, tests, and phase gates |

## Baseline decisions

- Product name: **Knovera**
- Tagline: **Turn Information into Intelligence.**
- Frontend: React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- Backend: Python 3.12.x + FastAPI
- Relational database: PostgreSQL
- Vector database: ChromaDB
- Architecture: modular monolith with a separate worker process where needed
- Authentication: application-managed email/password with Argon2id and rotating refresh sessions
- Initial deployment target: Ubuntu 24.04 LTS Docker-capable VPS, Docker Compose, Caddy, persistent data volumes

## Instruction for implementation agents

Treat these documents as a coordinated specification. Do not silently replace frameworks, databases, authentication, storage, routes, or scope. When a conflict or missing decision is found, report it and propose a documented change before implementing a different architecture. Planned features must not be represented as implemented.
