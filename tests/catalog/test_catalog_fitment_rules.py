# SYNTHETIC: every product, record and evidence reference here is made up.
"""Fitment engine hard rules, on small in-memory record sets."""

from __future__ import annotations

import random

import pytest

from app.catalog.evidence import EvidencePolicy, EvidenceRejection
from app.catalog.fitment import (
    Check,
    FitmentReason,
    MatchOutcome,
    VehicleQuery,
    evaluate,
    evaluate_candidates,
    evaluate_set,
    match_record,
    questions_to_ask,
)
from app.catalog.runtime import (
    RuntimeMode,
    SyntheticDataRejected,
    current_runtime_mode,
)
from app.catalog.types import (
    DataOrigin,
    EvidenceKind,
    FitmentRecord,
    FitmentStatus,
    SetComponent,
    SetKind,
)
from tests.catalog.helpers import W213_ANY, W213_POST, W213_PRE, product, record

FULL_PRE_AMG = VehicleQuery(
    chassis_code="W213",
    year=2018,
    facelift=False,
    trim_line="amg_line",
    parktronic_sensors=6,
    headlamp_washer=True,
    front_camera=False,
)
TEST = EvidencePolicy(RuntimeMode.TEST)
DEV = EvidencePolicy(RuntimeMode.DEVELOPMENT)
PROD = EvidencePolicy(RuntimeMode.PRODUCTION)


def test_verified_needs_full_match_with_accepted_evidence() -> None:
    p = product("SYN-GR-1")
    r = evaluate(p, [record("SYN-F1", p.sku, trim_line="amg_line")], FULL_PRE_AMG, TEST)
    assert r.status is FitmentStatus.VERIFIED
    assert r.reasons == (FitmentReason.VERIFIED_RECORD_MATCHES,)
    assert r.synthetic is True
    [item] = r.evidence
    assert item.evidence_kind is EvidenceKind.SYNTHETIC_FIXTURE and item.evidence_accepted
    assert {c.attribute for c in item.checks} >= {"chassis_code", "facelift", "trim_line"}


@pytest.mark.parametrize(
    "kind",
    [
        EvidenceKind.VISUAL_SIMILARITY,
        EvidenceKind.CUSTOMER_STATEMENT,
        EvidenceKind.LLM_OUTPUT,
        EvidenceKind.LISTING_TITLE,
        EvidenceKind.BODY_CODE_ONLY,
    ],
)
def test_non_evidence_kinds_never_verify_even_if_record_says_verified(kind: EvidenceKind) -> None:
    p = product("SYN-GR-1")
    rec = record("SYN-F1", p.sku, kind=kind, trim_line="amg_line")
    r = evaluate(p, [rec], FULL_PRE_AMG, TEST)
    assert r.status is FitmentStatus.NEEDS_VERIFICATION
    assert FitmentReason.EVIDENCE_NOT_ACCEPTED in r.reasons
    assert r.evidence[0].evidence_rejection is EvidenceRejection.KIND_NOT_EVIDENCE
    assert r.missing_attributes == ()  # asking the customer cannot fix missing evidence


def test_visual_similarity_cannot_make_a_part_incompatible_either() -> None:
    p = product("SYN-GR-1")
    rec = record("SYN-F1", p.sku, kind=EvidenceKind.VISUAL_SIMILARITY, trim_line="standard")
    r = evaluate(p, [rec], FULL_PRE_AMG, TEST)
    assert r.status is FitmentStatus.NEEDS_VERIFICATION
    assert r.reasons == (FitmentReason.NO_RECORD_MATCHES_VEHICLE,)


def test_body_code_alone_never_verifies() -> None:
    p = product("SYN-GR-1")
    rec = record("SYN-F1", p.sku, vehicle=W213_ANY)  # verified, but only "W213"
    for query in (VehicleQuery(chassis_code="W213"), FULL_PRE_AMG):
        r = evaluate(p, [rec], query, TEST)
        assert r.status is FitmentStatus.NEEDS_VERIFICATION
        assert r.reasons == (FitmentReason.BODY_CODE_ONLY,)
        assert r.missing_attributes == ()


