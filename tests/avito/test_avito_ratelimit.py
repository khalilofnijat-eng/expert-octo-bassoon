"""Priority rate limiter on virtual time: live before bulk, bulk share cap, 429 pause."""

from __future__ import annotations

import asyncio

import pytest

from app.avito_gateway import AvitoRateLimitedError, Priority, PriorityRateLimiter, RateLimit
from app.avito_gateway.http import parse_retry_after
from scripts.dev.avito_mock import SYNTHETIC_USER_ID, AvitoMock, rate_limited
from tests.avito.helpers import VirtualClock, make_client

pytestmark = pytest.mark.anyio

KEY = "messages_list"


def limiter(clock: VirtualClock, *, per_minute: float = 60, burst: int = 1, share: float = 0.5):
    return PriorityRateLimiter(
        {KEY: RateLimit(per_minute=per_minute, burst=burst)},
        default=RateLimit(per_minute=60, burst=1),
        bulk_share=share,
        clock=clock.time,
        sleep=clock.sleep,
    )


async def _grants(
    clock: VirtualClock, lim: PriorityRateLimiter, plan: list[Priority], *, until: float = 1e9
) -> list[tuple[float, Priority]]:
    grants: list[tuple[float, Priority]] = []

    async def one(priority: Priority) -> None:
        await lim.acquire(KEY, priority)
        grants.append((clock.now, priority))

    tasks = [asyncio.create_task(one(p)) for p in plan]
    await clock.run(tasks, until=until)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    return grants


async def test_live_is_served_before_waiting_bulk() -> None:
    clock = VirtualClock()
    lim = limiter(clock)  # 1 request/s, burst 1
    await lim.acquire(KEY, Priority.LIVE)  # drain the initial token
    # Bulk callers queue first, live callers arrive later: live still goes first.
    plan = [Priority.BULK] * 4 + [Priority.LIVE] * 4
    grants = await _grants(clock, lim, plan)
    order = [p for _, p in grants]
    assert order[:4] == [Priority.LIVE] * 4
    assert order[4:] == [Priority.BULK] * 4
    # Live: one per second (the bucket rate).
    assert [t for t, _ in grants[:4]] == pytest.approx([1.0, 2.0, 3.0, 4.0])


async def test_bulk_alone_is_capped_at_share() -> None:
    clock = VirtualClock()
    lim = limiter(clock, share=0.5)  # 1/s total → bulk ≤ 0.5/s
    grants = await _grants(clock, lim, [Priority.BULK] * 200, until=100.0)
    # 100 s at 0.5/s, plus the initial bulk token.
    assert 49 <= len(grants) <= 52


async def test_live_alone_gets_full_rate() -> None:
    clock = VirtualClock()
    lim = limiter(clock)
    grants = await _grants(clock, lim, [Priority.LIVE] * 200, until=100.0)
    assert 99 <= len(grants) <= 102


async def test_saturating_live_starves_bulk_and_bulk_never_exceeds_share() -> None:
    clock = VirtualClock()
    lim = limiter(clock, share=0.25)
    plan = [Priority.LIVE] * 60 + [Priority.BULK] * 200
    grants = await _grants(clock, lim, plan, until=120.0)
    live_times = [t for t, p in grants if p is Priority.LIVE]
    bulk_times = [t for t, p in grants if p is Priority.BULK]
    assert len(live_times) == 60
    # No bulk grant while live callers were still waiting (except possibly the very first
    # token, taken before any live caller registered).
    assert all(t >= live_times[-1] for t in bulk_times[1:])
    # After live is done (~60 s), bulk runs at ≤ 25 % of 1/s for the remaining ~60 s.
    after = [t for t in bulk_times if t > live_times[-1]]
    assert len(after) <= 0.25 * (120.0 - live_times[-1]) + 2


async def test_share_is_configurable() -> None:
    clock = VirtualClock()
    lim = limiter(clock, share=1.0)
    grants = await _grants(clock, lim, [Priority.BULK] * 200, until=100.0)
    assert 99 <= len(grants) <= 102


async def test_penalize_pauses_both_classes() -> None:
    clock = VirtualClock()
    lim = limiter(clock, per_minute=600, burst=5)
    lim.penalize(KEY, 30.0)
    assert lim.blocked_for(KEY) == pytest.approx(30.0)
    grants = await _grants(clock, lim, [Priority.LIVE, Priority.BULK])
    assert grants
    assert min(t for t, _ in grants) >= 30.0
    # No burst after the pause: tokens did not accrue while blocked.
    assert sorted(p for _, p in grants) == sorted([Priority.LIVE, Priority.BULK])


async def test_buckets_are_per_endpoint() -> None:
    clock = VirtualClock()
    lim = limiter(clock)
    lim.penalize(KEY, 100.0)
    task = asyncio.create_task(lim.acquire("chats_list", Priority.LIVE))
    await clock.run([task], until=0.0)
    assert task.done()
    assert lim.blocked_for("chats_list") == 0.0


def test_invalid_share_rejected() -> None:
    with pytest.raises(ValueError):
        PriorityRateLimiter({}, default=RateLimit(per_minute=1), bulk_share=0.0)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("7", 7.0),
        (" 12 ", 12.0),
        ("0", 0.0),
        ("-3", 0.0),
        ("soon", None),
        ("", None),
        (None, None),
        ("nan", None),
        ("Thu, 01 Jan 1970 00:01:40 GMT", 40.0),  # HTTP-date, 100 s epoch, "now" = 60
    ],
)
def test_parse_retry_after(header: str | None, expected: float | None) -> None:
    assert parse_retry_after(header, now=60.0) == expected


@pytest.mark.parametrize(("retry_after", "expected"), [("7", 7.0), (None, 42.0), ("99999", 900.0)])
async def test_client_honours_429(retry_after: str | None, expected: float) -> None:
    """429 → typed error (no retry) and the endpoint's bucket pauses for Retry-After, or for
    the configured cooldown when the header is missing (UNVERIFIED whether Avito sends it)."""
    clock = VirtualClock()
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock, default_429_cooldown_s=42.0) as client:
        lim = PriorityRateLimiter(
            {}, default=RateLimit(per_minute=6000, burst=100), clock=clock.time, sleep=clock.sleep
        )
        client._http.limiter = lim
        mock.inject(rate_limited(retry_after), endpoint="chats_list")
        with pytest.raises(AvitoRateLimitedError) as info:
            await client.list_chats(SYNTHETIC_USER_ID)
        assert mock.count("chats_list") == 1
        assert lim.blocked_for("chats_list") == pytest.approx(expected)
        assert lim.blocked_for("messages_list") == 0.0
    err = info.value
    assert err.retry_after == (None if retry_after is None else expected)
    assert err.limit == 25
    assert err.remaining == 0
