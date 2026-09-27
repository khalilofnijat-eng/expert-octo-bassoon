# SYNTHETIC: all rows created by these fixtures are made-up test data.
"""Real-PostgreSQL fixtures for tests/db.

``TEST_DATABASE_URL`` points at a PostgreSQL 16 server with a superuser (it creates and drops a
throwaway database and uses ``pg_terminate_backend``). Without it the DB tests are skipped, unless
``REQUIRE_TEST_DATABASE=1`` (set in CI), in which case they fail.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url

from app.config import REPO_ROOT
from app.queue.locks import SingletonToken, WorkerSingleton
from tests.db.factories import ExitRecorder


def _admin_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        if os.environ.get("REQUIRE_TEST_DATABASE") == "1":
            pytest.fail("TEST_DATABASE_URL is required (REQUIRE_TEST_DATABASE=1)")
        pytest.skip("TEST_DATABASE_URL not set; real-PostgreSQL tests skipped")
    return url


def alembic_config(connection: Connection) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.attributes["connection"] = connection
    return cfg


def create_temp_database(admin_url: str) -> str:
    name = f"t_{uuid.uuid4().hex[:12]}"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    return make_url(admin_url).set(database=name).render_as_string(hide_password=False)


def drop_temp_database(admin_url: str, url: str) -> None:
    name = make_url(url).database
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="session")
def admin_url() -> str:
    return _admin_url()


@pytest.fixture(scope="session")
def db_url(admin_url: str) -> Iterator[str]:
    url = create_temp_database(admin_url)
    engine = create_engine(url)
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    engine.dispose()
    yield url
    drop_temp_database(admin_url, url)


@pytest.fixture(scope="session")
def _session_engine(db_url: str) -> Iterator[Engine]:
    engine = create_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def engine(_session_engine: Engine) -> Engine:
    """Engine on a migrated database, emptied before each test and reset to the seed settings
    (kill switch on, draft_only). audit_event is append-only and is left alone; tests use unique
    op ids or count relative to a baseline."""
    with _session_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE message, outbound_message, draft, job, conversation "
                "RESTART IDENTITY CASCADE"
            )
        )
        conn.execute(
            text(
                "INSERT INTO system_setting (id) VALUES (1) ON CONFLICT (id) DO UPDATE SET "
                "kill_switch = true, automation_mode = 'draft_only', version = 0"
            )
        )
    return _session_engine


@pytest.fixture
def singleton(engine: Engine) -> Iterator[WorkerSingleton]:
    """A held worker singleton whose loss is recorded instead of ending the test process."""
    s = WorkerSingleton(engine, on_lost=ExitRecorder(), check_timeout_s=2.0)
    s.acquire()
    yield s
    s.release()


@pytest.fixture
def token(singleton: WorkerSingleton) -> SingletonToken:
    assert singleton.token is not None
    return singleton.token
