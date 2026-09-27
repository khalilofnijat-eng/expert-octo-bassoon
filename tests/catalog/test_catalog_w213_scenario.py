# SYNTHETIC: the W213 dataset is made up; results are synthetic-test results only.
"""Owner request §6 scenario on the synthetic dataset: a customer wants a complete W213 front
bumper and does not know which grille fits.

Flow exercised: search candidates via the inventory port → fitment engine → questions for the
customer → verdict split with full information → set completeness and stock/price claims →
photos tied to stock records.
"""

from __future__ import annotations

from app.catalog.dataset import SyntheticDataset
from app.catalog.evidence import EvidencePolicy
from app.catalog.fitment import (
    FitmentReason,
    FitmentResult,
    VehicleQuery,
    evaluate_candidates,
    evaluate_set,
    questions_to_ask,
)
from app.catalog.sets import set_availability
from app.catalog.types import FitmentStatus, Product, SetKind
from app.inventory.port import (
    AvailabilityStatus,
    MatchBasis,
    PriceStatus,
    ProductSearch,
    ReadStatus,
    claim_availability,
    claim_price,
)
from app.inventory.synthetic import SyntheticInventoryAdapter
from tests.catalog.helpers import make_adapter

BUMPER_TYPES = ("front_bumper", "front_bumper_set")


def _candidates(adapter: SyntheticInventoryAdapter) -> list[Product]:
    products: list[Product] = []
    for part_type in (*BUMPER_TYPES, "front_grille"):
        read = adapter.search_products(ProductSearch(chassis_code="W213", part_type=part_type))
        products.extend(hit.product for hit in read.fresh_value())
    return products


def _verdicts(
    dataset: SyntheticDataset,
    products: list[Product],
    query: VehicleQuery,
    policy: EvidencePolicy,
) -> dict[str, FitmentResult]:
    # Components are evaluated too, so sets can be combined from them.
    everything = {p.sku: p for p in [*products, *dataset.products]}
    results = {
        r.sku: r
        for r in evaluate_candidates(list(everything.values()), dataset.fitments, query, policy)
    }
    for p in everything.values():
        if p.set_kind is not SetKind.SINGLE:
            results[p.sku] = evaluate_set(p, dataset.set_components, results, results[p.sku])
    return {p.sku: results[p.sku] for p in products}


def _by_status(results: dict[str, FitmentResult]) -> dict[FitmentStatus, set[str]]:
    out: dict[FitmentStatus, set[str]] = {s: set() for s in FitmentStatus}
    for sku, r in results.items():
        out[r.status].add(sku)
    return out


def test_search_returns_bumpers_sets_and_grilles_as_candidates_only(
    dataset: SyntheticDataset,
) -> None:
    adapter, _ = make_adapter(dataset)
    read = adapter.search_products(ProductSearch(chassis_code="W213", part_type="front_grille"))
    assert read.status is ReadStatus.FRESH
    hits = {h.product.sku: h.match_basis for h in read.fresh_value()}
    assert set(hits) == {f"SYN-W213-GR-00{i}" for i in range(1, 8)}
    # GR-007 has no fitment record; it is found by its title only.
    assert hits["SYN-W213-GR-007"] == (MatchBasis.TITLE_MENTION,)
    assert MatchBasis.CATALOG_APPLICABILITY in hits["SYN-W213-GR-001"]
    bumpers = {p.sku for p in _candidates(adapter) if p.part_type in BUMPER_TYPES}
    assert bumpers == {
        "SYN-W213-FB-001",
        "SYN-W213-FB-002",
        "SYN-W213-FB-003",
        "SYN-W213-FB-004",
        "SYN-W213-FBSET-001",
        "SYN-W213-FBSET-002",
    }


