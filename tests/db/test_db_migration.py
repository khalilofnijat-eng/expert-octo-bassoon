# SYNTHETIC: throwaway databases only.
"""The initial migration installs cleanly, matches the models, seeds safe settings, round-trips,
and refuses to downgrade in production."""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from pydantic import ValidationError
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError

from app.config import AppEnv, AutomationMode, Settings
from app.db.models import Base
from app.db.roles import UnsafeDatabaseRoleError, check_runtime_role
from tests.db.conftest import alembic_config, create_temp_database, drop_temp_database

CORE_TABLES = {
    "conversation",
    "message",
    "job",
    "draft",
    "outbound_message",
    "system_setting",
    "worker_singleton",
    "audit_event",
}


def test_core_tables_and_seed_rows(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) >= CORE_TABLES
    with engine.connect() as conn:
        # The engine fixture resets to the seed values; check the column defaults too.
        row = conn.execute(text("SELECT kill_switch, automation_mode FROM system_setting")).one()
        default = conn.execute(
            text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_name = 'system_setting' AND column_name = 'kill_switch'"
            )
        ).scalar_one()
        assert conn.execute(text("SELECT count(*) FROM worker_singleton")).scalar_one() == 1
    assert tuple(row) == (True, "draft_only")
    assert default == "true"


def test_models_match_migration(engine: Engine) -> None:
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_partial_unique_indexes(engine: Engine) -> None:
    with engine.connect() as conn:
        defs = dict(
            conn.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes WHERE indexname IN "
                    "('uq_job_queued_kind_dedup_key', 'uq_draft_open_per_seq')"
                )
            ).all()
        )
    assert "WHERE (status = 'queued'::text)" in defs["uq_job_queued_kind_dedup_key"]
    assert "proposed" in defs["uq_draft_open_per_seq"]
    assert "approved" in defs["uq_draft_open_per_seq"]


def _fresh(admin_url: str) -> tuple[str, Engine]:
    url = create_temp_database(admin_url)
    return url, create_engine(url)


def test_seed_mode_comes_from_environment(admin_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOMATION_MODE", "approve_to_send")
    url, engine = _fresh(admin_url)
    try:
        with engine.begin() as conn:
            command.upgrade(alembic_config(conn), "head")
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT kill_switch, automation_mode FROM system_setting")
            ).one()
        assert tuple(row) == (True, "approve_to_send")  # the kill switch is still on
    finally:
        engine.dispose()
        drop_temp_database(admin_url, url)


def test_auto_scoped_is_not_an_active_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    assert [m.value for m in AutomationMode] == ["draft_only", "approve_to_send"]
    monkeypatch.setenv("AUTOMATION_MODE", "auto_scoped")
    with pytest.raises(ValidationError):
        Settings()


def test_downgrade_and_upgrade_again(admin_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    url, engine = _fresh(admin_url)
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


@pytest.mark.parametrize("app_env", [None, "production"])
def test_downgrade_refused_in_production(
    admin_url: str, monkeypatch: pytest.MonkeyPatch, app_env: str | None
) -> None:
    url, engine = _fresh(admin_url)
    try:
        with engine.begin() as conn:
            command.upgrade(alembic_config(conn), "0001")
        if app_env is None:
            monkeypatch.delenv("APP_ENV", raising=False)  # unset means production
        else:
            monkeypatch.setenv("APP_ENV", app_env)
        with engine.begin() as conn, pytest.raises(RuntimeError, match="production"):
            command.downgrade(alembic_config(conn), "base")
        assert set(inspect(engine).get_table_names()) >= CORE_TABLES
    finally:
        engine.dispose()
        drop_temp_database(admin_url, url)


def test_roles_end_to_end(admin_url: str) -> None:
    """R1: migrate as a non-superuser owner; the app logs in as a member of assistant_app.
    The owner can disable the audit trigger (why the app must never be the owner); the app
    login cannot, and passes the production role check, which the owner fails."""
    suffix = uuid.uuid4().hex[:8]
    owner, login, db = f"syn_owner_{suffix}", f"syn_login_{suffix}", f"syn_roles_{suffix}"
    password = uuid.uuid4().hex  # throwaway, for servers that require password auth (CI)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    base = make_url(admin_url)
    with admin.connect() as conn:
        conn.execute(text(f"CREATE ROLE {owner} LOGIN CREATEROLE PASSWORD '{password}'"))
        conn.execute(text(f"CREATE ROLE {login} LOGIN PASSWORD '{password}'"))
        conn.execute(text(f"CREATE DATABASE {db} OWNER {owner}"))
    owner_engine = create_engine(base.set(username=owner, password=password, database=db))
    login_engine = create_engine(base.set(username=login, password=password, database=db))
    try:
        with owner_engine.begin() as conn:
            command.upgrade(alembic_config(conn), "head")
        with admin.connect() as conn:
            # On a fresh cluster the owner created assistant_app and may grant it itself; here the
            # role already exists cluster-wide, so the superuser grants it.
            conn.execute(text(f"GRANT assistant_app TO {login}"))
        with login_engine.begin() as conn:
            check_runtime_role(conn, AppEnv.PRODUCTION)
            conn.execute(
                text(
                    "INSERT INTO audit_event (op_id, actor, action, result) "
                    "VALUES ('SYN-1', 't', 'a', 'ok')"
                )
            )
        for stmt in (
            "UPDATE audit_event SET result = 'x'",
            "DELETE FROM audit_event",
            "ALTER TABLE audit_event DISABLE TRIGGER USER",
        ):
            with login_engine.begin() as conn, pytest.raises(ProgrammingError):
                conn.execute(text(stmt))
        with owner_engine.begin() as conn:
            with pytest.raises(UnsafeDatabaseRoleError):
                check_runtime_role(conn, AppEnv.PRODUCTION)
            conn.execute(
                text("ALTER TABLE audit_event DISABLE TRIGGER audit_event_no_update_delete")
            )
            assert conn.execute(text("DELETE FROM audit_event")).rowcount == 1  # the known gap
            conn.rollback()
    finally:
        owner_engine.dispose()
        login_engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {db} WITH (FORCE)"))
            conn.execute(text(f"DROP ROLE IF EXISTS {login}"))
            conn.execute(text(f"REASSIGN OWNED BY {owner} TO CURRENT_USER"))
            conn.execute(text(f"DROP OWNED BY {owner}"))
            conn.execute(text(f"DROP ROLE IF EXISTS {owner}"))
        admin.dispose()
