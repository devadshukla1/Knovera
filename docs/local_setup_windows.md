# Knovera — Native Windows Setup & Operations Guide

> **Turn Information into Intelligence.**  
> Native Windows (10/11 x64) Production & Development Environment.  
> **100% Docker-Free Architecture.**

---

## 1. Native Architecture Overview

Knovera runs completely natively on Windows without Docker, Docker Desktop, or container hypervisors:

```
┌────────────────────────────────────────────────────────┐
│             Knovera Frontend (React + Vite)            │
│               http://127.0.0.1:5173                    │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP / REST / JSON
                            ▼
┌────────────────────────────────────────────────────────┐
│             Knovera Backend (FastAPI ASGI)             │
│               http://127.0.0.1:8000                    │
│             Entry: backend/app/main.py                 │
└─────────────┬────────────────────────────┬─────────────┘
              │ TCP :5432                  │ HTTP :8001
              ▼                            ▼
┌───────────────────────────┐┌───────────────────────────┐
│   Native PostgreSQL 16    ││   Native ChromaDB 1.5.9   │
│   Windows Process/Service ││   Native Python Process   │
│   Auth DB: knovera        ││   Path: %LOCALAPPDATA%    │
└───────────────────────────┘└───────────────────────────┘
```

| Service | Host & Port | Technology | Working Directory / Persistence Path |
| :--- | :--- | :--- | :--- |
| **Frontend UI** | `http://127.0.0.1:5173` | React 18, Vite 6, TypeScript | `frontend/` |
| **Backend API** | `http://127.0.0.1:8000` | FastAPI, Uvicorn, Python 3.12 | `backend/` |
| **Relational Database** | `127.0.0.1:5432` | PostgreSQL 16.4 (64-bit) | `%LOCALAPPDATA%\Knovera\data\postgres` |
| **Vector Store** | `http://127.0.0.1:8001` | ChromaDB 1.5.9 HTTP Server | `%LOCALAPPDATA%\Knovera\data\chroma` |

---

## 2. Prerequisites

1. **Operating System:** Windows 10/11 (64-bit AMD64).
2. **Python:** Python 3.12.x installed and configured in `.venv`.
3. **Node.js:** Node.js >= 20.x and npm >= 10.x.
4. **Git:** Git for Windows.
5. **PostgreSQL 16 Binaries:** Located in `%LOCALAPPDATA%\Programs\PostgreSQL\16\bin` or on system `PATH`.

---

## 3. Quick Start — Native PowerShell Commands

The entire platform is automated using verified scripts in `scripts/windows/`:

```powershell
# 1. First-time setup (Initializes DB, directories & runs migrations)
.\scripts\windows\setup.ps1

# 2. Start all services (PostgreSQL, ChromaDB, FastAPI, Frontend)
.\scripts\windows\start.ps1

# 3. Check health and status of all components
.\scripts\windows\status.ps1

# 4. View service logs
.\scripts\windows\logs.ps1 -Service all -Tail 30

# 5. Stop services safely
.\scripts\windows\stop.ps1
```

---

## 4. Component Details & Manual Configuration

### 4.1 Native PostgreSQL 16
- **Binaries:** `%LOCALAPPDATA%\Programs\PostgreSQL\16\bin`
- **Data Cluster:** `%LOCALAPPDATA%\Knovera\data\postgres`
- **Port:** `5432`
- **Database Name:** `knovera`
- **Application User:** `knovera_app`
- **Password:** `change_me_locally`
- **Manual Start:**
  ```powershell
  & "$env:LOCALAPPDATA\Programs\PostgreSQL\16\bin\postgres.exe" -D "$env:LOCALAPPDATA\Knovera\data\postgres"
  ```
- **Manual Check:**
  ```powershell
  & "$env:LOCALAPPDATA\Programs\PostgreSQL\16\bin\pg_isready.exe" -h 127.0.0.1 -p 5432
  ```

