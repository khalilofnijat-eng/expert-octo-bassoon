# SYNTHETIC: the adapter serves the made-up W213 dataset only.
"""Inventory port contract on the synthetic adapter: provenance, failure modes, claims."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.catalog.dataset import SyntheticDataset
from app.catalog.runtime import RuntimeMode, SyntheticDataRejected
from app.catalog.sets import set_availability
from app.catalog.types import DataOrigin, Provenance
from app.inventory.port import (
    AvailabilityStatus,
    ExternalReservationRequest,
    FreshnessPolicy,
    HealthStatus,
    InventoryNotFresh,
    InventoryPort,
    InventoryWriteNotSupported,
    InventoryWritePort,
    MatchBasis,
    PriceStatus,
    ProductSearch,
    ReadStatus,
    UnimplementedInventoryWrites,
    claim_availability,
    claim_price,
    normalize_oem,
)
from app.inventory.synthetic import FailureMode, SyntheticInventoryAdapter
from tests.catalog.helpers import NOW, make_adapter

SKU = "SYN-W213-FB-001"


def _all_provenance(adapter: SyntheticInventoryAdapter) -> list[Provenance]:
    item = adapter.get_item(SKU).fresh_value()
    out = [item.product.provenance, *(s.provenance for s in item.stock)]
    assert item.price is not None
    out.append(item.price.provenance)
    out.extend(p.provenance for p in adapter.get_photos(SKU).fresh_value())
    out.extend(
        h.product.provenance for h in adapter.search_products(ProductSearch(sku=SKU)).fresh_value()
    )
    return out


def test_adapter_implements_read_port_but_no_write_port(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset)
    assert isinstance(adapter, InventoryPort)
    assert not isinstance(adapter, InventoryWritePort)


def test_write_side_is_explicitly_unimplemented() -> None:
    writes = UnimplementedInventoryWrites()
    assert isinstance(writes, InventoryWritePort)
    request = ExternalReservationRequest("SYN-idem-1", (("SYN-STK-001", 1),))
    with pytest.raises(InventoryWriteNotSupported, match="B-002"):
        writes.reserve_external(request)
    with pytest.raises(InventoryWriteNotSupported, match="B-002"):
        writes.create_order_external(request)


def test_every_fact_carries_source_fetched_and_verified_at(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset)
    facts = _all_provenance(adapter)
    assert len(facts) >= 6
    for p in facts:
        assert p.source == "synthetic_fixture"
        assert p.data_origin is DataOrigin.SYNTHETIC
        assert p.fetched_at == NOW
        assert p.verified_at is not None and p.verified_at < NOW


def test_refuses_to_start_in_production(dataset: SyntheticDataset) -> None:
    with pytest.raises(SyntheticDataRejected):
        SyntheticInventoryAdapter(dataset, mode=RuntimeMode.PRODUCTION)


def test_refuses_to_start_when_app_env_unset(
    dataset: SyntheticDataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(SyntheticDataRejected):
        SyntheticInventoryAdapter(dataset)
    monkeypatch.setenv("APP_ENV", "development")
    assert SyntheticInventoryAdapter(dataset).mode is RuntimeMode.DEVELOPMENT


def test_search_by_sku_oem_and_vehicle(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset)
    by_sku = adapter.search_products(ProductSearch(sku="syn-w213-fb-001")).fresh_value()
    assert [(h.product.sku, h.match_basis) for h in by_sku] == [(SKU, (MatchBasis.SKU,))]
    by_oem = adapter.search_products(ProductSearch(oem_number="syn a213 885-0001")).fresh_value()
    assert [h.product.sku for h in by_oem] == [SKU]
    assert normalize_oem("SYN-A213 885.0001") == normalize_oem("syn-a213-885-0001")
    by_vehicle = adapter.search_products(
        ProductSearch(make="Mercedes-Benz", chassis_code="w213", part_type="lower_grille")
    ).fresh_value()
    assert [h.product.sku for h in by_vehicle] == ["SYN-W213-LG-001", "SYN-W213-LG-002"]
    none = adapter.search_products(ProductSearch(chassis_code="SYN-X999")).fresh_value()
    assert none == ()
    with pytest.raises(ValueError):
        ProductSearch(part_type="front_grille")


def test_unknown_sku_is_not_found_not_unavailable(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset)
    read = adapter.get_item("SYN-NOPE")
    assert read.status is ReadStatus.NOT_FOUND
    claim = claim_availability(read, adapter.health())
    assert claim.status is AvailabilityStatus.UNKNOWN
    # A virtual set has no own price.
    assert adapter.get_price("SYN-W213-FBSET-001").status is ReadStatus.NOT_FOUND


# --- Stock connection down: never say "available" --------------------------------------------


def test_connection_down_blocks_availability_and_price_claims(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset)
    assert claim_availability(adapter.get_item(SKU), adapter.health()).status is (
        AvailabilityStatus.AVAILABLE
    )

    adapter.set_failure(FailureMode.DOWN)
    health = adapter.health()
    assert health.status is HealthStatus.DOWN
    assert health.reason == "connection_down"
    assert health.last_success_at == NOW  # the successful call above
    read = adapter.get_item(SKU)
    assert read.status is ReadStatus.UNAVAILABLE and read.value is None
    with pytest.raises(InventoryNotFresh):
        read.fresh_value()
    availability = claim_availability(read, health)
    assert availability.status is AvailabilityStatus.UNKNOWN
    assert availability.sellable_qty is None
    assert availability.reason is not None and availability.reason.startswith("inventory_down")
    price = claim_price(read, health)
    assert (price.status, price.amount_minor) == (PriceStatus.UNKNOWN, None)
    for method in (
        adapter.search_products,
        adapter.get_photos,
        adapter.get_stock,
        adapter.get_price,
    ):
        arg = ProductSearch(sku=SKU) if method == adapter.search_products else SKU
        assert method(arg).status is ReadStatus.UNAVAILABLE  # type: ignore[operator]


def test_health_down_overrides_a_fresh_read(dataset: SyntheticDataset) -> None:
    """A read taken just before the connection dropped still must not back a claim."""
    adapter, _ = make_adapter(dataset)
    read = adapter.get_item(SKU)
    adapter.set_failure(FailureMode.DOWN)
    assert claim_availability(read, adapter.health()).status is AvailabilityStatus.UNKNOWN


def test_connection_down_makes_virtual_set_unknown(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset, failure=FailureMode.DOWN)
    set_product = dataset.product("SYN-W213-FBSET-001")
    health = adapter.health()
    claims = {
        c.component_sku: claim_availability(adapter.get_stock(c.component_sku), health)
        for c in dataset.set_components
    }
    view = set_availability(set_product, dataset.set_components, claims)
    assert view.claim.status is AvailabilityStatus.UNKNOWN
    assert view.complete is None
    assert view.complete_sets is None


# --- Stale data ------------------------------------------------------------------------------


def test_stale_data_is_served_but_never_claimed(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset, failure=FailureMode.STALE, stale_age=timedelta(hours=6))
    health = adapter.health()
    assert health.status is HealthStatus.DEGRADED
    assert health.reason == "stale_data"
    read = adapter.get_item(SKU)
    assert read.status is ReadStatus.STALE
    assert read.value is not None  # kept for the owner's screen
    assert read.value.stock[0].provenance.fetched_at == NOW - timedelta(hours=6)
    with pytest.raises(InventoryNotFresh):
        read.fresh_value()
    assert claim_availability(read, health).status is AvailabilityStatus.UNKNOWN
    assert claim_price(read, health).status is PriceStatus.UNKNOWN


def test_staleness_follows_the_freshness_policy(dataset: SyntheticDataset) -> None:
    lenient = FreshnessPolicy(max_stock_age=timedelta(days=1), max_price_age=timedelta(days=1))
    adapter, _ = make_adapter(
        dataset, failure=FailureMode.STALE, stale_age=timedelta(hours=6), freshness=lenient
    )
    assert adapter.get_item(SKU).status is ReadStatus.FRESH
    strict = FreshnessPolicy(max_stock_age=timedelta(days=1), max_price_age=timedelta(minutes=5))
    adapter, _ = make_adapter(
        dataset, failure=FailureMode.STALE, stale_age=timedelta(hours=6), freshness=strict
    )
    assert adapter.get_stock(SKU).status is ReadStatus.FRESH
    assert adapter.get_price(SKU).status is ReadStatus.STALE
    assert adapter.get_item(SKU).status is ReadStatus.STALE


def test_future_fetched_at_is_not_fresh() -> None:
    policy = FreshnessPolicy()
    assert not policy.is_fresh(NOW + timedelta(seconds=1), NOW, timedelta(minutes=15))


# --- Slow source -----------------------------------------------------------------------------


def test_slow_source_within_timeout_is_degraded_but_usable(dataset: SyntheticDataset) -> None:
    adapter, clock = make_adapter(dataset, failure=FailureMode.SLOW, slow_delay_s=1.5, timeout_s=5)
    health = adapter.health()
    assert (health.status, health.reason) == (HealthStatus.DEGRADED, "slow")
    read = adapter.get_item(SKU)
    assert read.status is ReadStatus.FRESH
    assert claim_availability(read, health).status is AvailabilityStatus.AVAILABLE
    assert clock.slept == [1.5, 1.5]


def test_slow_source_beyond_timeout_is_unavailable(dataset: SyntheticDataset) -> None:
    adapter, clock = make_adapter(dataset, failure=FailureMode.SLOW, slow_delay_s=30, timeout_s=5)
    health = adapter.health()
    assert (health.status, health.reason) == (HealthStatus.DOWN, "timeout")
    read = adapter.get_item(SKU)
    assert (read.status, read.reason) == (ReadStatus.UNAVAILABLE, "timeout")
    assert claim_availability(read, health).status is AvailabilityStatus.UNKNOWN
    assert clock.slept == [5, 5]  # gives up at the timeout, never waits longer


def test_recovers_after_failure_clears(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset, failure=FailureMode.DOWN)
    assert adapter.health().status is HealthStatus.DOWN
    adapter.set_failure(FailureMode.NONE)
    health = adapter.health()
    assert health.status is HealthStatus.UP
    assert claim_availability(adapter.get_item(SKU), health).status is (
        AvailabilityStatus.AVAILABLE
    )