def test_body_code_only_yields_questions_and_nothing_verified(
    dataset: SyntheticDataset, test_policy: EvidencePolicy
) -> None:
    adapter, _ = make_adapter(dataset)
    products = _candidates(adapter)
    results = _verdicts(dataset, products, VehicleQuery(chassis_code="W213"), test_policy)

    split = _by_status(results)
    assert split[FitmentStatus.VERIFIED] == set()
    assert split[FitmentStatus.INCOMPATIBLE] == set()
    # Most useful first: the attribute is missing for this many candidates: facelift 10,
    # trim_line 10, parktronic_sensors 6, headlamp_washer 6, front_camera 5.
    assert questions_to_ask(results.values()) == (
        "facelift",
        "trim_line",
        "parktronic_sensors",
        "headlamp_washer",
        "front_camera",
    )
    # Parts that asking cannot settle are flagged for the owner, with the reason.
    assert results["SYN-W213-GR-005"].reasons == (FitmentReason.RECORD_NOT_VERIFIED,)
    assert results["SYN-W213-GR-006"].reasons == (FitmentReason.BODY_CODE_ONLY,)
    assert results["SYN-W213-GR-007"].reasons == (FitmentReason.NO_FITMENT_RECORD,)
    for sku in ("SYN-W213-GR-005", "SYN-W213-GR-006", "SYN-W213-GR-007"):
        assert not results[sku].customer_can_resolve


def test_partial_answer_narrows_candidates_and_questions(
    dataset: SyntheticDataset, test_policy: EvidencePolicy
) -> None:
    adapter, _ = make_adapter(dataset)
    query = VehicleQuery(chassis_code="W213", year=2018, trim_line="AMG-Line")
    results = _verdicts(dataset, _candidates(adapter), query, test_policy)
    split = _by_status(results)
    assert split[FitmentStatus.VERIFIED] == set()
    # No explicit incompatibility matches yet (GR-002's needs front_camera=no).
    assert split[FitmentStatus.INCOMPATIBLE] == set()
    # Year 2018 is outside every facelift record and "standard" trim records mismatch: those
    # parts are outside their verified range, which is not incompatibility. They stay
    # needs_verification and are owner-only by default.
    assert {s for s, r in results.items() if r.owner_only_by_default} == {
        "SYN-W213-FB-002",
        "SYN-W213-FB-003",
        "SYN-W213-FB-004",
        "SYN-W213-GR-003",
        "SYN-W213-GR-004",
        "SYN-W213-FBSET-002",
    }
    assert results["SYN-W213-FB-003"].reasons == (FitmentReason.OUTSIDE_VERIFIED_RANGE,)
    assert questions_to_ask(results.values()) == (
        "facelift",
        "front_camera",
        "parktronic_sensors",
        "headlamp_washer",
    )
    assert results["SYN-W213-GR-001"].missing_attributes == ("facelift", "front_camera")


def test_full_answer_splits_verified_needs_verification_incompatible(
    dataset: SyntheticDataset, test_policy: EvidencePolicy
) -> None:
    adapter, _ = make_adapter(dataset)
    query = VehicleQuery(
        make="Mercedes-Benz",
        model="E-Class",
        chassis_code="W213",
        year=2018,
        facelift=False,
        trim_line="amg_line",
        parktronic_sensors=6,
        headlamp_washer=True,
        front_camera=False,
    )
    results = _verdicts(dataset, _candidates(adapter), query, test_policy)
    split = _by_status(results)
    assert split[FitmentStatus.VERIFIED] == {
        "SYN-W213-FB-001",
        "SYN-W213-GR-001",
        "SYN-W213-FBSET-001",
    }
    # Only an explicit, accepted incompatibility record makes a part incompatible.
    assert split[FitmentStatus.INCOMPATIBLE] == {
        "SYN-W213-GR-002",  # SYN-FIT-017: camera-mount grille, car has no camera
    }
    assert results["SYN-W213-GR-002"].reasons == (FitmentReason.EXPLICIT_INCOMPATIBLE_RECORD,)
    # Undecided, shown to the customer as "needs checking" (the owner checks first) ...
    shown = {
        "SYN-W213-GR-005",  # visual similarity only
        "SYN-W213-GR-006",  # body code only
        "SYN-W213-GR-007",  # no fitment record
    }
    # ... and outside the verified range: undecided too, but owner-only by default.
    outside_range = {
        "SYN-W213-FB-002",
        "SYN-W213-FB-003",
        "SYN-W213-FB-004",
        "SYN-W213-GR-003",
        "SYN-W213-GR-004",
        "SYN-W213-FBSET-002",  # via its components
    }
    assert split[FitmentStatus.NEEDS_VERIFICATION] == shown | outside_range
    assert {s for s, r in results.items() if r.owner_only_by_default} == outside_range
    assert all(FitmentReason.OUTSIDE_VERIFIED_RANGE in results[s].reasons for s in outside_range)
    assert questions_to_ask(results.values()) == ()
    # Every verdict is flagged synthetic: it must not be reported as a real verification.
    assert all(r.synthetic for r in results.values())
    assert all(
        e.evidence_kind is not None and e.evidence_kind.value == "synthetic_fixture"
        for e in results["SYN-W213-FB-001"].evidence
    )


