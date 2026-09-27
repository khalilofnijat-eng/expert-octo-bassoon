"""Set completeness and availability (ARCHITECTURE §6.7; set semantics pending B-002, D-033).

Both set models fit:

- ``virtual_set`` (the current proposal): the set has no stock of its own. The number of
  complete sets is ``min(floor(sellable / qty))`` over the required components. A component with
  no sellable unit is a missing item. If any required component's availability is ``unknown``
  (inventory down, stale read), the set is ``unknown`` too: nothing is claimed.
- ``stocked_set``: the warehouse keeps the kit as its own stock line; availability is the kit's
  own claim. Components marked ``present=False`` are known missing items of that kit.

Input claims come from ``app.inventory.port.claim_availability``, so the "never say available
when stock is unknown" rule carries over. Local holds (T-027) are applied by the caller.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.catalog.types import Product, SetComponent, SetKind
from app.inventory.port import AvailabilityClaim, AvailabilityStatus


@dataclass(frozen=True)
class ComponentAvailability:
    component_sku: str
    qty: int
    present: bool
    optional: bool
    claim: AvailabilityClaim | None
    # Complete sets this component alone allows; None when unknown or not applicable.
    set_units: int | None


@dataclass(frozen=True)
class SetAvailability:
    set_sku: str
    set_kind: SetKind
    claim: AvailabilityClaim
    complete_sets: int | None
    components: tuple[ComponentAvailability, ...]
    missing_components: tuple[str, ...]
    unknown_components: tuple[str, ...]

    @property
    def complete(self) -> bool | None:
        """Whether a complete set can be offered; ``None`` when unknown."""
        if self.unknown_components or self.claim.status is AvailabilityStatus.UNKNOWN:
            return None
        return not self.missing_components and self.claim.status is AvailabilityStatus.AVAILABLE


_NO_CLAIM = AvailabilityClaim(AvailabilityStatus.UNKNOWN, None, "no_claim", None)


def set_availability(
    set_product: Product,
    components: Sequence[SetComponent],
    claims: Mapping[str, AvailabilityClaim],
) -> SetAvailability:
    """Evaluate one set. ``claims`` maps SKU → availability claim (components, and the kit
    itself for a stocked set). A missing entry counts as ``unknown``."""
    if set_product.set_kind is SetKind.SINGLE:
        raise ValueError(f"{set_product.sku} is not a set")
    lines = sorted(
        (c for c in components if c.set_sku == set_product.sku), key=lambda c: c.component_sku
    )

    if set_product.set_kind is SetKind.STOCKED_SET:
        own = claims.get(set_product.sku, _NO_CLAIM)
        missing = tuple(c.component_sku for c in lines if not c.present and not c.optional)
        comps = tuple(
            ComponentAvailability(c.component_sku, c.qty, c.present, c.optional, None, None)
            for c in lines
        )
        known = own.status is not AvailabilityStatus.UNKNOWN
        return SetAvailability(
            set_product.sku,
            set_product.set_kind,
            own,
            own.sellable_qty if known else None,
            comps,
            missing,
            () if known else (set_product.sku,),
        )

    comps_list: list[ComponentAvailability] = []
    for c in lines:
        claim = claims.get(c.component_sku, _NO_CLAIM)
        units = (
            (claim.sellable_qty or 0) // c.qty
            if claim.status is not AvailabilityStatus.UNKNOWN
            else None
        )
        comps_list.append(
            ComponentAvailability(c.component_sku, c.qty, c.present, c.optional, claim, units)
        )
    required = [c for c in comps_list if not c.optional]
    unknown = tuple(c.component_sku for c in required if c.set_units is None)
    missing = tuple(c.component_sku for c in required if c.set_units == 0)
    comps = tuple(comps_list)
    if not required:
        claim = AvailabilityClaim(AvailabilityStatus.UNKNOWN, None, "set_has_no_components", None)
        return SetAvailability(set_product.sku, set_product.set_kind, claim, None, comps, (), ())
    if unknown:
        claim = AvailabilityClaim(
            AvailabilityStatus.UNKNOWN, None, "component_unknown:" + ",".join(unknown), None
        )
        return SetAvailability(
            set_product.sku, set_product.set_kind, claim, None, comps, missing, unknown
        )
    complete_sets = min(c.set_units or 0 for c in required)
    as_of = min(
        (c.claim.as_of for c in required if c.claim is not None and c.claim.as_of is not None),
        default=None,
    )
    if complete_sets > 0:
        claim = AvailabilityClaim(AvailabilityStatus.AVAILABLE, complete_sets, None, as_of)
    else:
        claim = AvailabilityClaim(
            AvailabilityStatus.NOT_AVAILABLE, 0, "missing_components:" + ",".join(missing), as_of
        )
    return SetAvailability(
        set_product.sku, set_product.set_kind, claim, complete_sets, comps, missing, ()
    )
