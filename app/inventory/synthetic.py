"""SYNTHETIC inventory adapter: serves the made-up fixture dataset through ``InventoryPort``.

For development and tests only (ARCHITECTURE §3). It refuses to start in production mode
(``APP_ENV=production`` or unset, see ``app.catalog.runtime``). Every fact it returns has
``data_origin='synthetic'`` and ``source='synthetic_fixture'``; photo references are
``synthetic://`` placeholders with ``placeholder=True`` and point at no file.

Failure injection (``failure``), switchable at runtime with ``set_failure``:

- ``down``: health ``down``; every read ``unavailable`` (``connection_down``).
- ``slow``: each call waits ``slow_delay_s`` (via the injectable ``sleep``). If that reaches
  ``timeout_s`` the call gives up: reads ``unavailable`` (``timeout``), health ``down``.
  Otherwise the data is served and health is ``degraded`` (``slow``).
- ``stale``: data is served as a cached copy fetched ``stale_age`` ago: reads are ``stale``
  (when older than the freshness policy) and health is ``degraded`` (``stale_data``).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from app.catalog.dataset import SyntheticDataset, load_synthetic_dataset
from app.catalog.runtime import RuntimeMode, SyntheticDataRejected, current_runtime_mode
from app.catalog.types import DataOrigin, Product, Provenance
from app.inventory.port import (
    FreshnessPolicy,
    HealthStatus,
    InventoryHealth,
    InventoryRead,
    ItemSnapshot,
    MatchBasis,
    PhotoRef,
    PriceRecord,
    ProductSearch,
    ReadStatus,
    SearchHit,
    StockRecord,
    normalize_oem,
)


class FailureMode(StrEnum):
    NONE = "none"
    DOWN = "down"
    SLOW = "slow"
    STALE = "stale"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _norm_text(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


class SyntheticInventoryAdapter:
    """``InventoryPort`` over a ``SyntheticDataset``. Read-only; implements no write port."""

    source_name = "synthetic_fixture"

    def __init__(
        self,
        dataset: SyntheticDataset | None = None,
        *,
        mode: RuntimeMode | None = None,
        clock: Callable[[], datetime] = _utcnow,
        sleep: Callable[[float], None] = time.sleep,
        failure: FailureMode = FailureMode.NONE,
        slow_delay_s: float = 2.0,
        timeout_s: float = 5.0,
        stale_age: timedelta = timedelta(hours=6),
        freshness: FreshnessPolicy | None = None,
    ) -> None:
        self.mode = mode if mode is not None else current_runtime_mode()
        if self.mode is RuntimeMode.PRODUCTION:
            raise SyntheticDataRejected("SyntheticInventoryAdapter refuses to start in production")
        self.dataset = dataset if dataset is not None else load_synthetic_dataset()
        if any(p.provenance.data_origin is not DataOrigin.SYNTHETIC for p in self.dataset.products):
            raise SyntheticDataRejected("SyntheticInventoryAdapter serves synthetic data only")
        self._clock = clock
        self._sleep = sleep
        self.failure = failure
        self.slow_delay_s = slow_delay_s
        self.timeout_s = timeout_s
        self.stale_age = stale_age
        self.freshness = freshness or FreshnessPolicy()
        self._last_success_at: datetime | None = None

    def set_failure(self, failure: FailureMode) -> None:
        self.failure = failure

    # -- plumbing -------------------------------------------------------------------------

    def _connect(self) -> tuple[datetime, datetime | None, str | None]:
        """Simulate one round trip. Returns (now, fetched_at, error); ``fetched_at`` is
        ``None`` when the call failed."""
        now = self._clock()
        if self.failure is FailureMode.DOWN:
            return now, None, "connection_down"
        if self.failure is FailureMode.SLOW:
            waited = min(self.slow_delay_s, self.timeout_s)
            self._sleep(waited)
            if self.slow_delay_s >= self.timeout_s:
                return now, None, "timeout"
        if self.failure is FailureMode.STALE:
            fetched_at = now - self.stale_age
        else:
            fetched_at = now
            self._last_success_at = now
        return now, fetched_at, None

    def _provenance(
        self, fetched_at: datetime, verified_at: datetime | None, ref: str | None
    ) -> Provenance:
        return Provenance(self.source_name, DataOrigin.SYNTHETIC, fetched_at, verified_at, ref)

    def _status(self, now: datetime, fetched_at: datetime, max_age: timedelta) -> ReadStatus:
        fresh = self.freshness.is_fresh(fetched_at, now, max_age)
        return ReadStatus.FRESH if fresh else ReadStatus.STALE

    def _product(self, product: Product, fetched_at: datetime) -> Product:
        return replace(
            product,
            provenance=self._provenance(
                fetched_at, product.provenance.verified_at, product.provenance.source_ref
            ),
        )

    def _find(self, sku: str) -> Product | None:
        wanted = sku.strip().upper()
        return next((p for p in self.dataset.products if p.sku.upper() == wanted), None)

    def _stock(self, sku: str, fetched_at: datetime) -> tuple[StockRecord, ...]:
        return tuple(
            StockRecord(
                stock_ref=s.ref,
                sku=s.sku,
                location=s.location,
                physical_qty=s.physical_qty,
                external_reserved_qty=s.external_reserved_qty,
                available_qty=s.available_qty,
                provenance=self._provenance(fetched_at, s.verified_at, s.ref),
            )
            for s in sorted(self.dataset.stock, key=lambda s: s.ref)
            if s.sku == sku
        )

    def _price(self, sku: str, fetched_at: datetime) -> PriceRecord | None:
        line = next((p for p in self.dataset.prices if p.sku == sku), None)
        if line is None:
            return None
        return PriceRecord(
            sku=sku,
            amount_minor=line.amount_minor,
            currency=line.currency,
            provenance=self._provenance(fetched_at, line.verified_at, sku),
            discount_rule_key=line.discount_rule_key,
        )

    # -- InventoryPort ----------------------------------------------------------------------

    def health(self) -> InventoryHealth:
        now, fetched_at, error = self._connect()
        if error is not None:
            return InventoryHealth(
                HealthStatus.DOWN, self.source_name, now, self._last_success_at, error
            )
        if self.failure is FailureMode.STALE:
            return InventoryHealth(
                HealthStatus.DEGRADED, self.source_name, now, fetched_at, "stale_data"
            )
        if self.failure is FailureMode.SLOW:
            return InventoryHealth(HealthStatus.DEGRADED, self.source_name, now, now, "slow")
        return InventoryHealth(HealthStatus.UP, self.source_name, now, now)

    def search_products(self, query: ProductSearch) -> InventoryRead[tuple[SearchHit, ...]]:
        now, fetched_at, error = self._connect()
        if fetched_at is None:
            return InventoryRead(ReadStatus.UNAVAILABLE, None, now, error)
        hits: list[SearchHit] = []
        oem = normalize_oem(query.oem_number) if query.oem_number else None
        vehicle_given = any((query.make, query.model, query.chassis_code))
        for product in sorted(self.dataset.products, key=lambda p: p.sku):
            if query.part_type and product.part_type != query.part_type:
                continue
            basis: list[MatchBasis] = []
            if query.sku is not None:
                if product.sku.upper() != query.sku.strip().upper():
                    continue
                basis.append(MatchBasis.SKU)
            if oem is not None:
                if oem not in {normalize_oem(o) for o in product.oem_numbers}:
                    continue
                basis.append(MatchBasis.OEM_NUMBER)
            if vehicle_given:
                vehicle_basis = self._vehicle_basis(product, query)
                if not vehicle_basis:
                    continue
                basis.extend(vehicle_basis)
            hits.append(SearchHit(self._product(product, fetched_at), tuple(basis)))
        return InventoryRead(
            self._status(now, fetched_at, self.freshness.max_stock_age), tuple(hits), now
        )

    def _vehicle_basis(self, product: Product, query: ProductSearch) -> list[MatchBasis]:
        wanted = {
            "make": query.make,
            "model": query.model,
            "chassis_code": query.chassis_code,
        }
        basis: list[MatchBasis] = []
        for record in self.dataset.fitments:
            if record.sku != product.sku:
                continue
            spec = record.vehicle
            if all(
                v is None or _norm_text(v) == _norm_text(getattr(spec, k))
                for k, v in wanted.items()
            ):
                basis.append(MatchBasis.CATALOG_APPLICABILITY)
                break
        if query.chassis_code and _norm_text(query.chassis_code) in _norm_text(product.title):
            basis.append(MatchBasis.TITLE_MENTION)
        return basis

    def get_item(self, sku: str) -> InventoryRead[ItemSnapshot]:
        now, fetched_at, error = self._connect()
        if fetched_at is None:
            return InventoryRead(ReadStatus.UNAVAILABLE, None, now, error)
        product = self._find(sku)
        if product is None:
            return InventoryRead(ReadStatus.NOT_FOUND, None, now, "unknown_sku")
        snapshot = ItemSnapshot(
            product=self._product(product, fetched_at),
            stock=self._stock(product.sku, fetched_at),
            price=self._price(product.sku, fetched_at),
        )
        max_age = min(self.freshness.max_stock_age, self.freshness.max_price_age)
        return InventoryRead(self._status(now, fetched_at, max_age), snapshot, now)

    def get_stock(self, sku: str) -> InventoryRead[tuple[StockRecord, ...]]:
        now, fetched_at, error = self._connect()
        if fetched_at is None:
            return InventoryRead(ReadStatus.UNAVAILABLE, None, now, error)
        product = self._find(sku)
        if product is None:
            return InventoryRead(ReadStatus.NOT_FOUND, None, now, "unknown_sku")
        return InventoryRead(
            self._status(now, fetched_at, self.freshness.max_stock_age),
            self._stock(product.sku, fetched_at),
            now,
        )

    def get_price(self, sku: str) -> InventoryRead[PriceRecord]:
        now, fetched_at, error = self._connect()
        if fetched_at is None:
            return InventoryRead(ReadStatus.UNAVAILABLE, None, now, error)
        product = self._find(sku)
        price = self._price(product.sku, fetched_at) if product is not None else None
        if price is None:
            reason = "unknown_sku" if product is None else "no_price"
            return InventoryRead(ReadStatus.NOT_FOUND, None, now, reason)
        return InventoryRead(
            self._status(now, fetched_at, self.freshness.max_price_age), price, now
        )

    def get_photos(self, sku: str) -> InventoryRead[tuple[PhotoRef, ...]]:
        now, fetched_at, error = self._connect()
        if fetched_at is None:
            return InventoryRead(ReadStatus.UNAVAILABLE, None, now, error)
        product = self._find(sku)
        if product is None:
            return InventoryRead(ReadStatus.NOT_FOUND, None, now, "unknown_sku")
        refs = {s.ref for s in self.dataset.stock if s.sku == product.sku}
        photos = tuple(
            PhotoRef(
                photo_key=ph.key,
                sku=product.sku,
                stock_ref=ph.stock_ref,
                sort_order=ph.sort_order,
                provenance=self._provenance(fetched_at, ph.verified_at, ph.key),
                placeholder=True,
            )
            for ph in sorted(self.dataset.photos, key=lambda ph: (ph.stock_ref, ph.sort_order))
            if ph.stock_ref in refs
        )
        return InventoryRead(
            self._status(now, fetched_at, self.freshness.max_stock_age), photos, now
        )