def test_complete_virtual_set_with_a_missing_component(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset)
    set_product = dataset.product("SYN-W213-FBSET-001")
    health = adapter.health()
    claims = {
        c.component_sku: claim_availability(adapter.get_stock(c.component_sku), health)
        for c in dataset.set_components
        if c.set_sku == set_product.sku
    }
    view = set_availability(set_product, dataset.set_components, claims)
    assert view.claim.status is AvailabilityStatus.NOT_AVAILABLE
    assert view.complete_sets == 0
    assert view.missing_components == ("SYN-W213-FC-L-001",)
    assert view.complete is False
    # The other components are individually available (GR-001 over two locations: 2 + 1).
    units = {c.component_sku: c.claim.sellable_qty for c in view.components if c.claim}
    assert units["SYN-W213-GR-001"] == 3
    assert units["SYN-W213-FB-001"] == 1


def test_stocked_set_lists_its_known_missing_item(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset)
    kit = dataset.product("SYN-W213-FBSET-002")
    claims = {kit.sku: claim_availability(adapter.get_item(kit.sku), adapter.health())}
    view = set_availability(kit, dataset.set_components, claims)
    assert view.claim.status is AvailabilityStatus.AVAILABLE
    assert view.missing_components == ("SYN-W213-LG-002",)
    assert view.complete is False


def test_offerable_items_have_stock_price_and_stock_bound_photos(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset)
    health = adapter.health()
    item = adapter.get_item("SYN-W213-FB-001")
    availability = claim_availability(item, health)
    price = claim_price(item, health)
    assert availability.status is AvailabilityStatus.AVAILABLE
    assert availability.sellable_qty == 1
    assert (price.status, price.amount_minor, price.currency) == (PriceStatus.EXACT, 1850000, "RUB")
    snapshot = item.fresh_value()
    assert snapshot.price is not None and snapshot.price.discount_rule_key is not None
    photos = adapter.get_photos("SYN-W213-FB-001").fresh_value()
    assert [p.photo_key for p in photos] == [
        "synthetic://placeholder/SYN-STK-001/1",
        "synthetic://placeholder/SYN-STK-001/2",
        "synthetic://placeholder/SYN-STK-001/3",
    ]
    stock_refs = {s.stock_ref for s in snapshot.stock}
    assert all(p.placeholder and p.stock_ref in stock_refs for p in photos)
    # A part without photos returns none (the renderer uses the "no photo" template).
    assert adapter.get_photos("SYN-W213-GR-006").fresh_value() == ()
    # Reserved stock is not sellable.
    fb3 = claim_availability(adapter.get_item("SYN-W213-FB-003"), health)
    assert fb3.status is AvailabilityStatus.NOT_AVAILABLE


def test_total_uses_integer_minor_units(dataset: SyntheticDataset) -> None:
    adapter, _ = make_adapter(dataset)
    health = adapter.health()
    lines = ("SYN-W213-FB-001", "SYN-W213-GR-001")
    amounts = [claim_price(adapter.get_price(sku), health).amount_minor for sku in lines]
    assert all(isinstance(a, int) for a in amounts)
    assert sum(a or 0 for a in amounts) == 2500000