def test_customer_saying_only_w213_verifies_nothing() -> None:
    p = product("SYN-GR-1")
    recs = [
        record("SYN-F1", p.sku, trim_line="amg_line"),
        record("SYN-F2", p.sku, vehicle=W213_POST, trim_line="amg_line"),
    ]
    r = evaluate(p, recs, VehicleQuery(chassis_code="W213"), TEST)
    assert r.status is FitmentStatus.NEEDS_VERIFICATION
    assert r.missing_attributes == ("facelift", "trim_line")
    assert r.customer_can_resolve


def test_make_and_model_without_chassis_ask_for_chassis() -> None:
    p = product("SYN-GR-1")
    rec = record("SYN-F1", p.sku, trim_line="amg_line")
    q = VehicleQuery(make="mercedes-benz", model="e class", facelift=False, trim_line="AMG Line")
    r = evaluate(p, [rec], q, TEST)
    assert r.status is FitmentStatus.NEEDS_VERIFICATION
    assert r.missing_attributes == ("chassis_code",)


def test_facelift_is_never_inferred_from_year() -> None:
    p = product("SYN-GR-1")
    rec = record("SYN-F1", p.sku, trim_line="amg_line")
    outcome, checks = match_record(
        rec, VehicleQuery(chassis_code="W213", year=2017, trim_line="amg_line")
    )
    assert outcome is MatchOutcome.PARTIAL
    assert [c.attribute for c in checks if c.outcome is Check.UNKNOWN] == ["facelift"]


def test_year_outside_range_is_a_mismatch() -> None:
    p = product("SYN-GR-1")
    rec = record("SYN-F1", p.sku, vehicle=W213_POST)
    outcome, _ = match_record(rec, VehicleQuery(chassis_code="W213", year=2017))
    assert outcome is MatchOutcome.MISMATCH


def test_year_is_asked_when_record_has_range_but_no_facelift_split() -> None:
    from app.catalog.types import VehicleSpec

    spec = VehicleSpec("Mercedes-Benz", "E-Class", "W213", 2016, 2018)
    p = product("SYN-GR-1")
    r = evaluate(
        p, [record("SYN-F1", p.sku, vehicle=spec)], VehicleQuery(chassis_code="W213"), TEST
    )
    assert r.missing_attributes == ("year",)
    r = evaluate(
        p,
        [record("SYN-F1", p.sku, vehicle=spec)],
        VehicleQuery(chassis_code="W213", year=2017),
        TEST,
    )
    assert r.status is FitmentStatus.VERIFIED


def test_explicit_incompatible_record() -> None:
    p = product("SYN-GR-1")
    rec = record("SYN-F1", p.sku, status=FitmentStatus.INCOMPATIBLE, front_camera=False)
    r = evaluate(p, [rec], FULL_PRE_AMG, TEST)
    assert r.status is FitmentStatus.INCOMPATIBLE
    assert r.reasons == (FitmentReason.EXPLICIT_INCOMPATIBLE_RECORD,)


def test_outside_verified_applicability_is_incompatible_with_evidence() -> None:
    p = product("SYN-GR-1")
    rec = record("SYN-F1", p.sku, trim_line="amg_line", front_camera=True)
    r = evaluate(p, [rec], FULL_PRE_AMG, TEST)
    assert r.status is FitmentStatus.INCOMPATIBLE
    assert r.reasons == (FitmentReason.OUTSIDE_VERIFIED_APPLICABILITY,)
    [item] = r.evidence
    mismatch = [c for c in item.checks if c.outcome is Check.MISMATCH]
    assert [(c.attribute, c.required, c.given) for c in mismatch] == [("front_camera", "yes", "no")]


def test_conflicting_records_stay_undecided() -> None:
    p = product("SYN-GR-1")
    recs = [
        record("SYN-F1", p.sku, trim_line="amg_line"),
        record("SYN-F2", p.sku, status=FitmentStatus.INCOMPATIBLE, headlamp_washer=True),
    ]
    r = evaluate(p, recs, FULL_PRE_AMG, TEST)
    assert r.status is FitmentStatus.NEEDS_VERIFICATION
    assert r.reasons == (FitmentReason.CONFLICTING_RECORDS,)


