# SYNTHETIC: helpers that build made-up catalog data for tests.
"""Shared test helpers for tests/catalog and tests/inventory."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.catalog.dataset import SyntheticDataset, load_synthetic_dataset
from app.catalog.runtime import RuntimeMode
from app.catalog.types import (
    Condition,
    DataOrigin,
    Evidence,
    EvidenceKind,
    FitmentRecord,
    FitmentStatus,
    Product,
    Provenance,
    SetKind,
    VehicleSpec,
)
from app.inventory.synthetic import FailureMode, SyntheticInventoryAdapter

NOW = datetime(2026, 9, 27, 9, 0, tzinfo=UTC)
VERIFIED_AT = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)

W213_PRE = VehicleSpec("Mercedes-Benz", "E-Class", "W213", 2016, 2020, facelift=False)
W213_POST = VehicleSpec("Mercedes-Benz", "E-Class", "W213", 2020, 2023, facelift=True)
W213_ANY = VehicleSpec("Mercedes-Benz", "E-Class", "W213")


class FakeClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now
        self.slept: list[float] = []

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += timedelta(seconds=seconds)


def make_adapter(
    dataset: SyntheticDataset | None = None,
    *,
    failure: FailureMode = FailureMode.NONE,
    clock: FakeClock | None = None,
    **kwargs: Any,
) -> tuple[SyntheticInventoryAdapter, FakeClock]:
    clk = clock or FakeClock()
    adapter = SyntheticInventoryAdapter(
        dataset if dataset is not None else load_synthetic_dataset(),
        mode=RuntimeMode.TEST,
        clock=clk,
        sleep=clk.sleep,
        failure=failure,
        **kwargs,
    )
    return adapter, clk


def provenance(origin: DataOrigin = DataOrigin.SYNTHETIC, ref: str | None = None) -> Provenance:
    source = "synthetic_fixture" if origin is DataOrigin.SYNTHETIC else "test-source"
    return Provenance(source, origin, NOW, VERIFIED_AT, ref)


def product(sku: str, origin: DataOrigin | None = None, **kw: Any) -> Product:
    """``SYN-`` SKUs are synthetic. Other SKUs are labelled real ONLY to exercise the
    production code path in memory; their values are made up too."""
    if origin is None:
        origin = DataOrigin.SYNTHETIC if sku.startswith("SYN-") else DataOrigin.REAL
    defaults: dict[str, Any] = {
        "title": f"{sku} test part",
        "part_type": "front_grille",
        "condition": Condition.NEW,
        "set_kind": SetKind.SINGLE,
    }
    defaults.update(kw)
    return Product(sku=sku, provenance=provenance(origin, sku), **defaults)


RecordFactory = Callable[..., FitmentRecord]


def record(
    record_id: str,
    sku: str,
    *,
    vehicle: VehicleSpec = W213_PRE,
    status: FitmentStatus = FitmentStatus.VERIFIED,
    kind: EvidenceKind | None = EvidenceKind.SYNTHETIC_FIXTURE,
    ref: str | None = "SYN-EVID",
    verified_at: datetime | None = VERIFIED_AT,
    origin: DataOrigin | None = None,
    **conditions: Any,
) -> FitmentRecord:
    if origin is None:
        origin = DataOrigin.SYNTHETIC if sku.startswith("SYN-") else DataOrigin.REAL
    evidence = Evidence(kind, ref, "tester", verified_at) if kind is not None else None
    return FitmentRecord(
        record_id=record_id,
        sku=sku,
        vehicle=vehicle,
        status=status,
        provenance=provenance(origin, record_id),
        conditions=conditions,
        evidence=evidence,
    )
