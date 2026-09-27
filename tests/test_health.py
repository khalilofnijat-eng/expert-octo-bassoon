"""Tests for the /healthz liveness endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_reports_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
