# SYNTHETIC: all data used by tests/avito is made up (see scripts/dev/avito_mock).
"""Shared helpers for the Avito gateway tests. No test here touches the network."""

from __future__ import annotations

import asyncio
import heapq
import itertools
import json
from pathlib import Path
from typing import Any

from app.avito_gateway import AvitoReadClient
from app.avito_gateway.http import AttemptRecord
from app.avito_gateway.ratelimit import Clock
from scripts.dev.avito_mock import AvitoMock, config_for_mock

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "avito"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_client(
    mock: AvitoMock,
    *,
    attempts: list[AttemptRecord] | None = None,
    clock: Clock | None = None,
    **config: Any,
) -> AvitoReadClient:
    kwargs: dict[str, Any] = {}
    if clock is not None:
        kwargs["clock"] = clock
    return AvitoReadClient(
        config_for_mock(**config),
        mock.credentials(),
        transport=mock.transport(),
        on_attempt=attempts.append if attempts is not None else None,
        **kwargs,
    )


class VirtualClock:
    """Virtual time for asyncio tests: ``sleep`` parks the caller until :meth:`run` advances
    time to its wake-up point. Deterministic and instant."""

    def __init__(self) -> None:
        self.now = 0.0
        self._sleepers: list[tuple[float, int, asyncio.Future[None]]] = []
        self._seq = itertools.count()

    def time(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        heapq.heappush(self._sleepers, (self.now + max(0.0, delay), next(self._seq), future))
        await future

    async def _settle(self) -> None:
        for _ in range(20):
            await asyncio.sleep(0)

    async def run(self, tasks: list[asyncio.Task[Any]], *, until: float = 1e9) -> None:
        """Advance virtual time until every task is done or ``until`` is reached."""
        await self._settle()
        while not all(t.done() for t in tasks):
            if not self._sleepers:
                raise AssertionError("tasks are blocked but nobody is sleeping")
            wake, _, future = heapq.heappop(self._sleepers)
            if wake > until:
                heapq.heappush(self._sleepers, (wake, next(self._seq), future))
                break
            self.now = max(self.now, wake)
            if not future.done():
                future.set_result(None)
            await self._settle()