### 4.2 Native ChromaDB
- **Process:** Chroma CLI server runner inside `.venv`
- **Persistence Path:** `%LOCALAPPDATA%\Knovera\data\chroma`
- **Port:** `8001`
- **Manual Start:**
  ```powershell
  .venv\Scripts\chroma.exe run --host 127.0.0.1 --port 8001 --path "$env:LOCALAPPDATA\Knovera\data\chroma"
  ```
- **Heartbeat Verification:**
  ```powershell
  curl.exe http://127.0.0.1:8001/api/v2/heartbeat
  ```

### 4.3 Database Migrations (Alembic)
Apply database migrations directly using the project virtual environment:
```powershell
# Run all pending migrations to head
.venv\Scripts\alembic.exe -c backend/alembic.ini upgrade head

# Inspect current revision
.venv\Scripts\alembic.exe -c backend/alembic.ini current
```

### 4.4 FastAPI Backend
- **Entrypoint:** `backend.app.main:app`
- **Host & Port:** `127.0.0.1:8000`
- **Manual Start:**
  ```powershell
  .venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
  ```
- **Endpoints:**
  - OpenAPI Swagger: `http://127.0.0.1:8000/docs`
  - Liveness Probe: `http://127.0.0.1:8000/health`
  - Readiness Probe: `http://127.0.0.1:8000/health/ready`

### 4.5 React + Vite Frontend
- **Framework:** React 18 with Vite 6.4.5 and TypeScript
- **Port:** `5173`
- **Manual Start:**
  ```powershell
  cd frontend
  npm run dev -- --host 127.0.0.1 --port 5173
  ```
- **UI Access:** `http://127.0.0.1:5173`

---

## 5. Persistent Storage & Backups

All mutable state is preserved in stable Windows directories outside OneDrive syncing:
- **Relational Data:** `%LOCALAPPDATA%\Knovera\data\postgres\`
- **Vector Embeddings:** `%LOCALAPPDATA%\Knovera\data\chroma\`
- **Uploaded Documents:** `./storage/documents/`
- **Model Caches:** `./storage/model_cache/`
- **Application Logs:** `%LOCALAPPDATA%\Knovera\logs\`

### Backup PostgreSQL
```powershell
$pgBin = "$env:LOCALAPPDATA\Programs\PostgreSQL\16\bin"
& "$pgBin\pg_dump.exe" -U knovera_app -h 127.0.0.1 -p 5432 -d knovera -F c -f "$env:LOCALAPPDATA\Knovera\backups\knovera_backup.dump"
```

### Restore PostgreSQL
```powershell
$pgBin = "$env:LOCALAPPDATA\Programs\PostgreSQL\16\bin"
& "$pgBin\pg_restore.exe" -U knovera_app -h 127.0.0.1 -p 5432 -d knovera --clean "$env:LOCALAPPDATA\Knovera\backups\knovera_backup.dump"
```

---

## 6. Troubleshooting & Diagnostics

| Problem | Cause | Resolution |
| :--- | :--- | :--- |
| **Port 5432 Conflict** | Another PostgreSQL instance running | Check with `Get-NetTCPConnection -LocalPort 5432`. Stop competing service or adjust `POSTGRES_PORT` in `.env`. |
| **Port 8001 / 8000 Conflict** | Stale background process | Run `.\scripts\windows\stop.ps1` to terminate lingering processes. |
| **PostgreSQL Socket Timeout** | Server not started | Run `.\scripts\windows\start.ps1` or check `%LOCALAPPDATA%\Knovera\logs\postgres.log`. |
| **ChromaDB Connection Error** | Server process stopped | Check heartbeat at `http://127.0.0.1:8001/api/v2/heartbeat`. Verify path in `%LOCALAPPDATA%\Knovera\data\chroma`. |
| **Vite DOM Parser Warning** | PowerShell 5.1 WebRequest | Use `-UseBasicParsing` switch in PowerShell web requests. |
