# SYNTHETIC: fixtures load the made-up W213 dataset and throwaway databases only.
from __future__ import annotations

from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text

from app.catalog.dataset import SyntheticDataset, load_synthetic_dataset
from app.catalog.evidence import EvidencePolicy
from app.catalog.runtime import RuntimeMode
from tests.db.conftest import _admin_url, alembic_config, create_temp_database, drop_temp_database


@pytest.fixture(scope="session")
def dataset() -> SyntheticDataset:
    return load_synthetic_dataset()


@pytest.fixture
def test_policy() -> EvidencePolicy:
    return EvidencePolicy(RuntimeMode.TEST)


# --- Real PostgreSQL (same rules as tests/db: TEST_DATABASE_URL, REQUIRE_TEST_DATABASE) -----

CATALOG_TABLES = (
    "photo",
    "price",
    "inventory_item",
    "set_component",
    "fitment",
    "vehicle_spec",
    "product_oem_number",
    "product",
)


@pytest.fixture(scope="session")
def catalog_db_url() -> Iterator[str]:
    admin = _admin_url()
    url = create_temp_database(admin)
    engine = create_engine(url)
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    engine.dispose()
    yield url
    drop_temp_database(admin, url)


@pytest.fixture(scope="session")
def _catalog_session_engine(catalog_db_url: str) -> Iterator[Engine]:
    engine = create_engine(catalog_db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def catalog_engine(_catalog_session_engine: Engine) -> Engine:
    """Migrated database with empty catalog/stock tables."""
    with _catalog_session_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(CATALOG_TABLES)} RESTART IDENTITY CASCADE"))
    return _catalog_session_engine
