"""Advisory locks for the single-worker model (docs/ARCHITECTURE.md §6.1).

Two-key namespace: ``pg_try_advisory_lock(1, 0)`` is the worker singleton and
``pg_try_advisory_lock(2, conversation_id)`` is a conversation. The keys never collide.

Conversation locks live on a connection that has been **detached from the pool** (Y2). Advisory
locks are re-entrant per session, so a pooled connection that still held a lock would let the next
borrower "acquire" it again and write unprotected. A detached connection is owned by exactly one
task, never returns to the pool and is closed when the lock is released; PostgreSQL releases the
lock if the connection or the process dies.

Fencing choice (Y5): job claims, the send-intent CAS and the hold transaction check the singleton
with ``singleton_fence_sql`` (``pg_locks`` shows lock (1, 0) held by the recorded backend pid, and
``worker_singleton.epoch`` still has the value this worker set when it took the lock) instead of
running those writes on the singleton connection. Reasons, both shown by tests/db: (1) a
conversation-locked write must run on the conversation lock connection (Y2), so it cannot also run
on the singleton connection; the fence lets it stay in one transaction on the lock connection;
(2) when the singleton session dies, the fenced statement deterministically affects 0 rows,
whereas a write on the dead singleton connection only raises a connection error. The epoch closes
the pid-reuse hole: a new worker whose backend happens to get the old pid has a new epoch.

Liveness: ``WorkerSingleton.check`` has a hard deadline; a probe that does not answer in time
(e.g. a half-open network path) counts as lost, and ``on_lost`` ends the process. The singleton
connection also uses TCP keepalives and ``tcp_user_timeout`` so the socket itself fails.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.pool import NullPool

log = logging.getLogger(__name__)

NS_SINGLETON = 1
NS_CONVERSATION = 2
SINGLETON_ID = 0
# pg_try_advisory_lock(int4, int4): the second key must fit in int4.
_INT4_MAX = 2**31 - 1
# Exit status when the singleton is lost; the service manager restarts the worker.
EXIT_SINGLETON_LOST = 75


@dataclass(frozen=True)
class SingletonToken:
    """Proof of the singleton: backend pid of the lock session and the epoch this worker set."""

    pid: int
    epoch: int

    def params(self) -> dict[str, int]:
        return {"singleton_pid": self.pid, "singleton_epoch": self.epoch}


def _holds_lock_sql(ns: int, key: str, pid: str) -> str:
    # For the two-int4 form, pg_locks shows key1 as classid, key2 as objid and objsubid = 2.
    return (
        f"EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND classid = {ns} "
        f"AND objid = {key} AND objsubid = 2 AND granted AND pid = {pid})"
    )


def singleton_fence_sql() -> str:
    """SQL condition: the singleton is still held by ``:singleton_pid`` with ``:singleton_epoch``.

    Bind it with ``SingletonToken.params()``.
    """
    return (
        _holds_lock_sql(NS_SINGLETON, str(SINGLETON_ID), ":singleton_pid")
        + " AND EXISTS (SELECT 1 FROM worker_singleton AS ws WHERE ws.id = 1 "
        "AND ws.epoch = :singleton_epoch AND ws.pid = :singleton_pid)"
    )


# The watchdog probe: the fence, evaluated on the singleton session itself.
_CHECK_SQL = "SELECT " + singleton_fence_sql() + " AND pg_backend_pid() = :singleton_pid"


def conversation_lock_held_here_sql(conversation_param: str = "conversation_id") -> str:
    """SQL condition: *this* session holds the lock for conversation ``:conversation_param``."""
    return _holds_lock_sql(NS_CONVERSATION, f":{conversation_param}", "pg_backend_pid()")


def try_advisory_lock(conn: Connection, ns: int, key: int) -> bool:
    """Session-level ``pg_try_advisory_lock(ns, key)``. Re-entrant within one session."""
    got = conn.execute(text("SELECT pg_try_advisory_lock(:ns, :key)"), {"ns": ns, "key": key})
    return bool(got.scalar_one())


def detached_connection(engine: Engine) -> Connection:
    """Open a connection that belongs to the caller alone and is really closed on ``close()``."""
    conn = engine.connect()
    conn.detach()
    return conn


@dataclass
class ConversationLock:
    """A held conversation lock and the only connection allowed to write under it."""

    conversation_id: int
    connection: Connection


@contextmanager
def conversation_lock(engine: Engine, conversation_id: int) -> Iterator[ConversationLock | None]:
    """Try to take lock (2, conversation_id). Yields ``None`` if another session holds it.

    No transaction is left open while the lock is held (the caller opens short transactions on
    ``lock.connection``). On exit the lock is released and the connection closed.
    """
    if not 0 < conversation_id <= _INT4_MAX:
        raise ValueError("conversation_id must fit in int4 for the advisory lock key")
    conn = detached_connection(engine)
    try:
        acquired = try_advisory_lock(conn, NS_CONVERSATION, conversation_id)
        conn.commit()
        if not acquired:
            yield None
            return
        try:
            yield ConversationLock(conversation_id, conn)
        finally:
            if conn.in_transaction():
                conn.rollback()
            if not conn.invalidated:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:ns, :key)"),
                    {"ns": NS_CONVERSATION, "key": conversation_id},
                )
                conn.commit()
    finally:
        conn.close()


class SingletonBusyError(RuntimeError):
    """Another worker holds the singleton lock."""


class SingletonNotHeldError(RuntimeError):
    """This worker does not (or no longer) hold the singleton."""


def _exit_process(status: int) -> None:
    os._exit(status)


def _keepalive_args(deadline_s: float) -> dict[str, Any]:
    """libpq TCP settings so a dead peer surfaces as a socket error within about the deadline."""
    idle = max(1, int(deadline_s))
    return {
        "keepalives": 1,
        "keepalives_idle": idle,
        "keepalives_interval": idle,
        "keepalives_count": 2,
        "tcp_user_timeout": max(1000, int(deadline_s * 1000)),
    }


class WorkerSingleton:
    """Singleton lock (1, 0) on a dedicated connection, with a liveness watchdog (Y5).

    If the connection fails, the lock is no longer held by this session with this epoch, or the
    probe misses its deadline, ``on_lost`` is called; by default it ends the process immediately
    with ``os._exit`` so no worker keeps running without the lock. The connection is used only by
    the lock, the epoch update and the watchdog (see the fencing note above).
    """

    def __init__(
        self,
        engine: Engine,
        on_lost: Callable[[int], None] = _exit_process,
        check_timeout_s: float = 5.0,
    ) -> None:
        self._source = engine
        self._on_lost = on_lost
        self._check_timeout_s = check_timeout_s
        self._engine: Engine | None = None
        self._conn: Connection | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._probe: threading.Thread | None = None
        self._lost = False
        self._token: SingletonToken | None = None

    @property
    def token(self) -> SingletonToken | None:
        """The fence token while the singleton is believed held, else ``None``."""
        return None if self._lost else self._token

    @property
    def pid(self) -> int | None:
        return None if self._token is None else self._token.pid

    def acquire(self) -> SingletonToken:
        """Take the lock and bump the epoch, or raise ``SingletonBusyError``."""
        self._engine = create_engine(
            self._source.url,
            poolclass=NullPool,
            isolation_level="AUTOCOMMIT",
            connect_args=_keepalive_args(self._check_timeout_s),
        )
        conn = self._engine.connect()
        if not try_advisory_lock(conn, NS_SINGLETON, SINGLETON_ID):
            conn.close()
            self._engine.dispose()
            self._engine = None
            raise SingletonBusyError("another worker holds the singleton lock")
        row = conn.execute(
            text(
                "UPDATE worker_singleton SET epoch = epoch + 1, pid = pg_backend_pid(), "
                "acquired_at = now() WHERE id = 1 RETURNING pid, epoch"
            )
        ).one()
        self._conn = conn
        self._lost = False
        self._token = SingletonToken(pid=int(row.pid), epoch=int(row.epoch))
        return self._token

    def check(self) -> bool:
        """Verify, within the deadline, that this session still holds the lock with our epoch.

        Anything else (error, ``false``, or no answer in time) calls ``on_lost``.
        """
        conn, token = self._conn, self._token
        if conn is None or token is None:
            raise SingletonNotHeldError("singleton not acquired")
        answer: list[bool] = []

        def probe() -> None:
            try:
                held = bool(conn.execute(text(_CHECK_SQL), token.params()).scalar_one())
                answer.append(held)
            except Exception:
                log.exception("singleton connection lost")
                answer.append(False)

        self._probe = threading.Thread(target=probe, name="singleton-probe", daemon=True)
        self._probe.start()
        self._probe.join(self._check_timeout_s)
        if answer == [True]:
            return True
        if not answer:
            log.error("singleton probe missed its %.1f s deadline", self._check_timeout_s)
        self._lost = True
        self._stop.set()
        self._on_lost(EXIT_SINGLETON_LOST)
        return False

    def start_watchdog(self, interval_s: float) -> None:
        """Poll ``check`` every ``interval_s`` seconds in a daemon thread."""

        def loop() -> None:
            while not self._stop.wait(interval_s):
                if not self.check():
                    return

        self._thread = threading.Thread(target=loop, name="singleton-watchdog", daemon=True)
        self._thread.start()

    def release(self) -> None:
        """Stop the watchdog and close the connection (PostgreSQL drops the lock)."""
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(self._check_timeout_s * 2 + 1)
        stuck = self._probe is not None and self._probe.is_alive()
        if self._conn is not None and not stuck:
            # A probe still blocked in the driver owns the socket; closing under it is unsafe.
            # In production on_lost has already ended the process.
            self._conn.close()
        self._conn = None
        if self._engine is not None and not stuck:
            self._engine.dispose()
        self._engine = None
        self._token = None
