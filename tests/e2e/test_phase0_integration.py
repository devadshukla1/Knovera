"""Phase 0 Comprehensive End-to-End (E2E) Integration Test Suite for Knovera.

Covers the 4 Verification Tiers:
- Tier 1: System Contracts (Python 3.12, .gitignore secret isolation, package purity,
          docker-compose syntax & volume contracts, .env.example completeness).
- Tier 2: Backend Integration (FastAPI liveness 200, readiness 200/503 graceful degradation,
          CORS preflight & origin isolation, SQLAlchemy session binding, ChromaDB lazy init,
          zero credential/traceback leakage).
- Tier 3: Frontend Build & Contract Verification (Vite production bundle in frontend/dist,
          browser-safe VITE_ environment safety, API base URL fallback contract).
- Tier 4: Cross-System Health Coherence (FastAPI Pydantic models matching TypeScript
          health.ts contracts 1:1, dual route parity at /health and /api/v1/health).
"""

import importlib.metadata
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Set
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
import yaml

# Repository root directory anchor
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.api.v1.endpoints.health import (
    LivenessResponse,
    ReadinessResponse,
    ServiceStatus,
)
from backend.app.core.config import get_settings
from backend.app.db.base import Base
from backend.app.db.chroma import check_chroma_connectivity, get_chroma_client
from backend.app.db.session import (
    SessionLocal,
    check_database_connectivity,
    engine,
)
from backend.app.main import app


