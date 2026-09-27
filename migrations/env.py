"""Alembic environment.

Connection source, in order: a connection passed by the caller in
``config.attributes["connection"]`` (tests), otherwise ``DATABASE_URL`` via ``app.config``.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import Connection

from app.db.engine import make_engine
from app.db.models import Base

target_metadata = Base.metadata


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    given = context.config.attributes.get("connection")
    if given is not None:
        _run(given)
        return
    engine = make_engine()
    try:
        with engine.connect() as connection:
            _run(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (--sql) mode is not supported; run against a database.")
run_migrations_online()
