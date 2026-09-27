"""Inventory port: the read-only interface to the owner's warehouse/accounting system.

The real system is UNKNOWN (B-002), so only this interface and a synthetic adapter exist
(``app.inventory.synthetic``). A real adapter is written after T-007.

Contract for every adapter
--------------------------
- Read methods never raise for connectivity problems. They return an ``InventoryRead`` whose
  ``status`` is ``fresh``, ``stale``, ``unavailable`` or ``not_found``; callers must look at it
  (or call ``fresh_value()``, which raises unless the read is fresh).
- Every fact carries a ``Provenance``: ``source``, ``data_origin``, ``fetched_at`` and
  ``verified_at``. Staleness is judged on ``fetched_at`` with ``FreshnessPolicy``.
- ``health()`` reports ``up`` / ``degraded`` / ``down``; ``/readyz`` and the alerting use it
  (§6.11).
- Availability and price are only ever claimed through ``claim_availability`` and
  ``claim_price``. They return ``unknown`` unless the inventory is not ``down`` and the read is
  fresh, so "stock connection down → never say available" and "price uncertain → no exact
  price" (owner request §7, ARCHITECTURE §6.11/§9.1) hold in one place.
- Photos are references only (``PhotoRef``) and always belong to one stock record (§8).
- There is no write side in v1 (MA-5/D-019). ``InventoryWritePort`` documents the shape and
  ``UnimplementedInventoryWrites`` refuses every call until B-002 is answered.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from app.catalog.types import Product, Provenance

T = TypeVar("T")


class HealthStatus(StrEnum):
    UP = "up"
    DEGRADED = "degraded"
    DOWN = "down"


class ReadStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    # The source answered and has no such item (or no price for it).
    NOT_FOUND = "not_found"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    NOT_AVAILABLE = "not_available"
    UNKNOWN = "unknown"


class PriceStatus(StrEnum):
    EXACT = "exact"
    UNKNOWN = "unknown"


class InventoryNotFresh(RuntimeError):
    """``fresh_value()`` was called on a stale or unavailable read."""


class InventoryWriteNotSupported(NotImplementedError):
    """External reservation/order writes are not implemented (MA-5, pending B-002)."""


@dataclass(frozen=True)
class FreshnessPolicy:
    """Maximum age of a fact's ``fetched_at`` before it is stale.

    The defaults are placeholders: the real sync cadence depends on the warehouse system
    (B-002) and becomes a setting then.
    """

    max_stock_age: timedelta = timedelta(minutes=15)
    max_price_age: timedelta = timedelta(minutes=15)

    def is_fresh(self, fetched_at: datetime, now: datetime, max_age: timedelta) -> bool:
        return fetched_at <= now and now - fetched_at <= max_age


@dataclass(frozen=True)
class InventoryHealth:
    status: HealthStatus
    source: str
    checked_at: datetime
    last_success_at: datetime | None
    reason: str | None = None


@dataclass(frozen=True)
class InventoryRead(Generic[T]):
    """The result of one read. ``value`` is ``None`` when ``status`` is ``unavailable``; a
    ``stale`` read keeps the old value for display to the owner, never for customer claims."""

    status: ReadStatus
    value: T | None
    checked_at: datetime
    reason: str | None = None

    def fresh_value(self) -> T:
        if self.status is not ReadStatus.FRESH or self.value is None:
            raise InventoryNotFresh(f"inventory read is {self.status.value}: {self.reason}")
        return self.value


@dataclass(frozen=True)
class StockRecord:
    """One stock line (warehouse location). Quantity meanings are B-002:
    ``available_qty`` is what the warehouse says can be sold now (the "sellable" quantity);
    ``external_reserved_qty`` is reserved in the warehouse system; local holds (T-027) are not
    part of this record."""

    stock_ref: str
    sku: str
    location: str | None
    physical_qty: int
    external_reserved_qty: int
    available_qty: int
    provenance: Provenance

    def __post_init__(self) -> None:
        if min(self.physical_qty, self.external_reserved_qty, self.available_qty) < 0:
            raise ValueError("stock quantities must be >= 0")


@dataclass(frozen=True)
class PriceRecord:
    """Current price in integer minor units (RUB → kopecks). ``discount_rule_key`` names the
    business rule that holds the allowed discount; the value is never stored here (§9.2)."""

    sku: str
    amount_minor: int
    currency: str
    provenance: Provenance
    discount_rule_key: str | None = None

    def __post_init__(self) -> None:
        if self.amount_minor < 0:
            raise ValueError("amount_minor must be >= 0")
        if not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValueError("currency must be an ISO 4217 code")


@dataclass(frozen=True)
class PhotoRef:
    """A reference to a photo of one stock record. No image bytes pass through the port.
    ``placeholder=True`` marks synthetic keys that point at no file."""

    photo_key: str
    sku: str
    stock_ref: str
    sort_order: int
    provenance: Provenance
    placeholder: bool = False


@dataclass(frozen=True)
class ItemSnapshot:
    product: Product
    stock: tuple[StockRecord, ...]
    price: PriceRecord | None


@dataclass(frozen=True)
class ProductSearch:
    """Search criteria. Vehicle criteria only produce *candidates* (``match_basis`` says why);
    whether a part fits is decided by the fitment engine, never by the search."""

    sku: str | None = None
    oem_number: str | None = None
    make: str | None = None
    model: str | None = None
    chassis_code: str | None = None
    part_type: str | None = None

    def __post_init__(self) -> None:
        if not any((self.sku, self.oem_number, self.make, self.model, self.chassis_code)):
            raise ValueError("search needs a SKU, an OEM number or a vehicle attribute")


class MatchBasis(StrEnum):
    SKU = "sku"
    OEM_NUMBER = "oem_number"
    CATALOG_APPLICABILITY = "catalog_applicability"
    TITLE_MENTION = "title_mention"


@dataclass(frozen=True)
class SearchHit:
    product: Product
    match_basis: tuple[MatchBasis, ...]


@dataclass(frozen=True)
class AvailabilityClaim:
    status: AvailabilityStatus
    sellable_qty: int | None
    reason: str | None
    as_of: datetime | None


@dataclass(frozen=True)
class PriceClaim:
    status: PriceStatus
    amount_minor: int | None
    currency: str | None
    reason: str | None
    as_of: datetime | None


def normalize_oem(value: str) -> str:
    """``A 213 885-14 00`` → ``A2138851400``: case-folded, spaces/dashes/dots removed."""
    return re.sub(r"[\s\-./]+", "", value).upper()


@runtime_checkable
class InventoryPort(Protocol):
    """Read-only inventory interface (ARCHITECTURE §3)."""

    source_name: str

    def health(self) -> InventoryHealth: ...

    def search_products(self, query: ProductSearch) -> InventoryRead[tuple[SearchHit, ...]]: ...

    def get_item(self, sku: str) -> InventoryRead[ItemSnapshot]: ...

    def get_stock(self, sku: str) -> InventoryRead[tuple[StockRecord, ...]]: ...

    def get_price(self, sku: str) -> InventoryRead[PriceRecord]: ...

    def get_photos(self, sku: str) -> InventoryRead[tuple[PhotoRef, ...]]: ...


@dataclass(frozen=True)
class ExternalReservationRequest:
    idempotency_key: str
    lines: tuple[tuple[str, int], ...]  # (stock_ref, qty)


@runtime_checkable
class InventoryWritePort(Protocol):
    """Write side of the warehouse system. NOT IMPLEMENTED in v1 (MA-5/D-019): whether the
    owner's system accepts reservations or orders, and how, is B-002. Local holds live in our
    own DB (T-027); the owner enters them in the warehouse system by hand."""

    def reserve_external(self, request: ExternalReservationRequest) -> str: ...

    def create_order_external(self, request: ExternalReservationRequest) -> str: ...


class UnimplementedInventoryWrites:
    """Placeholder that refuses every write; no adapter implements writes until B-002."""

    def reserve_external(self, request: ExternalReservationRequest) -> str:
        raise InventoryWriteNotSupported("external reservation is pending B-002 (MA-5)")

    def create_order_external(self, request: ExternalReservationRequest) -> str:
        raise InventoryWriteNotSupported("external order creation is pending B-002 (MA-5)")


def _gate(health: InventoryHealth, read: InventoryRead[Any]) -> str | None:
    """Why no claim may be made, or ``None`` if the read may back a claim."""
    if health.status is HealthStatus.DOWN:
        return f"inventory_down:{health.reason or 'unknown'}"
    if read.status is not ReadStatus.FRESH or read.value is None:
        return f"read_{read.status.value}:{read.reason or 'unknown'}"
    return None


def claim_availability(
    read: InventoryRead[ItemSnapshot] | InventoryRead[tuple[StockRecord, ...]],
    health: InventoryHealth,
) -> AvailabilityClaim:
    """The only way to turn stock data into an availability statement.

    ``unknown`` when the inventory is down or the read is not fresh; otherwise ``available``
    with the summed ``available_qty`` or ``not_available`` when it is 0.
    """
    blocked = _gate(health, read)
    if blocked is not None:
        return AvailabilityClaim(AvailabilityStatus.UNKNOWN, None, blocked, None)
    value = read.value
    stock: Sequence[StockRecord] = value.stock if isinstance(value, ItemSnapshot) else value or ()
    qty = sum(s.available_qty for s in stock)
    as_of = min((s.provenance.fetched_at for s in stock), default=read.checked_at)
    if qty > 0:
        return AvailabilityClaim(AvailabilityStatus.AVAILABLE, qty, None, as_of)
    return AvailabilityClaim(AvailabilityStatus.NOT_AVAILABLE, 0, "no_sellable_stock", as_of)


def claim_price(
    read: InventoryRead[ItemSnapshot] | InventoryRead[PriceRecord],
    health: InventoryHealth,
) -> PriceClaim:
    """Exact price only from a fresh read while the inventory is not down; else ``unknown``."""
    blocked = _gate(health, read)
    if blocked is not None:
        return PriceClaim(PriceStatus.UNKNOWN, None, None, blocked, None)
    value = read.value
    price = value.price if isinstance(value, ItemSnapshot) else value
    if price is None:
        return PriceClaim(PriceStatus.UNKNOWN, None, None, "no_price", None)
    return PriceClaim(
        PriceStatus.EXACT,
        price.amount_minor,
        price.currency,
        None,
        price.provenance.fetched_at,
    )