# ==============================================================================
# Tier 1: System Contracts
# ==============================================================================
class TestTier1SystemContracts:
    """Verifies low-level platform, repository, environment, and dependency contracts."""

    def test_python_version_and_venv_runtime(self) -> None:
        """Asserts Python runtime is strictly 3.12.x inside .venv."""
        major, minor = sys.version_info[:2]
        assert (major, minor) == (3, 12), (
            f"Expected Python 3.12 runtime, but detected {major}.{minor} ({sys.executable})"
        )
        # Verify execution inside a virtual environment
        assert sys.prefix != getattr(sys, "base_prefix", sys.prefix), (
            f"Test runner must execute inside a virtual environment, but sys.prefix == base_prefix ({sys.prefix})"
        )
        # Verify .venv directory exists at repository root
        venv_dir = ROOT_DIR / ".venv"
        assert venv_dir.is_dir(), f"Expected virtual environment at {venv_dir}"

    def test_gitignore_enforces_secret_and_artifact_isolation(self) -> None:
        """Verifies git ignore rules for sensitive files, virtual environments, and data."""
        targets_to_check = [
            ".env",
            "frontend/.env",
            ".venv/",
            "node_modules/",
            "postgres_data/",
            "chroma_data/",
            "storage/",
        ]
        cmd = ["git", "check-ignore", "-v"] + targets_to_check
        result = subprocess.run(
            cmd,
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"git check-ignore failed: {result.stderr}"

        ignored_lines = result.stdout.strip().splitlines()
        ignored_paths = [line.split("\t")[-1].strip() for line in ignored_lines if "\t" in line]

        for target in targets_to_check:
            clean_target = target.rstrip("/")
            assert any(
                clean_target in p or p.rstrip("/") == clean_target
                for p in ignored_paths
            ), f"Target '{target}' is not properly ignored by .gitignore rules: {result.stdout}"

    def test_gitignore_whitelists_safe_env_templates(self) -> None:
        """Verifies that .env.example templates are tracked and whitelisted."""
        templates = [".env.example", "frontend/.env.example"]
        cmd = ["git", "check-ignore", "-v", "--no-index"] + templates
        result = subprocess.run(
            cmd,
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"git check-ignore failed: {result.stderr}"

        # Whitelisted files should trigger negation rules starting with '!'
        for line in result.stdout.strip().splitlines():
            if line:
                rule = line.split("\t")[0]
                assert "!" in rule, (
                    f"Expected negation whitelist rule for template, but got: {line}"
                )

    def test_package_purity_zero_ml_and_cloud_ai_sdks(self) -> None:
        """Asserts zero paid cloud AI SDKs or redundant frameworks are installed."""
        prohibited_packages = {
            "tensorflow",
            "keras",
            "flax",
            "jax",
            "openai",
            "anthropic",
            "cohere",
            "langchain",
            "llama-index",
        }

        installed_dists = {
            dist.metadata["Name"].lower()
            for dist in importlib.metadata.distributions()
            if "Name" in dist.metadata
        }

        violations = prohibited_packages.intersection(installed_dists)
        assert not violations, (
            f"Package purity violation: found prohibited ML/AI packages in Phase 0: {violations}"
        )

        # Also inspect backend/requirements.txt directly
        reqs_file = ROOT_DIR / "backend" / "requirements.txt"
        assert reqs_file.is_file(), f"Missing requirements file at {reqs_file}"
        reqs_text = reqs_file.read_text(encoding="utf-8").lower()

        for prohibited in prohibited_packages:
            pattern = rf"^\s*{re.escape(prohibited)}(\[|\b|[<>=!~])"
            assert not re.search(pattern, reqs_text, re.MULTILINE), (
                f"Prohibited package '{prohibited}' declared in backend/requirements.txt"
            )

    def test_docker_compose_specification_and_service_contracts(self) -> None:
        """Validates docker-compose.yml syntax, required services, ports, and persistent volumes."""
        compose_file = ROOT_DIR / "docker-compose.yml"
        assert compose_file.is_file(), f"docker-compose.yml missing at {compose_file}"

        with open(compose_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert "services" in data, "docker-compose.yml missing 'services' block"
        services = data["services"]

        # Validate PostgreSQL service
        assert "postgres" in services, "Missing 'postgres' service in docker-compose.yml"
        pg_svc = services["postgres"]
        assert "image" in pg_svc and "postgres:16" in pg_svc["image"], (
            f"Postgres service must use postgres:16 image, got {pg_svc.get('image')}"
        )
        assert "volumes" in pg_svc and any("postgres_data" in v for v in pg_svc["volumes"])
        assert "ports" in pg_svc and any("5432" in str(p) for p in pg_svc["ports"])
        assert "healthcheck" in pg_svc and "test" in pg_svc["healthcheck"]

        # Validate ChromaDB service
        assert "chroma" in services, "Missing 'chroma' service in docker-compose.yml"
        chroma_svc = services["chroma"]
        assert "image" in chroma_svc and "chromadb/chroma:" in chroma_svc["image"], (
            f"Chroma service must use official pinned image, got {chroma_svc.get('image')}"
        )
        assert "volumes" in chroma_svc and any("chroma_data" in v for v in chroma_svc["volumes"])
        assert "ports" in chroma_svc and any("8001" in str(p) for p in chroma_svc["ports"])
        assert "healthcheck" in chroma_svc and "test" in chroma_svc["healthcheck"]

        # Validate volumes and networks
        assert "volumes" in data, "Missing 'volumes' block in docker-compose.yml"
        assert "postgres_data" in data["volumes"], "Missing 'postgres_data' volume definition"
        assert "chroma_data" in data["volumes"], "Missing 'chroma_data' volume definition"
        assert "networks" in data and "knovera_network" in data["networks"], (
            "Missing 'knovera_network' bridge network definition"
        )

    def test_env_example_templates_completeness(self) -> None:
        """Verifies root and frontend .env.example contain all expected keys."""
        root_env = ROOT_DIR / ".env.example"
        assert root_env.is_file(), f"Missing root .env.example at {root_env}"
        root_content = root_env.read_text(encoding="utf-8")

        required_root_keys = [
            "APP_ENV",
            "APP_PORT",
            "FRONTEND_ORIGIN",
            "POSTGRES_HOST",
            "POSTGRES_PORT",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "DATABASE_URL",
            "CHROMA_HOST",
            "CHROMA_PORT",
            "STORAGE_BACKEND",
        ]
        for key in required_root_keys:
            assert f"{key}=" in root_content, f"Key '{key}' missing from root .env.example"

        frontend_env = ROOT_DIR / "frontend" / ".env.example"
        assert frontend_env.is_file(), f"Missing frontend .env.example at {frontend_env}"
        frontend_content = frontend_env.read_text(encoding="utf-8")
        assert "VITE_API_BASE_URL=" in frontend_content, (
            "VITE_API_BASE_URL missing from frontend/.env.example"
        )


# ==============================================================================
# Tier 2: Backend Integration
# ==============================================================================
class TestTier2BackendIntegration:
    """Verifies FastAPI backend operations, health probes, resilience, and security."""

    @pytest.fixture(scope="class")
    def client(self) -> TestClient:
        return TestClient(app)

    def test_liveness_endpoints_root_and_versioned(self, client: TestClient) -> None:
        """Verifies GET /health and GET /api/v1/health return 200 with application metadata."""
        for endpoint in ["/health", "/api/v1/health"]:
            response = client.get(endpoint)
            assert response.status_code == 200, (
                f"Expected 200 from {endpoint}, got {response.status_code}"
            )
            data = response.json()
            assert data["status"] == "ok"
            assert data["app"] == "Knovera"
            assert data["version"] == "1.0.0"
            assert "environment" in data

    def test_readiness_probe_healthy_services_simulation(self, client: TestClient) -> None:
        """Verifies readiness probe returns 200 OK when both DB and Chroma are healthy."""
        with patch(
            "backend.app.api.v1.endpoints.health.check_database_connectivity",
            return_value=(True, 1.42, None),
        ), patch(
            "backend.app.api.v1.endpoints.health.check_chroma_connectivity",
            return_value=(True, 2.15, None),
        ):
            for endpoint in ["/health/ready", "/api/v1/health/ready"]:
                response = client.get(endpoint)
                assert response.status_code == 200, (
                    f"Expected 200 from {endpoint}, got {response.status_code}"
                )
                data = response.json()
                assert data["status"] == "ready"
                assert data["services"]["database"]["status"] == "connected"
                assert data["services"]["database"]["latency_ms"] == 1.42
                assert data["services"]["vector_store"]["status"] == "connected"
                assert data["services"]["vector_store"]["latency_ms"] == 2.15

    def test_readiness_probe_degraded_service_failure_simulation(self, client: TestClient) -> None:
        """Verifies readiness probe returns 503 with disconnected status when services fail."""
        # 1. Database down, Chroma up
        with patch(
            "backend.app.api.v1.endpoints.health.check_database_connectivity",
            return_value=(False, None, "Database service unavailable"),
        ), patch(
            "backend.app.api.v1.endpoints.health.check_chroma_connectivity",
            return_value=(True, 1.85, None),
        ):
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert data["services"]["database"]["status"] == "disconnected"
            assert data["services"]["database"]["error"] == "Database service unavailable"
            assert data["services"]["vector_store"]["status"] == "connected"

        # 2. Database up, Chroma down
        with patch(
            "backend.app.api.v1.endpoints.health.check_database_connectivity",
            return_value=(True, 1.20, None),
        ), patch(
            "backend.app.api.v1.endpoints.health.check_chroma_connectivity",
            return_value=(False, None, "Vector store service unavailable"),
        ):
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert data["services"]["database"]["status"] == "connected"
            assert data["services"]["vector_store"]["status"] == "disconnected"

        # 3. Both services down
        with patch(
            "backend.app.api.v1.endpoints.health.check_database_connectivity",
            return_value=(False, None, "Database service unavailable"),
        ), patch(
            "backend.app.api.v1.endpoints.health.check_chroma_connectivity",
            return_value=(False, None, "Vector store service unavailable"),
        ):
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert data["services"]["database"]["status"] == "disconnected"
            assert data["services"]["vector_store"]["status"] == "disconnected"

    def test_readiness_probe_live_socket_handling_graceful_degradation(
        self, client: TestClient
    ) -> None:
        """Verifies live un-mocked readiness endpoint executes without throwing 500 or crashing."""
        response = client.get("/health/ready")
        assert response.status_code in (200, 503), (
            f"Expected 200 or 503 graceful status, got {response.status_code}"
        )
        data = response.json()
        assert "status" in data
        assert "services" in data
        assert "database" in data["services"]
        assert "vector_store" in data["services"]

    def test_cors_preflight_and_allowed_origins(self, client: TestClient) -> None:
        """Verifies CORS preflight headers and origin restriction."""
        settings = get_settings()

        # Preflight from configured frontend origin
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": settings.FRONTEND_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin") == settings.FRONTEND_ORIGIN
        )

        # Preflight from disallowed origin
        response_disallowed = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://unauthorized-attacker-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in response_disallowed.headers

    def test_sqlalchemy_session_and_declarative_base(self) -> None:
        """Verifies SQLAlchemy SessionLocal binding, pool_pre_ping, and DeclarativeBase metadata."""
        assert engine.pool._pre_ping is True, "SQLAlchemy engine must configure pool_pre_ping=True"

        # Instantiate a session
        session = SessionLocal()
        try:
            assert session.is_active is True
            assert session.bind is engine
        finally:
            session.close()

        # Check Base metadata
        assert hasattr(Base, "metadata"), "Base must have DeclarativeBase metadata"

    def test_chroma_client_lazy_initialization(self) -> None:
        """Verifies Chroma client lazy initialization and error containment."""
        client = get_chroma_client()
        # Either returns a valid client or None if unreachable
        if client is not None:
            assert hasattr(client, "heartbeat")

        # check_chroma_connectivity should return 3-tuple without throwing uncaught exceptions
        connected, latency, error = check_chroma_connectivity()
        assert isinstance(connected, bool)
        if connected:
            assert latency is not None and latency >= 0
            assert error is None
        else:
            assert error is not None

    def test_zero_credential_leakage_in_responses(self, client: TestClient) -> None:
        """Ensures that no health response contains passwords, connection URIs, or tracebacks."""
        forbidden_substrings = [
            "change_me_locally",
            "postgresql+psycopg://",
            "POSTGRES_PASSWORD",
            "AUTH_SECRET_KEY",
            "Traceback (most recent call last)",
            "File \"c:\\Users\\",
        ]

        endpoints = ["/health", "/api/v1/health", "/health/ready", "/api/v1/health/ready"]
        for ep in endpoints:
            res = client.get(ep)
            raw_text = res.text
            for forbidden in forbidden_substrings:
                assert forbidden not in raw_text, (
                    f"Security leak detected on endpoint {ep}: found forbidden substring '{forbidden}'"
                )


# ==============================================================================
# Tier 3: Frontend Build & Contract Verification
# ==============================================================================
class TestTier3FrontendBuildAndContract:
    """Verifies frontend bundle artifacts, safety configuration, and API service contracts."""

    def test_frontend_production_bundle_exists(self) -> None:
        """Verifies frontend/dist/ contains bundled index.html, JS, and CSS files."""
        dist_dir = ROOT_DIR / "frontend" / "dist"
        assert dist_dir.is_dir(), f"Frontend dist directory missing at {dist_dir}"

        index_html = dist_dir / "index.html"
        assert index_html.is_file(), f"Missing production index.html at {index_html}"
        html_content = index_html.read_text(encoding="utf-8")
        assert len(html_content) > 100, "dist/index.html appears truncated or empty"
        assert 'id="root"' in html_content, "dist/index.html missing '#root' mounting element"

        assets_dir = dist_dir / "assets"
        assert assets_dir.is_dir(), f"Missing dist/assets directory at {assets_dir}"

        js_bundles = list(assets_dir.glob("*.js"))
        css_bundles = list(assets_dir.glob("*.css"))
        assert len(js_bundles) >= 1, "No compiled JavaScript chunks found in dist/assets"
        assert len(css_bundles) >= 1, "No compiled CSS bundles found in dist/assets"

    def test_frontend_env_example_safety(self) -> None:
        """Verifies frontend/.env.example contains only browser-safe VITE_ variables."""
        frontend_env = ROOT_DIR / "frontend" / ".env.example"
        assert frontend_env.is_file()

        lines = frontend_env.read_text(encoding="utf-8").splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                key = stripped.split("=")[0].strip()
                assert key.startswith("VITE_"), (
                    f"Unsafe non-VITE variable in frontend/.env.example: '{key}'"
                )
                assert "POSTGRES" not in key
                assert "SECRET" not in key
                assert "PASSWORD" not in key

    def test_frontend_api_base_url_contract(self) -> None:
        """Verifies frontend API service resolves VITE_API_BASE_URL with safe fallback."""
        api_ts = ROOT_DIR / "frontend" / "src" / "services" / "api.ts"
        assert api_ts.is_file(), f"api.ts missing at {api_ts}"
        content = api_ts.read_text(encoding="utf-8")

        assert "http://localhost:8000/api/v1" in content, (
            "Default API base URL contract http://localhost:8000/api/v1 missing in api.ts"
        )
        assert "VITE_API_BASE_URL" in content, (
            "VITE_API_BASE_URL environment variable reference missing in api.ts"
        )


# ==============================================================================
# Tier 4: Cross-System Health Coherence
# ==============================================================================
class TestTier4CrossSystemHealthCoherence:
    """Verifies exact schema alignment between backend FastAPI models and frontend TypeScript types."""

    def test_liveness_schema_coherence_between_fastapi_and_typescript(self) -> None:
        """Asserts exact 1:1 match of LivenessResponse fields between Python and TypeScript."""
        backend_fields: Set[str] = set(LivenessResponse.model_fields.keys())
        expected_fields = {"status", "app", "version", "environment"}
        assert backend_fields == expected_fields, (
            f"Backend LivenessResponse schema changed: {backend_fields} != {expected_fields}"
        )

        health_ts = ROOT_DIR / "frontend" / "src" / "types" / "health.ts"
        assert health_ts.is_file(), f"health.ts missing at {health_ts}"
        content = health_ts.read_text(encoding="utf-8")

        # Extract interface LivenessResponse block
        match = re.search(
            r"export\s+interface\s+LivenessResponse\s*\{([^}]+)\}",
            content,
            re.DOTALL,
        )
        assert match, "LivenessResponse interface not found in frontend/src/types/health.ts"

        ts_block = match.group(1)
        ts_fields = set(re.findall(r"(\w+)\s*:", ts_block))
        assert backend_fields == ts_fields, (
            f"Schema mismatch: backend fields {backend_fields} vs TypeScript fields {ts_fields}"
        )

    def test_readiness_schema_coherence_between_fastapi_and_typescript(self) -> None:
        """Asserts exact match of ReadinessResponse & ServiceStatus fields with TypeScript."""
        backend_readiness_fields: Set[str] = set(ReadinessResponse.model_fields.keys())
        assert backend_readiness_fields == {"status", "services"}

        backend_service_fields: Set[str] = set(ServiceStatus.model_fields.keys())
        assert backend_service_fields == {"status", "latency_ms", "error"}

        health_ts = ROOT_DIR / "frontend" / "src" / "types" / "health.ts"
        content = health_ts.read_text(encoding="utf-8")

        # Extract top-level properties of ReadinessResponse
        match_readiness = re.search(
            r"export\s+interface\s+ReadinessResponse\s*\{([\s\S]*?\n\})",
            content,
        )
        assert match_readiness, "ReadinessResponse interface not found in health.ts"
        ts_readiness_block = match_readiness.group(1)
        # Match top-level properties (indented by 2 spaces directly under interface)
        ts_top_properties = set(re.findall(r"^\s{2}(\w+)\s*:", ts_readiness_block, re.MULTILINE))
        assert {"status", "services"} == ts_top_properties

        # Also assert services contains database and vector_store keys
        assert "database" in ts_readiness_block, "ReadinessResponse.services missing database"
        assert "vector_store" in ts_readiness_block, "ReadinessResponse.services missing vector_store"

        # Extract ServiceDependencyStatus
        match_service = re.search(
            r"export\s+interface\s+ServiceDependencyStatus\s*\{([^}]+)\}",
            content,
            re.DOTALL,
        )
        assert match_service, "ServiceDependencyStatus interface not found in health.ts"
        ts_service_block = match_service.group(1)
        ts_service_fields = set(re.findall(r"(\w+)\s*\??:", ts_service_block))
        assert {"status", "latency_ms", "error"} == ts_service_fields

    def test_dual_route_access_coherence(self) -> None:
        """Verifies that root probes (/health, /health/ready) match versioned probes (/api/v1/...)."""
        client = TestClient(app)

        # Liveness route parity
        res_root = client.get("/health")
        res_v1 = client.get("/api/v1/health")
        assert res_root.status_code == res_v1.status_code == 200
        assert res_root.json() == res_v1.json()

        # Readiness route parity under mock
        with patch(
            "backend.app.api.v1.endpoints.health.check_database_connectivity",
            return_value=(True, 1.1, None),
        ), patch(
            "backend.app.api.v1.endpoints.health.check_chroma_connectivity",
            return_value=(True, 1.9, None),
        ):
            ready_root = client.get("/health/ready")
            ready_v1 = client.get("/api/v1/health/ready")
            assert ready_root.status_code == ready_v1.status_code == 200
            assert ready_root.json() == ready_v1.json()
