# SYNTHETIC: dataset documents here are made up.
"""The synthetic dataset loader accepts only clearly labelled synthetic data."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from app.catalog.dataset import DEFAULT_DATASET_PATH, DatasetError, SyntheticDataset, parse_dataset
from app.catalog.types import DataOrigin, SetKind


@pytest.fixture
def doc() -> dict[str, Any]:
    with DEFAULT_DATASET_PATH.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return copy.deepcopy(data)


def test_fixture_is_labelled_synthetic_throughout(dataset: SyntheticDataset) -> None:
    assert dataset.name.startswith("SYN-")
    assert all(p.sku.startswith("SYN-") for p in dataset.products)
    assert all(p.provenance.data_origin is DataOrigin.SYNTHETIC for p in dataset.products)
    assert all(o.startswith("SYN-") for p in dataset.products for o in p.oem_numbers)
    assert all(f.record_id.startswith("SYN-") for f in dataset.fitments)
    assert all(
        s.ref.startswith("SYN-") and (s.location or "SYN-").startswith("SYN-")
        for s in dataset.stock
    )
    assert all(ph.key.startswith("synthetic://placeholder/") for ph in dataset.photos)
    assert {pr.currency for pr in dataset.prices} == {"RUB"}
    # Covers the structure the scenario needs.
    assert {p.condition.value for p in dataset.products} == {"new", "used"}
    assert {p.set_kind for p in dataset.products} == set(SetKind)
    assert any(not c.present for c in dataset.set_components)
    assert any(s.external_reserved_qty > 0 for s in dataset.stock)
    assert any(s.available_qty == 0 for s in dataset.stock)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(data_origin="real"), "data_origin"),
        (lambda d: d["products"][0].update(sku="W213-FB-001"), "SYN-"),
        (lambda d: d["products"][0].update(oem_numbers=["X-0000-TEST"]), "SYN-"),
        (lambda d: d["photos"][0].update(key="https://example.invalid/p.jpg"), "placeholder"),
        (lambda d: d["photos"][0].update(stock_ref="SYN-STK-999"), "stock record"),
        (lambda d: d["fitments"][0].update(vehicle_spec="SYN-VS-NOPE"), "vehicle spec"),
        (
            lambda d: d["stock"].append(
                {**d["stock"][0], "ref": "SYN-STK-900", "sku": "SYN-W213-FBSET-001"}
            ),
            "virtual set",
        ),
        (lambda d: d["set_components"][0].update(present=False), "virtual set"),
        (lambda d: d.update(snapshot_at="2026-09-27T08:00:00"), "UTC offset"),
    ],
)
def test_loader_rejects_unlabelled_or_malformed_data(
    doc: dict[str, Any], mutate: Any, message: str
) -> None:
    mutate(doc)
    with pytest.raises(DatasetError, match=message):
        parse_dataset(doc)


def test_unknown_condition_key_in_fixture_is_rejected(doc: dict[str, Any]) -> None:
    doc["fitments"][0]["conditions"]["paint_code"] = "SYN-1"
    with pytest.raises(ValueError, match="unknown fitment condition"):
        parse_dataset(doc)
