"""Engine construction. The URL comes from ``DATABASE_URL`` (a secret) unless passed explicitly."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine

from app.config import get_settings


def database_url() -> str:
    """Return ``DATABASE_URL`` or raise if it is not configured."""
    url = get_settings().database_url
    if url is None:
        raise RuntimeError("DATABASE_URL is not set")
    return url.get_secret_value()


def make_engine(url: str | None = None, **kwargs: object) -> Engine:
    """Create an engine. ``pool_pre_ping`` drops dead pooled connections before use.

    Lock-holding connections never come back to this pool (see ``app.queue.locks``).
    """
    return create_engine(url or database_url(), pool_pre_ping=True, **kwargs)
