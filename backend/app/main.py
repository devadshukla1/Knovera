"""Knovera FastAPI main application entrypoint and factory.

Initializes FastAPI application with centralized logging, CORS middleware,
and mounts both root-level and versioned (/api/v1) health and API routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.endpoints import health
from backend.app.api.v1.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.logging import setup_logging


def create_app() -> FastAPI:
    """Application factory for the Knovera FastAPI service."""
    settings = get_settings()

    # Configure structured logging with credential sanitization
    setup_logging(settings.LOG_LEVEL)

    application = FastAPI(
        title="Knovera API",
        version="1.0.0",
        description="AI-powered knowledge intelligence platform for students and researchers.",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure Cross-Origin Resource Sharing (CORS)
    allowed_origins = list(dict.fromkeys([
        settings.FRONTEND_ORIGIN,
        "http://localhost",
        "http://localhost:80",
        "http://localhost:3000",
        "http://localhost:4173",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1",
        "http://127.0.0.1:80",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]))
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    @application.on_event("startup")
    def on_startup() -> None:
        """Ensure database schemas and local owner identity are provisioned on startup."""
        try:
            import backend.app.models  # noqa: F401
            from backend.app.db.base import Base
            from backend.app.db.session import engine, SessionLocal
            from backend.app.core.local_user import get_or_create_local_user
            Base.metadata.create_all(bind=engine)
            with SessionLocal() as db:
                get_or_create_local_user(db)
        except Exception:
            pass

    # Mount versioned API routes (/api/v1)
    application.include_router(api_router, prefix="/api/v1")

    # Mount health probes at root level as well (/health, /health/ready, /api/health)
    application.include_router(health.router, tags=["Health"])
    application.include_router(health.router, prefix="/api", tags=["Health"])

    @application.get("/", include_in_schema=False)
    def root_info() -> dict:
        return {
            "app": "Knovera",
            "version": "1.0.0",
            "status": "online",
            "docs": "/docs",
        }

    return application


app = create_app()
