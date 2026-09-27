"""Catalog domain types: provenance, products, vehicle applicability, fitment records, sets.

These are plain immutable values used by the fitment engine, the set logic and the inventory
port. They are independent of the database (``app.db.models`` holds the tables, §5) and of any
warehouse software (B-002: unknown). Field meanings that depend on the owner's warehouse system
are marked "B-002".
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

SYNTHETIC_SKU_PREFIX = "SYN-"


class DataOrigin(StrEnum):
    """Where a row or fact came from. ``synthetic`` data is made up for development and tests."""

    REAL = "real"
    SYNTHETIC = "synthetic"


class Condition(StrEnum):
    NEW = "new"
    USED = "used"


class SetKind(StrEnum):
    """``virtual_set``: no own stock, availability comes from the components (§6.7 proposal,
    D-033). ``stocked_set``: the warehouse keeps the kit as its own stock line. Which one the
    owner's warehouse uses is B-002; both fit the model."""

    SINGLE = "single"
    VIRTUAL_SET = "virtual_set"
    STOCKED_SET = "stocked_set"


class FitmentStatus(StrEnum):
    VERIFIED = "verified"
    NEEDS_VERIFICATION = "needs_verification"
    INCOMPATIBLE = "incompatible"


class EvidenceKind(StrEnum):
    """Kinds of fitment evidence.

    Only ``QUALIFYING_EVIDENCE_KINDS`` can make a record ``verified`` (the DB enforces the same
    list with a CHECK). ``synthetic_fixture`` qualifies only in test mode and only on synthetic
    rows. The remaining kinds may be recorded as hints but never verify anything.
    """

    OEM_CATALOG = "oem_catalog"
    MANUFACTURER_DOC = "manufacturer_doc"
    OWNER_CONFIRMED = "owner_confirmed"
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    # Never evidence (owner request §6, ARCHITECTURE §3):
    VISUAL_SIMILARITY = "visual_similarity"
    CUSTOMER_STATEMENT = "customer_statement"
    LLM_OUTPUT = "llm_output"
    LISTING_TITLE = "listing_title"
    BODY_CODE_ONLY = "body_code_only"


QUALIFYING_EVIDENCE_KINDS: frozenset[EvidenceKind] = frozenset(
    {EvidenceKind.OEM_CATALOG, EvidenceKind.MANUFACTURER_DOC, EvidenceKind.OWNER_CONFIRMED}
)
NON_EVIDENCE_KINDS: frozenset[EvidenceKind] = frozenset(
    {
        EvidenceKind.VISUAL_SIMILARITY,
        EvidenceKind.CUSTOMER_STATEMENT,
        EvidenceKind.LLM_OUTPUT,
        EvidenceKind.LISTING_TITLE,
        EvidenceKind.BODY_CODE_ONLY,
    }
)


def _require_aware(name: str, value: datetime | None) -> None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True)
class Provenance:
    """Where a fact came from and how old it is. Every fact the port returns carries one.

    ``fetched_at``: when we read it from the source. ``verified_at``: when the source says the
    fact was last checked (e.g. a stock count or a catalog check); ``None`` = never verified.
    """

    source: str
    data_origin: DataOrigin
    fetched_at: datetime
    verified_at: datetime | None
    source_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("source must not be empty")
        _require_aware("fetched_at", self.fetched_at)
        _require_aware("verified_at", self.verified_at)

    @property
    def synthetic(self) -> bool:
        return self.data_origin is DataOrigin.SYNTHETIC


@dataclass(frozen=True)
class Product:
    """A sellable product (SKU). Colour and condition live here: a used part is usually its own
    SKU. ``oem_numbers`` are as written by the source; search normalises them."""

    sku: str
    title: str
    part_type: str
    condition: Condition
    set_kind: SetKind
    provenance: Provenance
    brand: str | None = None
    color: str | None = None
    condition_notes: str | None = None
    oem_numbers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        is_syn_sku = self.sku.startswith(SYNTHETIC_SKU_PREFIX)
        if self.provenance.synthetic != is_syn_sku:
            raise ValueError(
                f"{self.sku}: synthetic products must use the {SYNTHETIC_SKU_PREFIX!r} SKU "
                "prefix and real products must not"
            )


@dataclass(frozen=True)
class SetComponent:
    """One component line of a set. ``present=False`` is only meaningful for a stocked set: the
    kit as stocked lacks this component (a known missing item)."""

    set_sku: str
    component_sku: str
    qty: int = 1
    present: bool = True
    optional: bool = False

    def __post_init__(self) -> None:
        if self.qty < 1:
            raise ValueError("qty must be >= 1")


@dataclass(frozen=True)
class VehicleSpec:
    """A vehicle applicability range. ``facelift``: ``False`` = pre-facelift, ``True`` =
    facelift, ``None`` = the record does not distinguish."""

    make: str
    model: str
    chassis_code: str
    year_from: int | None = None
    year_to: int | None = None
    facelift: bool | None = None

    def __post_init__(self) -> None:
        if (
            self.year_from is not None
            and self.year_to is not None
            and self.year_from > self.year_to
        ):
            raise ValueError("year_from must be <= year_to")


# Equipment/variant attributes a fitment record may require, in the order questions are asked.
# Values: trim_line → text; parktronic_sensors → int (sensor count); the rest → bool.
CONDITION_ATTRIBUTES: tuple[str, ...] = (
    "trim_line",
    "parktronic_sensors",
    "headlamp_washer",
    "front_camera",
)
BOOL_ATTRIBUTES = frozenset({"headlamp_washer", "front_camera"})
INT_ATTRIBUTES = frozenset({"parktronic_sensors"})
TEXT_ATTRIBUTES = frozenset({"trim_line"})

ConditionScalar = str | int | bool
# A required value, or a tuple meaning "any of these".
ConditionValue = ConditionScalar | tuple[ConditionScalar, ...]


def validate_conditions(conditions: Mapping[str, ConditionValue]) -> None:
    """Reject unknown condition keys and wrongly typed values (the engine must not guess)."""
    for key, value in conditions.items():
        if key not in CONDITION_ATTRIBUTES:
            raise ValueError(f"unknown fitment condition {key!r}")
        for item in value if isinstance(value, tuple) else (value,):
            if key in BOOL_ATTRIBUTES:
                ok = isinstance(item, bool)
            elif key in INT_ATTRIBUTES:
                ok = isinstance(item, int) and not isinstance(item, bool)
            else:
                ok = isinstance(item, str) and bool(item)
            if not ok:
                raise ValueError(f"bad value for condition {key!r}: {item!r}")


@dataclass(frozen=True)
class Evidence:
    kind: EvidenceKind
    ref: str | None
    verified_by: str | None = None
    verified_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_aware("verified_at", self.verified_at)


@dataclass(frozen=True)
class FitmentRecord:
    """One stored statement "product X, on vehicles matching ``vehicle`` + ``conditions``, has
    status S, based on ``evidence``". The engine combines records; a record alone is not a
    verdict (a ``verified`` record still has to match the customer's vehicle)."""

    record_id: str
    sku: str
    vehicle: VehicleSpec
    status: FitmentStatus
    provenance: Provenance
    conditions: Mapping[str, ConditionValue] = field(default_factory=dict)
    evidence: Evidence | None = None

    def __post_init__(self) -> None:
        validate_conditions(self.conditions)
