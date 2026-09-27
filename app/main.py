"""FastAPI application factory. Run locally with ``uv run uvicorn app.main:app``."""

from __future__ import annotations

from fastapi import FastAPI

from app.ops.health import router as health_router


def create_app() -> FastAPI:
    """Build the web application."""
    application = FastAPI(title="Avito Assistant", docs_url=None, redoc_url=None)
    application.include_router(health_router)
    return application


app = create_app()