def test_no_record_means_owner_check_not_customer_question() -> None:
    r = evaluate(product("SYN-GR-1"), [], FULL_PRE_AMG, TEST)
    assert r.status is FitmentStatus.NEEDS_VERIFICATION
    assert r.reasons == (FitmentReason.NO_FITMENT_RECORD,)
    assert not r.customer_can_resolve


@pytest.mark.parametrize(
    ("kw", "rejection"),
    [
        ({"ref": None}, EvidenceRejection.REF_MISSING),
        ({"ref": "  "}, EvidenceRejection.REF_MISSING),
        ({"verified_at": None}, EvidenceRejection.VERIFIED_AT_MISSING),
        ({"kind": None}, EvidenceRejection.MISSING),
    ],
)
def test_incomplete_evidence_is_not_accepted(
    kw: dict[str, object], rejection: EvidenceRejection
) -> None:
    p = product("SYN-GR-1")
    rec = record("SYN-F1", p.sku, trim_line="amg_line", **kw)  # type: ignore[arg-type]
    r = evaluate(p, [rec], FULL_PRE_AMG, TEST)
    assert r.status is FitmentStatus.NEEDS_VERIFICATION
    assert r.evidence[0].evidence_rejection is rejection


# --- Synthetic evidence outside test mode ---------------------------------------------------


def test_synthetic_evidence_does_not_verify_in_development() -> None:
    p = product("SYN-GR-1")
    rec = record("SYN-F1", p.sku, trim_line="amg_line")
    r = evaluate(p, [rec], FULL_PRE_AMG, DEV)
    assert r.status is FitmentStatus.NEEDS_VERIFICATION
    assert r.reasons == (FitmentReason.EVIDENCE_NOT_ACCEPTED,)
    assert r.evidence[0].evidence_rejection is EvidenceRejection.SYNTHETIC_NOT_ACCEPTED
    assert r.synthetic


def test_synthetic_evidence_is_rejected_in_production() -> None:
    p = product("SYN-GR-1")
    with pytest.raises(SyntheticDataRejected):
        evaluate(p, [record("SYN-F1", p.sku)], FULL_PRE_AMG, PROD)


def test_synthetic_evidence_on_a_real_record_is_rejected_in_production() -> None:
    p = product("T-GR-1")  # labelled real only to exercise the production path
    rec = record("T-F1", p.sku, origin=DataOrigin.REAL, trim_line="amg_line")
    with pytest.raises(SyntheticDataRejected):
        evaluate(p, [rec], FULL_PRE_AMG, PROD)
    # ... and never accepted in test mode either
    r = evaluate(p, [rec], FULL_PRE_AMG, TEST)
    assert r.evidence[0].evidence_rejection is EvidenceRejection.SYNTHETIC_ON_REAL_RECORD


def test_real_owner_confirmation_verifies_in_production() -> None:
    p = product("T-GR-1")  # labelled real only to exercise the production path
    rec = record(
        "T-F1", p.sku, kind=EvidenceKind.OWNER_CONFIRMED, ref="T-OWNER-1", trim_line="amg_line"
    )
    r = evaluate(p, [rec], FULL_PRE_AMG, PROD)
    assert r.status is FitmentStatus.VERIFIED
    assert r.synthetic is False


def test_synthetic_record_cannot_claim_real_evidence() -> None:
    p = product("SYN-GR-1")
    rec = record("SYN-F1", p.sku, kind=EvidenceKind.OWNER_CONFIRMED, trim_line="amg_line")
    r = evaluate(p, [rec], FULL_PRE_AMG, TEST)
    assert r.status is FitmentStatus.NEEDS_VERIFICATION
    assert r.evidence[0].evidence_rejection is EvidenceRejection.SYNTHETIC_RECORD_CLAIMS_REAL_KIND


