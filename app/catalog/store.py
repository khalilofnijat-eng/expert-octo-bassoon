"""Catalog tables ↔ domain types (migration 0002).

- ``seed_synthetic_dataset`` writes the SYNTHETIC fixture dataset into the catalog and stock
  tables (``data_origin='synthetic'`` everywhere). It refuses production mode. Syncing real
  warehouse data is the real adapter's job (after T-007, B-002).
- ``load_catalog`` reads products, fitment rows and set components back into the types the
  fitment engine and set logic use. Provenance comes from the row (source, data_origin,
  fetched_at, verified_at), so production mode still rejects synthetic rows downstream.

Helpers do not commit; the caller owns the transaction.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import Connection, insert, select

from app.catalog.dataset import SyntheticDataset
from app.catalog.runtime import RuntimeMode, SyntheticDataRejected, current_runtime_mode
from app.catalog.types import (
    Condition,
    ConditionValue,
    DataOrigin,
    Evidence,
    EvidenceKind,
    FitmentRecord,
    FitmentStatus,
    Product,
    Provenance,
    SetComponent,
    SetKind,
    VehicleSpec,
)
from app.db import models as db
from app.inventory.port import normalize_oem

SYNTHETIC = DataOrigin.SYNTHETIC.value


@dataclass(frozen=True)
class Catalog:
    products: tuple[Product, ...]
    fitments: tuple[FitmentRecord, ...]
    set_components: tuple[SetComponent, ...]

    def product(self, sku: str) -> Product:
        for p in self.products:
            if p.sku == sku:
                return p
        raise KeyError(sku)


def seed_synthetic_dataset(
    conn: Connection, dataset: SyntheticDataset, *, mode: RuntimeMode | None = None
) -> dict[str, int]:
    """Insert the synthetic dataset; returns SKU → ``product.id``."""
    if (mode if mode is not None else current_runtime_mode()) is RuntimeMode.PRODUCTION:
        raise SyntheticDataRejected("refusing to seed synthetic catalog data in production")
    source = dataset.source
    fetched_at = dataset.snapshot_at

    spec_ids: dict[str, int] = {}
    for ref, spec in dataset.vehicle_specs.items():
        spec_ids[ref] = conn.execute(
            insert(db.VehicleSpec)
            .values(
                make=spec.make,
                model=spec.model,
                chassis_code=spec.chassis_code,
                year_from=spec.year_from,
                year_to=spec.year_to,
                facelift=spec.facelift,
                data_origin=SYNTHETIC,
                source=source,
                source_ref=ref,
            )
            .returning(db.VehicleSpec.id)
        ).scalar_one()

    product_ids: dict[str, int] = {}
    for p in dataset.products:
        pid = conn.execute(
            insert(db.Product)
            .values(
                sku=p.sku,
                title=p.title,
                brand=p.brand,
                part_type=p.part_type,
                condition=p.condition.value,
                color=p.color,
                condition_notes=p.condition_notes,
                set_kind=p.set_kind.value,
                data_origin=SYNTHETIC,
                source=source,
                source_ref=p.sku,
                fetched_at=fetched_at,
                last_verified_at=p.provenance.verified_at,
            )
            .returning(db.Product.id)
        ).scalar_one()
        product_ids[p.sku] = pid
        for oem in p.oem_numbers:
            conn.execute(
                insert(db.ProductOemNumber).values(
                    product_id=pid, oem_number=oem, oem_number_norm=normalize_oem(oem)
                )
            )

    for f in dataset.fitments:
        ev = f.evidence
        conn.execute(
            insert(db.Fitment).values(
                product_id=product_ids[f.sku],
                vehicle_spec_id=spec_ids[dataset.fitment_spec_ids[f.record_id]],
                conditions={
                    k: list(v) if isinstance(v, tuple) else v for k, v in f.conditions.items()
                },
                status=f.status.value,
                evidence_type=ev.kind.value if ev else None,
                evidence_ref=ev.ref if ev else None,
                verified_by=ev.verified_by if ev else None,
                verified_at=ev.verified_at if ev else None,
                data_origin=SYNTHETIC,
                source=source,
                source_ref=f.record_id,
                fetched_at=fetched_at,
            )
        )

    for c in dataset.set_components:
        conn.execute(
            insert(db.SetComponent).values(
                set_product_id=product_ids[c.set_sku],
                component_product_id=product_ids[c.component_sku],
                qty=c.qty,
                present=c.present,
                optional=c.optional,
                data_origin=SYNTHETIC,
                source=source,
            )
        )

    item_ids: dict[str, int] = {}
    for s in dataset.stock:
        item_ids[s.ref] = conn.execute(
            insert(db.InventoryItem)
            .values(
                product_id=product_ids[s.sku],
                location=s.location,
                physical_qty=s.physical_qty,
                external_reserved_qty=s.external_reserved_qty,
                available_qty=s.available_qty,
                data_origin=SYNTHETIC,
                source=source,
                source_ref=s.ref,
                fetched_at=fetched_at,
                verified_at=s.verified_at,
            )
            .returning(db.InventoryItem.id)
        ).scalar_one()

    for pr in dataset.prices:
        conn.execute(
            insert(db.Price).values(
                product_id=product_ids[pr.sku],
                amount_minor=pr.amount_minor,
                currency=pr.currency,
                discount_rule_key=pr.discount_rule_key,
                data_origin=SYNTHETIC,
                source=source,
                source_ref=pr.sku,
                fetched_at=fetched_at,
                verified_at=pr.verified_at,
            )
        )

    for ph in dataset.photos:
        conn.execute(
            insert(db.Photo).values(
                inventory_item_id=item_ids[ph.stock_ref],
                storage_uri=ph.key,
                sort_order=ph.sort_order,
                data_origin=SYNTHETIC,
                source=source,
                source_ref=ph.key,
                fetched_at=fetched_at,
                verified_at=ph.verified_at,
            )
        )
    return product_ids


def _conditions(raw: dict[str, Any]) -> dict[str, ConditionValue]:
    return {k: tuple(v) if isinstance(v, list) else cast(ConditionValue, v) for k, v in raw.items()}


def load_catalog(conn: Connection, skus: Iterable[str] | None = None) -> Catalog:
    """Read products (with OEM numbers), fitment rows and set components, ordered by SKU /
    row id. ``skus`` limits products and fitments; set lines are kept when their set is
    selected."""
    wanted = set(skus) if skus is not None else None
    pt = db.Product.__table__
    all_rows = conn.execute(select(pt).order_by(pt.c.sku, pt.c.id)).mappings().all()
    sku_by_id: dict[int, str] = {r["id"]: r["sku"] for r in all_rows}
    rows = [r for r in all_rows if wanted is None or r["sku"] in wanted]
    selected = {r["id"] for r in rows}

    ot = db.ProductOemNumber.__table__
    oems: dict[int, list[str]] = {}
    for o in conn.execute(select(ot.c.product_id, ot.c.oem_number).order_by(ot.c.id)):
        oems.setdefault(o.product_id, []).append(o.oem_number)
    products = tuple(
        Product(
            sku=r["sku"],
            title=r["title"],
            part_type=r["part_type"],
            condition=Condition(r["condition"]),
            set_kind=SetKind(r["set_kind"]),
            provenance=Provenance(
                r["source"],
                DataOrigin(r["data_origin"]),
                r["fetched_at"],
                r["last_verified_at"],
                r["source_ref"],
            ),
            brand=r["brand"],
            color=r["color"],
            condition_notes=r["condition_notes"],
            oem_numbers=tuple(oems.get(r["id"], ())),
        )
        for r in rows
    )

    ft = db.Fitment.__table__
    vt = db.VehicleSpec.__table__
    stmt = (
        select(
            ft,
            vt.c.make,
            vt.c.model,
            vt.c.chassis_code,
            vt.c.year_from,
            vt.c.year_to,
            vt.c.facelift,
        )
        .join_from(ft, vt, ft.c.vehicle_spec_id == vt.c.id)
        .order_by(ft.c.id)
    )
    fitments: list[FitmentRecord] = []
    for f in conn.execute(stmt).mappings():
        if f["product_id"] not in selected:
            continue
        evidence = (
            Evidence(
                kind=EvidenceKind(f["evidence_type"]),
                ref=f["evidence_ref"],
                verified_by=f["verified_by"],
                verified_at=f["verified_at"],
            )
            if f["evidence_type"] is not None
            else None
        )
        fitments.append(
            FitmentRecord(
                record_id=f["source_ref"] or f"fitment:{f['id']}",
                sku=sku_by_id[f["product_id"]],
                vehicle=VehicleSpec(
                    make=f["make"],
                    model=f["model"],
                    chassis_code=f["chassis_code"],
                    year_from=f["year_from"],
                    year_to=f["year_to"],
                    facelift=f["facelift"],
                ),
                status=FitmentStatus(f["status"]),
                provenance=Provenance(
                    f["source"],
                    DataOrigin(f["data_origin"]),
                    f["fetched_at"],
                    f["verified_at"],
                    f["source_ref"],
                ),
                conditions=_conditions(f["conditions"]),
                evidence=evidence,
            )
        )

    st = db.SetComponent.__table__
    components = tuple(
        SetComponent(
            set_sku=sku_by_id[c["set_product_id"]],
            component_sku=sku_by_id[c["component_product_id"]],
            qty=c["qty"],
            present=c["present"],
            optional=c["optional"],
        )
        for c in conn.execute(
            select(st).order_by(st.c.set_product_id, st.c.component_product_id)
        ).mappings()
        if c["set_product_id"] in selected
    )
    return Catalog(products, tuple(fitments), components)
