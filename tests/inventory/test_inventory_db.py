# SYNTHETIC: throwaway databases; rows are the made-up W213 dataset. Rows labelled
# data_origin='real' below use 'TEST-ONLY-' SKUs and exist only to prove the CHECKs.
"""Migration 0002 on real PostgreSQL: constraints, grants, seed/load round trip."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import Connection, Engine, insert, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.catalog.dataset import SyntheticDataset
from app.catalog.evidence import EvidencePolicy
from app.catalog.fitment import VehicleQuery, evaluate_candidates, evaluate_set
from app.catalog.runtime import RuntimeMode, SyntheticDataRejected
from app.catalog.store import load_catalog, seed_synthetic_dataset
from app.catalog.types import DataOrigin, FitmentStatus, SetKind
from app.db import models as db
from tests.inventory.conftest import CATALOG_TABLES

T0 = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)
FULL_PRE_AMG = VehicleQuery(
    chassis_code="W213",
    year=2018,
    facelift=False,
    trim_line="amg_line",
    parktronic_sensors=6,
    headlamp_washer=True,
    front_camera=False,
)


def _product(conn: Connection, sku: str, origin: str = "synthetic") -> int:
    return int(
        conn.execute(
            insert(db.Product)
            .values(
                sku=sku,
                title="test part",
                part_type="front_grille",
                condition="new",
                data_origin=origin,
                source="test",
                fetched_at=T0,
            )
            .returning(db.Product.id)
        ).scalar_one()
    )


def _spec(conn: Connection, origin: str = "synthetic") -> int:
    return int(
        conn.execute(
            insert(db.VehicleSpec)
            .values(
                make="Mercedes-Benz",
                model="E-Class",
                chassis_code="W213",
                data_origin=origin,
                source="test",
            )
            .returning(db.VehicleSpec.id)
        ).scalar_one()
    )


def _fitment(conn: Connection, product_id: int, spec_id: int, **values: Any) -> None:
    row = {
        "product_id": product_id,
        "vehicle_spec_id": spec_id,
        "status": "verified",
        "evidence_type": "synthetic_fixture",
        "evidence_ref": "SYN-EVID-1",
        "verified_at": T0,
        "data_origin": "synthetic",
        "source": "test",
        "fetched_at": T0,
    }
    row.update(values)
    conn.execute(insert(db.Fitment).values(**row))


def _rejects(engine: Engine, action: Callable[[Connection], None], constraint: str) -> None:
    with pytest.raises(IntegrityError) as err, engine.begin() as conn:
        action(conn)
    assert constraint in str(err.value)


def test_tables_exist_and_runtime_role_has_dml(catalog_engine: Engine) -> None:
    assert set(inspect(catalog_engine).get_table_names()) >= set(CATALOG_TABLES)
    with catalog_engine.connect() as conn:
        for table in CATALOG_TABLES:
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert conn.execute(
                    text("SELECT has_table_privilege('assistant_app', :t, :p)"),
                    {"t": table, "p": privilege},
                ).scalar_one(), (table, privilege)


def test_verified_fitment_needs_allowed_evidence(catalog_engine: Engine) -> None:
    with catalog_engine.begin() as conn:
        pid, sid = _product(conn, "SYN-GR-1"), _spec(conn)
        _fitment(conn, pid, sid)  # synthetic evidence on a synthetic row: allowed
        _fitment(
            conn, pid, sid, status="needs_verification", evidence_type="visual_similarity"
        )  # a hint may be stored, just never as 'verified'

    for kind in ("visual_similarity", "customer_statement", "llm_output", "body_code_only"):
        _rejects(
            catalog_engine,
            lambda c, k=kind: _fitment(c, pid, sid, evidence_type=k),
            "ck_fitment_verified_evidence",
        )
    _rejects(
        catalog_engine,
        lambda c: _fitment(c, pid, sid, evidence_type=None, evidence_ref=None),
        "ck_fitment_verified_evidence",
    )
    _rejects(
        catalog_engine,
        lambda c: _fitment(c, pid, sid, evidence_type="owner_confirmed", evidence_ref=" "),
        "ck_fitment_verified_evidence",
    )
    _rejects(
        catalog_engine,
        lambda c: _fitment(c, pid, sid, evidence_type="owner_confirmed", verified_at=None),
        "ck_fitment_verified_evidence",
    )
    _rejects(
        catalog_engine,
        lambda c: _fitment(c, pid, sid, evidence_type="looks_the_same"),
        "ck_fitment_evidence_type",
    )


def test_synthetic_evidence_only_on_synthetic_rows(catalog_engine: Engine) -> None:
    with catalog_engine.begin() as conn:
        pid, sid = _product(conn, "TEST-ONLY-GR-1", "real"), _spec(conn, "real")
        _fitment(
            conn, pid, sid, data_origin="real", evidence_type="owner_confirmed", evidence_ref="T-1"
        )
    _rejects(
        catalog_engine,
        lambda c: _fitment(c, pid, sid, data_origin="real"),
        # Violates ck_fitment_verified_evidence too; PostgreSQL reports the first by name.
        "ck_fitment_synthetic_evidence",
    )
    _rejects(
        catalog_engine,
        lambda c: _fitment(c, pid, sid, data_origin="real", status="needs_verification"),
        "ck_fitment_synthetic_evidence",
    )


def test_synthetic_labels_are_enforced(catalog_engine: Engine) -> None:
    _rejects(catalog_engine, lambda c: _product(c, "SYN-GR-1", "real"), "ck_product_synthetic_sku")
    _rejects(catalog_engine, lambda c: _product(c, "GR-1", "synthetic"), "ck_product_synthetic_sku")
    _rejects(catalog_engine, lambda c: _product(c, "SYN-GR-1", "made_up"), "ck_product_data_origin")


def test_stock_price_photo_constraints(catalog_engine: Engine) -> None:
    with catalog_engine.begin() as conn:
        pid = _product(conn, "SYN-GR-1")
        item = conn.execute(
            insert(db.InventoryItem)
            .values(
                product_id=pid,
                physical_qty=1,
                available_qty=1,
                data_origin="synthetic",
                source="test",
                source_ref="SYN-STK-1",
                fetched_at=T0,
            )
            .returning(db.InventoryItem.id)
        ).scalar_one()

    def stock(**values: Any) -> Callable[[Connection], None]:
        row = {
            "product_id": pid,
            "physical_qty": 1,
            "available_qty": 1,
            "data_origin": "synthetic",
            "source": "test",
            "fetched_at": T0,
            **values,
        }
        return lambda c: c.execute(insert(db.InventoryItem).values(**row)) and None

    def price(**values: Any) -> Callable[[Connection], None]:
        row = {
            "product_id": pid,
            "amount_minor": 100,
            "currency": "RUB",
            "data_origin": "synthetic",
            "source": "test",
            "fetched_at": T0,
            **values,
        }
        return lambda c: c.execute(insert(db.Price).values(**row)) and None

    def photo(**values: Any) -> Callable[[Connection], None]:
        row = {
            "inventory_item_id": item,
            "storage_uri": "synthetic://placeholder/SYN-STK-1/1",
            "data_origin": "synthetic",
            "source": "test",
            "fetched_at": T0,
            **values,
        }
        return lambda c: c.execute(insert(db.Photo).values(**row)) and None

    _rejects(catalog_engine, stock(physical_qty=-1), "ck_inventory_item_physical_qty")
    _rejects(catalog_engine, stock(available_qty=-1), "ck_inventory_item_available_qty")
    _rejects(catalog_engine, stock(source_ref="SYN-STK-1"), "uq_inventory_item_source_ref")
    _rejects(catalog_engine, price(currency="rub"), "ck_price_currency")
    _rejects(catalog_engine, price(amount_minor=-1), "ck_price_amount_minor")
    _rejects(catalog_engine, photo(storage_uri="https://example.invalid/1.jpg"), "ck_photo")
    _rejects(catalog_engine, photo(inventory_item_id=None), "inventory_item_id")
    with catalog_engine.begin() as conn:
        photo()(conn)
        price()(conn)


def test_set_component_constraints(catalog_engine: Engine) -> None:
    with catalog_engine.begin() as conn:
        pid = _product(conn, "SYN-SET-1")

    def line(**values: Any) -> Callable[[Connection], None]:
        row = {
            "set_product_id": pid,
            "component_product_id": pid,
            "data_origin": "synthetic",
            "source": "test",
            **values,
        }
        return lambda c: c.execute(insert(db.SetComponent).values(**row)) and None

    _rejects(catalog_engine, line(), "ck_set_component_not_self")


def test_seed_refused_in_production(catalog_engine: Engine, dataset: SyntheticDataset) -> None:
    with pytest.raises(SyntheticDataRejected), catalog_engine.begin() as conn:
        seed_synthetic_dataset(conn, dataset, mode=RuntimeMode.PRODUCTION)


def test_seed_and_load_round_trip(catalog_engine: Engine, dataset: SyntheticDataset) -> None:
    with catalog_engine.begin() as conn:
        ids = seed_synthetic_dataset(conn, dataset, mode=RuntimeMode.TEST)
    assert set(ids) == {p.sku for p in dataset.products}
    with catalog_engine.connect() as conn:
        origins = {
            t: conn.execute(text(f"SELECT DISTINCT data_origin FROM {t}")).scalars().all()
            for t in CATALOG_TABLES
            if t != "product_oem_number"
        }
        catalog = load_catalog(conn)
        photo_items = conn.execute(
            select(db.Photo.storage_uri, db.InventoryItem.source_ref).join(
                db.InventoryItem, db.Photo.inventory_item_id == db.InventoryItem.id
            )
        ).all()
    assert all(v == ["synthetic"] for v in origins.values()), origins
    assert {(p.sku, p.oem_numbers, p.set_kind) for p in catalog.products} == {
        (p.sku, p.oem_numbers, p.set_kind) for p in dataset.products
    }
    assert all(p.provenance.data_origin is DataOrigin.SYNTHETIC for p in catalog.products)
    assert sorted(catalog.set_components, key=repr) == sorted(dataset.set_components, key=repr)
    assert sorted(
        (f.record_id, f.status, sorted(f.conditions.items())) for f in catalog.fitments
    ) == sorted((f.record_id, f.status, sorted(f.conditions.items())) for f in dataset.fitments)
    assert {f.record_id: f.evidence for f in catalog.fitments} == {
        f.record_id: f.evidence for f in dataset.fitments
    }
    assert {(uri, ref) for uri, ref in photo_items} == {
        (ph.key, ph.stock_ref) for ph in dataset.photos
    }


def test_w213_verdicts_from_db_match_in_memory(
    catalog_engine: Engine, dataset: SyntheticDataset, test_policy: EvidencePolicy
) -> None:
    with catalog_engine.begin() as conn:
        seed_synthetic_dataset(conn, dataset, mode=RuntimeMode.TEST)
    with catalog_engine.connect() as conn:
        catalog = load_catalog(conn)

    def verdicts(products: Any, fitments: Any, components: Any) -> dict[str, Any]:
        found = evaluate_candidates(products, fitments, FULL_PRE_AMG, test_policy)
        results = {r.sku: r for r in found}
        for p in products:
            if p.set_kind is not SetKind.SINGLE:
                results[p.sku] = evaluate_set(p, components, results, results[p.sku])
        return {s: (r.status, r.reasons, r.missing_attributes) for s, r in results.items()}

    from_db = verdicts(catalog.products, catalog.fitments, catalog.set_components)
    in_memory = verdicts(dataset.products, dataset.fitments, dataset.set_components)
    assert from_db == in_memory
    verified = {s for s, v in from_db.items() if v[0] is FitmentStatus.VERIFIED}
    assert "SYN-W213-FB-001" in verified and "SYN-W213-GR-001" in verified

    # The same DB rows are refused in production mode.
    with pytest.raises(SyntheticDataRejected):
        evaluate_candidates(
            catalog.products, catalog.fitments, FULL_PRE_AMG, EvidencePolicy(RuntimeMode.PRODUCTION)
        )
