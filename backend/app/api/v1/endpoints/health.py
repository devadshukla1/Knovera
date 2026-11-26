"""Health check endpoints for Knovera.

Provides:
- GET /health (Liveness): Validates FastAPI process is operational.
- GET /health/ready (Readiness): Validates PostgreSQL and ChromaDB connectivity,
  returning 503 on service degradation without exposing sensitive credentials or tracebacks.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional
from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from backend.app.core.config import get_settings
from backend.app.db.session import check_database_connectivity
from backend.app.db.chroma import check_chroma_connectivity

router = APIRouter()
settings = get_settings()


class LivenessResponse(BaseModel):
    """Liveness probe response schema."""
    status: str = Field(..., examples=["ok"])
    app: str = Field(..., examples=["Knovera"])
    version: str = Field(..., examples=["1.0.0"])
    environment: str = Field(..., examples=["development"])


class ServiceStatus(BaseModel):
    """Individual service readiness status."""
    status: str = Field(..., examples=["connected"])
    latency_ms: Optional[float] = Field(default=None, examples=[1.45])
    error: Optional[str] = Field(default=None, examples=["Database service unavailable"])


class ReadinessResponse(BaseModel):
    """Readiness probe aggregated response schema."""
    status: str = Field(..., examples=["ready"])
    services: Dict[str, ServiceStatus]


@router.get(
    "/health",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Application liveness probe",
    description="Returns 200 OK if the FastAPI application process is up and running.",
)
def get_liveness() -> LivenessResponse:
    """Returns application liveness state."""
    return LivenessResponse(
        status="ok",
        app="Knovera",
        version="1.0.0",
        environment=settings.APP_ENV,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Dependency readiness probe",
    description="Verifies active connectivity to PostgreSQL and ChromaDB services.",
    responses={
        200: {
            "description": "All dependencies are healthy and reachable.",
            "model": ReadinessResponse,
        },
        503: {
            "description": "One or more dependencies are unreachable.",
            "model": ReadinessResponse,
        },
    },
)
def get_readiness(response: Response) -> ReadinessResponse:
    """Verifies relational database and vector store connectivity."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_db = executor.submit(check_database_connectivity)
        f_chroma = executor.submit(check_chroma_connectivity)
        db_connected, db_latency, db_error = f_db.result()
        chroma_connected, chroma_latency, chroma_error = f_chroma.result()

    services: Dict[str, ServiceStatus] = {}

    if db_connected:
        services["database"] = ServiceStatus(status="connected", latency_ms=db_latency)
    else:
        services["database"] = ServiceStatus(
            status="disconnected",
            error=db_error or "Database service unavailable",
        )

    if chroma_connected:
        services["vector_store"] = ServiceStatus(
            status="connected", latency_ms=chroma_latency
        )
    else:
        services["vector_store"] = ServiceStatus(
            status="disconnected",
            error=chroma_error or "Vector store service unavailable",
        )

    is_ready = db_connected and chroma_connected

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="not_ready", services=services)

    return ReadinessResponse(status="ready", services=services)
