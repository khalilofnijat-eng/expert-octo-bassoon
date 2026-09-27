"""Advisory locks for the single-worker model (docs/ARCHITECTURE.md §6.1).

Two-key namespace: ``pg_try_advisory_lock(1, 0)`` is the worker singleton and
``pg_try_advisory_lock(2, conversation_id)`` is a conversation. The keys never collide.

Every lock lives on a connection that has been **detached from the pool** (Y2). Advisory locks
are re-entrant per session, so a pooled connection that still held a lock would let the next
borrower "acquire" it again and write unprotected. A detached connection is owned by exactly one
task, never returns to the pool and is closed when the lock is released; PostgreSQL releases the
lock if the connection or the process dies.

Fencing choice (Y5): the send-intent CAS and the hold transaction check
``pg_locks`` for the singleton lock held by the recorded backend pid (``singleton_fence_sql``),
instead of running those writes on the singleton connection. Reasons, both shown by
tests/db: (1) a conversation-locked write must run on the conversation lock connection (Y2), so it
cannot also run on the singleton connection; the pg_locks check lets it stay in the same
transaction on the lock connection; (2) when the singleton session dies the fenced statement
deterministically affects 0 rows, whereas a write on the dead singleton connection only raises a
connection error. Residual risk: if the singleton backend dies and a *new* worker's singleton
backend receives the same pid while the old process is still inside its exit window, the old
process would pass the fence. The watchdog (``WorkerSingleton.check``) bounds that window to one
poll interval.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Connection, Engine, text

log = logging.getLogger(__name__)

NS_SINGLETON = 1
NS_CONVERSATION = 2
SINGLETON_ID = 0
# pg_try_advisory_lock(int4, int4): the second key must fit in int4.
_INT4_MAX = 2**31 - 1
# Exit status when the singleton connection is lost; the service manager restarts the worker.
EXIT_SINGLETON_LOST = 75


def _holds_lock_sql(ns: int, key: str, pid: str) -> str:
    # For the two-int4 form, pg_locks shows key1 as classid, key2 as objid and objsubid = 2.
    return (
        f"EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND classid = {ns} "
        f"AND objid = {key} AND objsubid = 2 AND granted AND pid = {pid})"
    )


def singleton_fence_sql(pid_param: str = "singleton_pid") -> str:
    """SQL condition: the worker singleton lock is still held by backend ``:pid_param``."""
    return _holds_lock_sql(NS_SINGLETON, str(SINGLETON_ID), f":{pid_param}")


def conversation_lock_held_here_sql(conversation_param: str = "conversation_id") -> str:
    """SQL condition: *this* session holds the lock for conversation ``:conversation_param``."""
    return _holds_lock_sql(NS_CONVERSATION, f":{conversation_param}", "pg_backend_pid()")


def try_advisory_lock(conn: Connection, ns: int, key: int) -> bool:
    """Session-level ``pg_try_advisory_lock(ns, key)``. Re-entrant within one session."""
    got = conn.execute(text("SELECT pg_try_advisory_lock(:ns, :key)"), {"ns": ns, "key": key})
    return bool(got.scalar_one())


def detached_connection(engine: Engine, *, autocommit: bool = False) -> Connection:
    """Open a connection that belongs to the caller alone and is really closed on ``close()``."""
    conn = engine.connect()
    if autocommit:  # must be set before detach(): SQLAlchemy resets it through the pool record
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
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


def _exit_process(status: int) -> None:
    os._exit(status)


class WorkerSingleton:
    """Singleton lock (1, 0) on a dedicated connection, with a liveness watchdog (Y5).

    If the connection fails or the lock is no longer held, ``on_lost`` is called; by default it
    ends the process immediately with ``os._exit`` so no worker keeps running without the lock.
    The connection is used only by the lock and the watchdog (see the fencing note above).
    """

    def __init__(self, engine: Engine, on_lost: Callable[[int], None] = _exit_process) -> None:
        self._engine = engine
        self._on_lost = on_lost
        self._conn: Connection | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.pid: int | None = None

    def acquire(self) -> int:
        """Take the lock or raise ``SingletonBusyError``. Returns the backend pid for fencing."""
        conn = detached_connection(self._engine, autocommit=True)
        if not try_advisory_lock(conn, NS_SINGLETON, SINGLETON_ID):
            conn.close()
            raise SingletonBusyError("another worker holds the singleton lock")
        self._conn = conn
        self.pid = int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
        return self.pid

    def check(self) -> bool:
        """Verify the lock is still held on a live connection; call ``on_lost`` if not."""
        if self._conn is None:
            raise RuntimeError("singleton not acquired")
        try:
            held = bool(
                self._conn.execute(
                    text("SELECT " + singleton_fence_sql()),
                    {"singleton_pid": self.pid},
                ).scalar_one()
            )
        except Exception:
            log.exception("singleton connection lost")
            held = False
        if not held:
            self._stop.set()
            self._on_lost(EXIT_SINGLETON_LOST)
            return False
        return True

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
            self._thread.join()
        if self._conn is not None:
            self._conn.close()
            self._conn = None
