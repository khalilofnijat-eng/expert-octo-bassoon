"""Liveness endpoint. Reports process health only; it does not check the DB or external systems."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Return ``{"status": "ok"}`` while the process can serve requests."""
    return {"status": "ok"}
