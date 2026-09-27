# SYNTHETIC: throwaway databases only.
"""The initial migration installs cleanly, matches the models and round-trips."""

from __future__ import annotations

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text

from app.db.models import Base
from tests.db.conftest import alembic_config, create_temp_database, drop_temp_database

CORE_TABLES = {
    "conversation",
    "message",
    "job",
    "draft",
    "outbound_message",
    "system_setting",
    "audit_event",
}


def test_core_tables_and_seed_row(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) >= CORE_TABLES
    with engine.connect() as conn:
        row = conn.execute(text("SELECT kill_switch, automation_mode FROM system_setting")).one()
    assert tuple(row) == (False, "draft_only")


def test_models_match_migration(engine: Engine) -> None:
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_partial_unique_index_is_queued_only(engine: Engine) -> None:
    with engine.connect() as conn:
        indexdef = conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_job_queued_kind_dedup_key'")
        ).scalar_one()
    assert "UNIQUE" in indexdef
    assert "WHERE (status = 'queued'::text)" in indexdef


def test_downgrade_and_upgrade_again(admin_url: str) -> None:
    url = create_temp_database(admin_url)
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            command.upgrade(alembic_config(conn), "head")
        with engine.begin() as conn:
            command.downgrade(alembic_config(conn), "base")
        assert not CORE_TABLES & set(inspect(engine).get_table_names())
        with engine.begin() as conn:
            command.upgrade(alembic_config(conn), "head")
        assert set(inspect(engine).get_table_names()) >= CORE_TABLES
    finally:
        engine.dispose()
        drop_temp_database(admin_url, url)
