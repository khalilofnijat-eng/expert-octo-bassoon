"""Loader for the SYNTHETIC catalog/inventory dataset (JSON fixtures, T-022).

The dataset backs ``SyntheticInventoryAdapter`` and the DB seeder (``app.catalog.store``). It is
made-up data for development and tests only. The loader refuses anything that is not clearly
labelled synthetic: ``data_origin`` must be ``synthetic``, every SKU/stock/fitment id must start
with ``SYN-`` and every photo key must be a ``synthetic://`` placeholder (no image files exist).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from app.catalog.types import (
    SYNTHETIC_SKU_PREFIX,
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
from app.config import REPO_ROOT

DEFAULT_DATASET_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "synthetic_catalog" / "w213_front_bumper.json"
)
SYNTHETIC_PHOTO_SCHEME = "synthetic://"


class DatasetError(ValueError):
    """The dataset is malformed or not labelled synthetic."""


@dataclass(frozen=True)
class StockLine:
    ref: str
    sku: str
    location: str | None
    physical_qty: int
    external_reserved_qty: int
    available_qty: int
    verified_at: datetime | None


@dataclass(frozen=True)
class PriceLine:
    sku: str
    amount_minor: int
    currency: str
    discount_rule_key: str | None
    verified_at: datetime | None


@dataclass(frozen=True)
class PhotoLine:
    stock_ref: str
    key: str
    sort_order: int
    verified_at: datetime | None


@dataclass(frozen=True)
class SyntheticDataset:
    name: str
    source: str
    snapshot_at: datetime
    vehicle_specs: dict[str, VehicleSpec]
    products: tuple[Product, ...]
    fitments: tuple[FitmentRecord, ...]
    # Spec id per fitment record id (the DB seeder links rows through it).
    fitment_spec_ids: dict[str, str]
    set_components: tuple[SetComponent, ...]
    stock: tuple[StockLine, ...]
    prices: tuple[PriceLine, ...]
    photos: tuple[PhotoLine, ...]

    def product(self, sku: str) -> Product:
        for p in self.products:
            if p.sku == sku:
                return p
        raise KeyError(sku)


def _ts(value: Any, what: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DatasetError(f"{what}: timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise DatasetError(f"{what}: timestamp must carry a UTC offset")
    return parsed


def _req_ts(value: Any, what: str) -> datetime:
    parsed = _ts(value, what)
    if parsed is None:
        raise DatasetError(f"{what}: timestamp required")
    return parsed


def _syn(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.startswith(SYNTHETIC_SKU_PREFIX):
        raise DatasetError(f"{what} must start with {SYNTHETIC_SKU_PREFIX!r}: {value!r}")
    return value


def _int(value: Any, what: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise DatasetError(f"{what} must be an integer")
    return value


def _conditions(raw: Any, what: str) -> dict[str, ConditionValue]:
    if not isinstance(raw, dict):
        raise DatasetError(f"{what}: conditions must be an object")
    out: dict[str, ConditionValue] = {}
    for key, value in raw.items():
        out[key] = tuple(value) if isinstance(value, list) else cast(ConditionValue, value)
    return out


def parse_dataset(doc: dict[str, Any]) -> SyntheticDataset:
    """Build a ``SyntheticDataset`` from the parsed JSON document, validating labels."""
    if doc.get("data_origin") != DataOrigin.SYNTHETIC.value:
        raise DatasetError("dataset must declare data_origin 'synthetic'")
    name = _syn(doc.get("dataset"), "dataset name")
    source = doc.get("source")
    if not isinstance(source, str) or not source:
        raise DatasetError("dataset source required")
    snapshot_at = _req_ts(doc.get("snapshot_at"), "snapshot_at")

    def provenance(verified_at: datetime | None, ref: str | None = None) -> Provenance:
        return Provenance(source, DataOrigin.SYNTHETIC, snapshot_at, verified_at, ref)

    specs: dict[str, VehicleSpec] = {}
    for raw in doc.get("vehicle_specs", []):
        spec_id = _syn(raw.get("id"), "vehicle spec id")
        specs[spec_id] = VehicleSpec(
            make=raw["make"],
            model=raw["model"],
            chassis_code=raw["chassis_code"],
            year_from=raw.get("year_from"),
            year_to=raw.get("year_to"),
            facelift=raw.get("facelift"),
        )

    products: list[Product] = []
    for raw in doc.get("products", []):
        sku = _syn(raw.get("sku"), "sku")
        oems = tuple(_syn(o, f"{sku} OEM number") for o in raw.get("oem_numbers", []))
        products.append(
            Product(
                sku=sku,
                title=raw["title"],
                part_type=raw["part_type"],
                condition=Condition(raw["condition"]),
                set_kind=SetKind(raw["set_kind"]),
                provenance=provenance(_ts(raw.get("last_verified_at"), sku), sku),
                brand=raw.get("brand"),
                color=raw.get("color"),
                condition_notes=raw.get("condition_notes"),
                oem_numbers=oems,
            )
        )
    skus = {p.sku for p in products}
    if len(skus) != len(products):
        raise DatasetError("duplicate SKU")

    fitments: list[FitmentRecord] = []
    spec_ids: dict[str, str] = {}
    for raw in doc.get("fitments", []):
        rid = _syn(raw.get("id"), "fitment id")
        sku = raw.get("sku")
        if sku not in skus:
            raise DatasetError(f"{rid}: unknown sku {sku!r}")
        spec_id = raw.get("vehicle_spec")
        if spec_id not in specs:
            raise DatasetError(f"{rid}: unknown vehicle spec {spec_id!r}")
        kind = raw.get("evidence_type")
        evidence = (
            Evidence(
                kind=EvidenceKind(kind),
                ref=raw.get("evidence_ref"),
                verified_by=raw.get("verified_by"),
                verified_at=_ts(raw.get("verified_at"), rid),
            )
            if kind is not None
            else None
        )
        fitments.append(
            FitmentRecord(
                record_id=rid,
                sku=sku,
                vehicle=specs[spec_id],
                status=FitmentStatus(raw["status"]),
                provenance=provenance(_ts(raw.get("verified_at"), rid), rid),
                conditions=_conditions(raw.get("conditions", {}), rid),
                evidence=evidence,
            )
        )
        spec_ids[rid] = spec_id

    components: list[SetComponent] = []
    set_skus = {p.sku for p in products if p.set_kind is not SetKind.SINGLE}
    for raw in doc.get("set_components", []):
        if raw.get("set_sku") not in set_skus or raw.get("component_sku") not in skus:
            raise DatasetError(f"bad set component {raw!r}")
        components.append(
            SetComponent(
                set_sku=raw["set_sku"],
                component_sku=raw["component_sku"],
                qty=_int(raw.get("qty", 1), "qty"),
                present=bool(raw.get("present", True)),
                optional=bool(raw.get("optional", False)),
            )
        )
    for c in components:
        if not c.present and _set_kind(products, c.set_sku) is SetKind.VIRTUAL_SET:
            raise DatasetError(f"{c.set_sku}: a virtual set cannot mark components absent")

    stock: list[StockLine] = []
    for raw in doc.get("stock", []):
        ref = _syn(raw.get("ref"), "stock ref")
        if raw.get("sku") not in skus:
            raise DatasetError(f"{ref}: unknown sku")
        if _set_kind(products, raw["sku"]) is SetKind.VIRTUAL_SET:
            raise DatasetError(f"{ref}: a virtual set has no own stock")
        stock.append(
            StockLine(
                ref=ref,
                sku=raw["sku"],
                location=raw.get("location"),
                physical_qty=_int(raw["physical_qty"], "physical_qty"),
                external_reserved_qty=_int(raw["external_reserved_qty"], "external_reserved_qty"),
                available_qty=_int(raw["available_qty"], "available_qty"),
                verified_at=_ts(raw.get("verified_at"), ref),
            )
        )
    stock_refs = {s.ref for s in stock}
    if len(stock_refs) != len(stock):
        raise DatasetError("duplicate stock ref")

    prices: list[PriceLine] = []
    for raw in doc.get("prices", []):
        if raw.get("sku") not in skus:
            raise DatasetError(f"price for unknown sku {raw.get('sku')!r}")
        prices.append(
            PriceLine(
                sku=raw["sku"],
                amount_minor=_int(raw["amount_minor"], "amount_minor"),
                currency=raw["currency"],
                discount_rule_key=raw.get("discount_rule_key"),
                verified_at=_ts(raw.get("verified_at"), raw["sku"]),
            )
        )

    photos: list[PhotoLine] = []
    for raw in doc.get("photos", []):
        key = raw.get("key")
        if not isinstance(key, str) or not key.startswith(SYNTHETIC_PHOTO_SCHEME):
            raise DatasetError(f"photo key must be a {SYNTHETIC_PHOTO_SCHEME} placeholder")
        if raw.get("stock_ref") not in stock_refs:
            raise DatasetError(f"photo {key}: must belong to a stock record")
        photos.append(
            PhotoLine(
                stock_ref=raw["stock_ref"],
                key=key,
                sort_order=_int(raw.get("sort_order", 1), "sort_order"),
                verified_at=_ts(raw.get("verified_at"), key),
            )
        )

    return SyntheticDataset(
        name=name,
        source=source,
        snapshot_at=snapshot_at,
        vehicle_specs=specs,
        products=tuple(products),
        fitments=tuple(fitments),
        fitment_spec_ids=spec_ids,
        set_components=tuple(components),
        stock=tuple(stock),
        prices=tuple(prices),
        photos=tuple(photos),
    )


def _set_kind(products: list[Product], sku: str) -> SetKind:
    for p in products:
        if p.sku == sku:
            return p.set_kind
    raise DatasetError(f"unknown sku {sku!r}")


def load_synthetic_dataset(path: Path | None = None) -> SyntheticDataset:
    """Read and validate a synthetic dataset file (default: the W213 front bumper fixture)."""
    target = path or DEFAULT_DATASET_PATH
    with target.open(encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict):
        raise DatasetError("dataset root must be an object")
    return parse_dataset(doc)
