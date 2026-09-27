"""Per-endpoint token buckets with two priority classes (docs/ARCHITECTURE.md §6.10).

* ``live`` (sending, reconciliation, ``process_chat`` reads, poller) is served first.
* ``bulk`` (history import, measurement) waits while any ``live`` caller waits on the same bucket,
  and is additionally held to ``bulk_share`` of the bucket's rate by a second, smaller bucket.
  Long-term, bulk therefore never takes more than ``bulk_share`` of the budget, and live always
  keeps at least ``1 - bulk_share``.
* :meth:`PriorityRateLimiter.penalize` (after a 429) pauses **both** classes on that bucket.

Clock and sleep are injectable so tests can run on virtual time.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.avito_gateway.config import RateLimit

Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]


# Float tolerance: 0.9999999999999929 tokens count as one, otherwise a waiter could be told to
# sleep for 1e-16 s again and again (a livelock seen in testing).
_ONE = 1.0 - 1e-9
_MIN_WAIT_S = 0.001


def _wait(seconds: float) -> float:
    return max(seconds, _MIN_WAIT_S)


class Priority(StrEnum):
    LIVE = "live"
    BULK = "bulk"


@dataclass
class _Bucket:
    rate: float  # tokens per second
    capacity: float
    bulk_rate: float
    bulk_capacity: float
    tokens: float
    bulk_tokens: float
    updated: float
    blocked_until: float = 0.0
    live_waiters: int = 0

    def refill(self, now: float) -> None:
        # Nothing accrues during a 429 pause, so the pause is not followed by a full burst.
        elapsed = max(0.0, now - max(self.updated, self.blocked_until))
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.bulk_tokens = min(self.bulk_capacity, self.bulk_tokens + elapsed * self.bulk_rate)
        self.updated = max(self.updated, now)

    def try_take(self, priority: Priority, now: float) -> float:
        """Take a token and return 0, or return how long to wait before trying again."""
        self.refill(now)
        if now < self.blocked_until:
            return self.blocked_until - now
        if priority is Priority.LIVE:
            if self.tokens >= _ONE:
                self.tokens = max(0.0, self.tokens - 1.0)
                return 0.0
            return _wait((1.0 - self.tokens) / self.rate)
        if self.live_waiters > 0:
            # Live goes first: check again after roughly one token interval.
            return _wait(1.0 / self.rate)
        if self.tokens >= _ONE and self.bulk_tokens >= _ONE:
            self.tokens = max(0.0, self.tokens - 1.0)
            self.bulk_tokens = max(0.0, self.bulk_tokens - 1.0)
            return 0.0
        return _wait(
            max((1.0 - self.tokens) / self.rate, (1.0 - self.bulk_tokens) / self.bulk_rate)
        )


class PriorityRateLimiter:
    def __init__(
        self,
        limits: Mapping[str, RateLimit],
        *,
        default: RateLimit,
        bulk_share: float = 0.5,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
        max_wait_step_s: float = 1.0,
    ) -> None:
        if not 0.0 < bulk_share <= 1.0:
            raise ValueError("bulk_share must be in (0, 1]")
        self._limits = dict(limits)
        self._default = default
        self._bulk_share = bulk_share
        self._clock = clock
        self._sleep = sleep
        self._max_wait_step_s = max_wait_step_s
        self._buckets: dict[str, _Bucket] = {}

    def _bucket(self, key: str) -> _Bucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            limit = self._limits.get(key, self._default)
            rate = limit.per_minute / 60.0
            capacity = float(limit.burst)
            bulk_capacity = max(1.0, capacity * self._bulk_share)
            bucket = _Bucket(
                rate=rate,
                capacity=capacity,
                bulk_rate=rate * self._bulk_share,
                bulk_capacity=bulk_capacity,
                tokens=capacity,
                bulk_tokens=bulk_capacity,
                updated=self._clock(),
            )
            self._buckets[key] = bucket
        return bucket

    async def acquire(self, key: str, priority: Priority) -> None:
        """Wait until one request on bucket ``key`` may be sent."""
        bucket = self._bucket(key)
        if priority is Priority.LIVE:
            bucket.live_waiters += 1
        try:
            while True:
                wait = bucket.try_take(priority, self._clock())
                if wait <= 0.0:
                    return
                await self._sleep(min(wait, self._max_wait_step_s))
        finally:
            if priority is Priority.LIVE:
                bucket.live_waiters -= 1

    def penalize(self, key: str, seconds: float) -> None:
        """After a 429: empty the bucket and pause both classes for ``seconds``."""
        bucket = self._bucket(key)
        now = self._clock()
        bucket.refill(now)
        bucket.tokens = 0.0
        bucket.bulk_tokens = 0.0
        bucket.blocked_until = max(bucket.blocked_until, now + max(0.0, seconds))

    def blocked_for(self, key: str) -> float:
        """Seconds left of a 429 pause on ``key`` (0 if none)."""
        bucket = self._buckets.get(key)
        if bucket is None:
            return 0.0
        return max(0.0, bucket.blocked_until - self._clock())