@pytest.mark.parametrize(
    ("env", "mode"),
    [
        ({}, RuntimeMode.PRODUCTION),
        ({"APP_ENV": ""}, RuntimeMode.PRODUCTION),
        ({"APP_ENV": "staging"}, RuntimeMode.PRODUCTION),
        ({"APP_ENV": "Development"}, RuntimeMode.DEVELOPMENT),
        ({"APP_ENV": "test"}, RuntimeMode.TEST),
    ],
)
def test_runtime_mode_defaults_to_production(env: dict[str, str], mode: RuntimeMode) -> None:
    assert current_runtime_mode(env) is mode


def test_policy_from_env_rejects_synthetic_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    p = product("SYN-GR-1")
    with pytest.raises(SyntheticDataRejected):
        evaluate(p, [], FULL_PRE_AMG, EvidencePolicy.from_env())


# --- Determinism, validation, questions, sets ------------------------------------------------


def test_result_does_not_depend_on_record_order() -> None:
    p = product("SYN-GR-1")
    recs: list[FitmentRecord] = [
        record(f"SYN-F{i}", p.sku, vehicle=v, trim_line=t)
        for i, (v, t) in enumerate(
            [(W213_PRE, "amg_line"), (W213_POST, "amg_line"), (W213_PRE, "standard")]
        )
    ]
    query = VehicleQuery(chassis_code="W213", trim_line="amg_line")
    expected = evaluate(p, recs, query, TEST)
    rng = random.Random(7)
    for _ in range(5):
        shuffled = recs[:]
        rng.shuffle(shuffled)
        assert evaluate(p, shuffled, query, TEST) == expected


def test_unknown_condition_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown fitment condition"):
        record("SYN-F1", "SYN-GR-1", colour="red")
    with pytest.raises(ValueError, match="bad value"):
        record("SYN-F1", "SYN-GR-1", parktronic_sensors="six")


def test_synthetic_label_must_match_sku_prefix() -> None:
    with pytest.raises(ValueError, match="SKU"):
        product("SYN-GR-1", origin=DataOrigin.REAL)
    with pytest.raises(ValueError, match="SKU"):
        product("GR-1", origin=DataOrigin.SYNTHETIC)


def test_questions_are_ordered_by_usefulness_then_fixed_order() -> None:
    a, b = product("SYN-A"), product("SYN-B")
    recs = [
        record("SYN-F1", a.sku, trim_line="amg_line", front_camera=False),
        record("SYN-F2", b.sku, front_camera=True),
    ]
    results = evaluate_candidates([a, b], recs, VehicleQuery(chassis_code="W213"), TEST)
    assert questions_to_ask(results) == ("facelift", "front_camera", "trim_line")


def test_set_verdict_combines_components() -> None:
    s = product("SYN-SET", set_kind=SetKind.VIRTUAL_SET)
    a, b = product("SYN-A"), product("SYN-B")
    comps = [SetComponent(s.sku, a.sku), SetComponent(s.sku, b.sku)]
    recs = [
        record("SYN-F1", a.sku, trim_line="amg_line"),
        record("SYN-F2", b.sku, trim_line="amg_line"),
    ]
    results = {r.sku: r for r in evaluate_candidates([a, b], recs, FULL_PRE_AMG, TEST)}
    assert evaluate_set(s, comps, results).status is FitmentStatus.VERIFIED

    recs[1] = record("SYN-F2", b.sku, trim_line="standard")
    results = {r.sku: r for r in evaluate_candidates([a, b], recs, FULL_PRE_AMG, TEST)}
    combined = evaluate_set(s, comps, results)
    assert combined.status is FitmentStatus.INCOMPATIBLE
    assert combined.reasons == (FitmentReason.COMPONENT_INCOMPATIBLE,)

    partial = {
        r.sku: r for r in evaluate_candidates([a, b], recs, VehicleQuery(chassis_code="W213"), TEST)
    }
    combined = evaluate_set(s, comps, partial)
    assert combined.status is FitmentStatus.NEEDS_VERIFICATION
    assert combined.missing_attributes == ("facelift", "trim_line")


def test_set_component_without_result_is_not_verified() -> None:
    s = product("SYN-SET", set_kind=SetKind.VIRTUAL_SET)
    comps = [SetComponent(s.sku, "SYN-A")]
    assert evaluate_set(s, comps, {}).status is FitmentStatus.NEEDS_VERIFICATION
