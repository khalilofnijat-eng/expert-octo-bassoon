"""Fitment engine: pure, deterministic, no LLM (ARCHITECTURE §3 "Catalog / fitment engine").

Input: the customer's vehicle attributes (``VehicleQuery``, any subset may be unknown), the
candidate products and their stored ``FitmentRecord`` rows, and an ``EvidencePolicy``.
Output per product: ``verified`` / ``needs_verification`` / ``incompatible``, the evidence list,
reason codes and the vehicle attributes whose answer would resolve it. ``questions_to_ask``
turns the missing attributes of all candidates into one ordered list for the "ask the customer"
step.

How one record is matched against the vehicle
---------------------------------------------
Each attribute the record constrains is ``match``, ``mismatch`` or ``unknown`` (the customer did
not say). Chassis code, make and model: when the customer gave a chassis code that matches, make
and model are taken from the record and not asked. Year: checked whenever the customer gave one
(a year outside the range is a mismatch); it is asked only when the record has a year range but
no facelift split. The facelift is never inferred from the year (model year vs registration year
is ambiguous), so a facelift-specific record needs the facelift answer. Equipment conditions
(trim line, parktronic sensor count, headlamp washers, front camera) must each be known.
Record outcome: ``mismatch`` if anything mismatches, else ``partial`` if anything is unknown,
else ``full``.

How records combine into a verdict (hard rules first)
-----------------------------------------------------
- Evidence is judged by the policy (``app.catalog.evidence``): visual similarity, customer
  statements, LLM output, listing titles and body code alone never count; synthetic evidence
  counts only in test mode and raises in production.
- ``verified`` needs a ``full`` match on a ``verified`` record with accepted evidence **and** at
  least one matched attribute beyond make/model/chassis code. A record that only says "W213"
  therefore never verifies anything (reason ``body_code_only``).
- ``incompatible`` needs accepted evidence: either a ``full`` match on an ``incompatible``
  record, or every record mismatches and at least one mismatching record is ``verified`` with
  accepted evidence (the part's verified applicability excludes this vehicle).
- A verified and an incompatible full match together → ``needs_verification``
  (``conflicting_records``).
- Everything else is ``needs_verification`` with reasons. ``missing_attributes`` lists what to
  ask; it is empty when asking the customer cannot help (no record, unverified record) and the
  owner has to check.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum

from app.catalog.evidence import EvidencePolicy, EvidenceRejection
from app.catalog.types import (
    CONDITION_ATTRIBUTES,
    ConditionScalar,
    ConditionValue,
    DataOrigin,
    EvidenceKind,
    FitmentRecord,
    FitmentStatus,
    Product,
    SetComponent,
    SetKind,
)

# Order in which missing attributes are reported and asked.
ATTRIBUTE_ORDER: tuple[str, ...] = (
    "make",
    "model",
    "chassis_code",
    "year",
    "facelift",
    *CONDITION_ATTRIBUTES,
)
_IDENTITY_ATTRIBUTES = frozenset({"make", "model", "chassis_code"})


@dataclass(frozen=True)
class VehicleQuery:
    """What the customer told us about the car; ``None`` = unknown. These are the customer's
    statements: the engine uses them to select records, never as fitment evidence."""

    make: str | None = None
    model: str | None = None
    chassis_code: str | None = None
    year: int | None = None
    facelift: bool | None = None
    trim_line: str | None = None
    parktronic_sensors: int | None = None
    headlamp_washer: bool | None = None
    front_camera: bool | None = None

    def known(self) -> dict[str, object]:
        return {
            f.name: getattr(self, f.name) for f in fields(self) if getattr(self, f.name) is not None
        }


class Check(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class MatchOutcome(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    MISMATCH = "mismatch"


class FitmentReason(StrEnum):
    VERIFIED_RECORD_MATCHES = "verified_record_matches"
    EXPLICIT_INCOMPATIBLE_RECORD = "explicit_incompatible_record"
    OUTSIDE_VERIFIED_APPLICABILITY = "outside_verified_applicability"
    NO_FITMENT_RECORD = "no_fitment_record"
    MISSING_VEHICLE_ATTRIBUTES = "missing_vehicle_attributes"
    RECORD_NOT_VERIFIED = "record_not_verified"
    EVIDENCE_NOT_ACCEPTED = "evidence_not_accepted"
    BODY_CODE_ONLY = "body_code_only"
    CONFLICTING_RECORDS = "conflicting_records"
    NO_RECORD_MATCHES_VEHICLE = "no_record_matches_vehicle"
    COMPONENT_INCOMPATIBLE = "component_incompatible"
    COMPONENT_NEEDS_VERIFICATION = "component_needs_verification"
    ALL_COMPONENTS_VERIFIED = "all_components_verified"


@dataclass(frozen=True)
class AttributeCheck:
    attribute: str
    required: str
    given: str | None
    outcome: Check


@dataclass(frozen=True)
class EvidenceItem:
    """One record the verdict looked at, with how it matched and whether its evidence counted."""

    record_id: str
    sku: str
    record_status: FitmentStatus
    match: MatchOutcome
    checks: tuple[AttributeCheck, ...]
    evidence_kind: EvidenceKind | None
    evidence_ref: str | None
    evidence_accepted: bool
    evidence_rejection: EvidenceRejection | None
    source: str
    data_origin: DataOrigin
    verified_at: datetime | None


@dataclass(frozen=True)
class FitmentResult:
    sku: str
    status: FitmentStatus
    reasons: tuple[FitmentReason, ...]
    evidence: tuple[EvidenceItem, ...]
    missing_attributes: tuple[str, ...]
    # True when any record or product behind this verdict is synthetic (test data).
    synthetic: bool

    @property
    def customer_can_resolve(self) -> bool:
        """Whether asking the customer for ``missing_attributes`` could settle it."""
        return bool(self.missing_attributes)


def _norm(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return re.sub(r"[\W_]+", "", str(value).casefold())


def _show(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, tuple):
        return "|".join(_show(v) for v in value)
    return str(value)


def _equal(required: ConditionScalar, given: object) -> bool:
    if isinstance(required, bool) or isinstance(given, bool):
        return isinstance(required, bool) and isinstance(given, bool) and required is given
    if isinstance(required, int):
        return isinstance(given, int) and required == given
    return _norm(required) == _norm(given)


def _check_value(attribute: str, required: ConditionValue, given: object) -> AttributeCheck:
    if given is None:
        return AttributeCheck(attribute, _show(required), None, Check.UNKNOWN)
    options = required if isinstance(required, tuple) else (required,)
    ok = any(_equal(option, given) for option in options)
    return AttributeCheck(
        attribute, _show(required), _show(given), Check.MATCH if ok else Check.MISMATCH
    )


def match_record(
    record: FitmentRecord, vehicle: VehicleQuery
) -> tuple[MatchOutcome, tuple[AttributeCheck, ...]]:
    """Match one record against the vehicle (see the module docstring)."""
    spec = record.vehicle
    checks: list[AttributeCheck] = []
    if vehicle.chassis_code is not None:
        chassis = _check_value("chassis_code", spec.chassis_code, vehicle.chassis_code)
        checks.append(chassis)
        for name, required in (("make", spec.make), ("model", spec.model)):
            given = getattr(vehicle, name)
            if given is not None:
                checks.append(_check_value(name, required, given))
    else:
        checks.append(_check_value("make", spec.make, vehicle.make))
        checks.append(_check_value("model", spec.model, vehicle.model))
        checks.append(_check_value("chassis_code", spec.chassis_code, None))

    if spec.year_from is not None or spec.year_to is not None:
        required_years = f"{spec.year_from or ''}-{spec.year_to or ''}"
        if vehicle.year is not None:
            in_range = (spec.year_from is None or vehicle.year >= spec.year_from) and (
                spec.year_to is None or vehicle.year <= spec.year_to
            )
            checks.append(
                AttributeCheck(
                    "year",
                    required_years,
                    str(vehicle.year),
                    Check.MATCH if in_range else Check.MISMATCH,
                )
            )
        elif spec.facelift is None:
            checks.append(AttributeCheck("year", required_years, None, Check.UNKNOWN))

    if spec.facelift is not None:
        checks.append(_check_value("facelift", spec.facelift, vehicle.facelift))

    for attribute in CONDITION_ATTRIBUTES:
        if attribute in record.conditions:
            checks.append(
                _check_value(attribute, record.conditions[attribute], getattr(vehicle, attribute))
            )

    if any(c.outcome is Check.MISMATCH for c in checks):
        outcome = MatchOutcome.MISMATCH
    elif any(c.outcome is Check.UNKNOWN for c in checks):
        outcome = MatchOutcome.PARTIAL
    else:
        outcome = MatchOutcome.FULL
    return outcome, tuple(checks)


def _ordered(attributes: Iterable[str]) -> tuple[str, ...]:
    wanted = set(attributes)
    return tuple(a for a in ATTRIBUTE_ORDER if a in wanted)


def _discriminating(checks: Sequence[AttributeCheck]) -> bool:
    return any(c.outcome is Check.MATCH and c.attribute not in _IDENTITY_ATTRIBUTES for c in checks)


@dataclass(frozen=True)
class _Assessed:
    record: FitmentRecord
    outcome: MatchOutcome
    checks: tuple[AttributeCheck, ...]
    accepted: bool
    rejection: EvidenceRejection | None
    synthetic: bool

    def item(self) -> EvidenceItem:
        ev = self.record.evidence
        return EvidenceItem(
            record_id=self.record.record_id,
            sku=self.record.sku,
            record_status=self.record.status,
            match=self.outcome,
            checks=self.checks,
            evidence_kind=ev.kind if ev else None,
            evidence_ref=ev.ref if ev else None,
            evidence_accepted=self.accepted,
            evidence_rejection=self.rejection,
            source=self.record.provenance.source,
            data_origin=self.record.provenance.data_origin,
            verified_at=ev.verified_at if ev else None,
        )


def evaluate(
    product: Product,
    records: Sequence[FitmentRecord],
    vehicle: VehicleQuery,
    policy: EvidencePolicy,
) -> FitmentResult:
    """Classify one product for one vehicle. ``records`` may contain other products' records;
    only those with ``product.sku`` are used."""
    policy.check_origin(product.provenance, f"product {product.sku}")
    own = sorted((r for r in records if r.sku == product.sku), key=lambda r: r.record_id)
    assessed: list[_Assessed] = []
    for record in own:
        verdict = policy.assess(record)
        outcome, checks = match_record(record, vehicle)
        assessed.append(
            _Assessed(
                record,
                outcome,
                checks,
                verdict.accepted,
                verdict.rejection,
                verdict.synthetic or record.provenance.synthetic,
            )
        )
    synthetic = product.provenance.synthetic or any(a.synthetic for a in assessed)

    def result(
        status: FitmentStatus,
        reasons: Iterable[FitmentReason],
        used: Iterable[_Assessed],
        missing: Iterable[str] = (),
    ) -> FitmentResult:
        unique_reasons = tuple(dict.fromkeys(reasons))
        return FitmentResult(
            sku=product.sku,
            status=status,
            reasons=unique_reasons,
            evidence=tuple(a.item() for a in used),
            missing_attributes=_ordered(missing),
            synthetic=synthetic,
        )

    if not assessed:
        return result(FitmentStatus.NEEDS_VERIFICATION, [FitmentReason.NO_FITMENT_RECORD], [])

    applicable = [a for a in assessed if a.outcome is not MatchOutcome.MISMATCH]
    if not applicable:
        excluding = [
            a for a in assessed if a.record.status is FitmentStatus.VERIFIED and a.accepted
        ]
        if excluding:
            return result(
                FitmentStatus.INCOMPATIBLE,
                [FitmentReason.OUTSIDE_VERIFIED_APPLICABILITY],
                excluding,
            )
        return result(
            FitmentStatus.NEEDS_VERIFICATION,
            [FitmentReason.NO_RECORD_MATCHES_VEHICLE],
            assessed,
        )

    full = [a for a in applicable if a.outcome is MatchOutcome.FULL]
    verified = [
        a
        for a in full
        if a.record.status is FitmentStatus.VERIFIED and a.accepted and _discriminating(a.checks)
    ]
    incompatible = [a for a in full if a.record.status is FitmentStatus.INCOMPATIBLE and a.accepted]
    if verified and incompatible:
        return result(
            FitmentStatus.NEEDS_VERIFICATION,
            [FitmentReason.CONFLICTING_RECORDS],
            verified + incompatible,
        )
    if verified:
        return result(FitmentStatus.VERIFIED, [FitmentReason.VERIFIED_RECORD_MATCHES], verified)
    if incompatible:
        return result(
            FitmentStatus.INCOMPATIBLE, [FitmentReason.EXPLICIT_INCOMPATIBLE_RECORD], incompatible
        )

    reasons: list[FitmentReason] = []
    missing: list[str] = []
    for a in applicable:
        # Asking only helps where a partially matched record could give a definite answer.
        decisive = a.accepted and a.record.status is not FitmentStatus.NEEDS_VERIFICATION
        if a.outcome is MatchOutcome.PARTIAL and decisive:
            reasons.append(FitmentReason.MISSING_VEHICLE_ATTRIBUTES)
            missing.extend(c.attribute for c in a.checks if c.outcome is Check.UNKNOWN)
        if a.record.status is FitmentStatus.NEEDS_VERIFICATION:
            reasons.append(FitmentReason.RECORD_NOT_VERIFIED)
        elif not a.accepted:
            reasons.append(FitmentReason.EVIDENCE_NOT_ACCEPTED)
        elif a.outcome is MatchOutcome.FULL and a.record.status is FitmentStatus.VERIFIED:
            reasons.append(FitmentReason.BODY_CODE_ONLY)
    return result(FitmentStatus.NEEDS_VERIFICATION, reasons, applicable, missing)


def evaluate_candidates(
    products: Sequence[Product],
    records: Sequence[FitmentRecord],
    vehicle: VehicleQuery,
    policy: EvidencePolicy,
) -> tuple[FitmentResult, ...]:
    """``evaluate`` for each product, in the given product order."""
    return tuple(evaluate(p, records, vehicle, policy) for p in products)


def evaluate_set(
    set_product: Product,
    components: Sequence[SetComponent],
    component_results: Mapping[str, FitmentResult],
    own_result: FitmentResult | None = None,
) -> FitmentResult:
    """Combine component verdicts into the set's verdict.

    Members: every non-optional component (for a stocked set only the ones present in the kit)
    plus the set's own result when it has records. Any member ``incompatible`` → incompatible;
    all ``verified`` → verified; otherwise needs_verification. A component without a result is
    treated as ``needs_verification``.
    """
    lines = [c for c in components if c.set_sku == set_product.sku and not c.optional]
    if set_product.set_kind is SetKind.STOCKED_SET:
        lines = [c for c in lines if c.present]
    members: list[FitmentResult] = []
    for line in sorted(lines, key=lambda c: c.component_sku):
        found = component_results.get(line.component_sku)
        members.append(
            found
            if found is not None
            else FitmentResult(
                line.component_sku,
                FitmentStatus.NEEDS_VERIFICATION,
                (FitmentReason.NO_FITMENT_RECORD,),
                (),
                (),
                synthetic=set_product.provenance.synthetic,
            )
        )
    if own_result is not None and FitmentReason.NO_FITMENT_RECORD not in own_result.reasons:
        members.append(own_result)

    synthetic = set_product.provenance.synthetic or any(m.synthetic for m in members)
    evidence = tuple(e for m in members for e in m.evidence)
    missing = _ordered(a for m in members for a in m.missing_attributes)
    if not members:
        return FitmentResult(
            set_product.sku,
            FitmentStatus.NEEDS_VERIFICATION,
            (FitmentReason.NO_FITMENT_RECORD,),
            (),
            (),
            synthetic,
        )
    if any(m.status is FitmentStatus.INCOMPATIBLE for m in members):
        return FitmentResult(
            set_product.sku,
            FitmentStatus.INCOMPATIBLE,
            (FitmentReason.COMPONENT_INCOMPATIBLE,),
            evidence,
            (),
            synthetic,
        )
    if all(m.status is FitmentStatus.VERIFIED for m in members):
        return FitmentResult(
            set_product.sku,
            FitmentStatus.VERIFIED,
            (FitmentReason.ALL_COMPONENTS_VERIFIED,),
            evidence,
            (),
            synthetic,
        )
    return FitmentResult(
        set_product.sku,
        FitmentStatus.NEEDS_VERIFICATION,
        (FitmentReason.COMPONENT_NEEDS_VERIFICATION,),
        evidence,
        missing,
        synthetic,
    )


def questions_to_ask(results: Iterable[FitmentResult]) -> tuple[str, ...]:
    """Missing vehicle attributes over all undecided candidates, most useful first: attributes
    that would settle more candidates come first, ties in ``ATTRIBUTE_ORDER``."""
    counts: dict[str, int] = {}
    for r in results:
        if r.status is FitmentStatus.NEEDS_VERIFICATION:
            for attribute in r.missing_attributes:
                counts[attribute] = counts.get(attribute, 0) + 1
    return tuple(sorted(counts, key=lambda a: (-counts[a], ATTRIBUTE_ORDER.index(a))))
