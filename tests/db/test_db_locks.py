# SYNTHETIC: conversations and jobs are made up.
"""Advisory locks and the single worker on real PostgreSQL: Y1 (worker start), Y2, Y5 (loss,
lock ownership, epoch, hang deadline), the takeover gap, Y6, and the runtime role check."""

from __future__ import annotations

import contextlib
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from app.config import AppEnv
from app.db.cas import claim_send_intent
from app.db.roles import UnsafeDatabaseRoleError, check_runtime_role
from app.queue import jobs
from app.queue.jobs import Job
from app.queue.locks import (
    EXIT_SINGLETON_LOST,
    NS_CONVERSATION,
    NS_SINGLETON,
    ConversationLock,
    SingletonBusyError,
    SingletonNotHeldError,
    SingletonToken,
    WorkerSingleton,
    conversation_lock,
    try_advisory_lock,
)
from app.queue.worker import Worker
from tests.db.factories import (
    ExitRecorder,
    enable_sending,
    job_row,
    make_conversation,
    make_draft,
    make_outbound,
    settings,
)


def _backend_alive(engine: Engine, pid: int) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE pid = :p)"), {"p": pid}
            ).scalar()
        )


def _terminate(engine: Engine, pid: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_terminate_backend(:p)"), {"p": pid})


def test_lock_namespaces_do_not_collide(engine: Engine) -> None:
    with engine.connect() as a, engine.connect() as b:
        assert try_advisory_lock(a, NS_SINGLETON, 5)
        assert try_advisory_lock(b, NS_CONVERSATION, 5)  # (1, 5) and (2, 5) are distinct
        assert not try_advisory_lock(b, NS_SINGLETON, 5)
        a.execute(text("SELECT pg_advisory_unlock_all()"))
        b.execute(text("SELECT pg_advisory_unlock_all()"))


def test_y2_reentrancy_trap_on_one_session(engine: Engine) -> None:
    """Advisory locks are re-entrant per session: the same session "acquires" again. This is why
    a lock connection must never be shared or returned to a pool."""
    with engine.connect() as same, engine.connect() as other:
        assert try_advisory_lock(same, NS_CONVERSATION, 42)
        assert try_advisory_lock(same, NS_CONVERSATION, 42)  # the trap
        assert not try_advisory_lock(other, NS_CONVERSATION, 42)
        same.execute(text("SELECT pg_advisory_unlock_all()"))


def test_y2_lock_connection_is_detached_and_closed(db_url: str) -> None:
    # A one-connection pool makes any reuse of the lock connection visible.
    engine = create_engine(db_url, pool_size=1, max_overflow=0, pool_timeout=2)
    try:
        with engine.begin() as conn:
            cid = make_conversation(conn, "SYN-chat-y2")

        # conversation_lock takes the idle pooled DBAPI connection out of the pool for good.
        with conversation_lock(engine, cid) as lock:
            assert lock is not None
            lock_pid = lock.connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
            lock.connection.rollback()
            assert engine.pool.checkedout() == 0  # the lock connection is not a pool checkout
            with engine.connect() as pooled:
                pooled_pid = pooled.execute(text("SELECT pg_backend_pid()")).scalar_one()
                assert pooled_pid != lock_pid
                # The pooled session cannot take (or re-enter) the lock the detached one holds.
                assert not try_advisory_lock(pooled, NS_CONVERSATION, cid)
            # A second task asking for the same conversation gets None, not a shared handle.
            with conversation_lock(engine, cid) as again:
                assert again is None

        # Released and really closed: the backend is gone and never came back through the pool.
        assert lock.connection.closed
        assert not _backend_alive(engine, lock_pid)
        with engine.connect() as pooled:
            assert pooled.execute(text("SELECT pg_backend_pid()")).scalar_one() != lock_pid
            assert try_advisory_lock(pooled, NS_CONVERSATION, cid)
            pooled.execute(text("SELECT pg_advisory_unlock_all()"))
    finally:
        engine.dispose()


def test_singleton_is_exclusive_and_bumps_epoch(engine: Engine) -> None:
    first = WorkerSingleton(engine, on_lost=ExitRecorder())
    second = WorkerSingleton(engine, on_lost=ExitRecorder())
    t1 = first.acquire()
    try:
        with pytest.raises(SingletonBusyError):
            second.acquire()
    finally:
        first.release()
    t2 = second.acquire()
    second.release()
    assert t2.epoch == t1.epoch + 1


def test_y5_singleton_loss_calls_exit_and_fences_writes(engine: Engine) -> None:
    with engine.begin() as conn:
        enable_sending(conn)
        cid = make_conversation(conn)
        outbound = make_outbound(conn, make_draft(conn, cid, 0))
        job_id = jobs.enqueue(conn, "k", "x")
    exit_hook = ExitRecorder()
    singleton = WorkerSingleton(engine, on_lost=exit_hook)
    token = singleton.acquire()
    try:
        assert singleton.check()
        _terminate(engine, token.pid)
        # Fenced writes from any other connection now affect 0 rows.
        with engine.begin() as conn:
            assert not claim_send_intent(conn, outbound, 0, token)
            assert jobs.claim(conn, "w1", token) is None
        assert not singleton.check()
        assert exit_hook.codes == [EXIT_SINGLETON_LOST]
        assert singleton.token is None
    finally:
        singleton.release()
    assert job_row(engine, job_id).status == "queued"


def test_check_verifies_lock_ownership_not_just_liveness(engine: Engine) -> None:
    """A live connection that no longer holds (1, 0) must count as lost."""
    hook = ExitRecorder()
    s = WorkerSingleton(engine, on_lost=hook)
    s.acquire()
    try:
        assert s.check()
        assert s._conn is not None
        s._conn.execute(text("SELECT pg_advisory_unlock_all()"))  # connection stays up
        assert not s.check()
        assert hook.codes == [EXIT_SINGLETON_LOST]
    finally:
        s.release()


def test_check_fails_when_epoch_moves(engine: Engine, singleton: WorkerSingleton) -> None:
    """Same pid and lock, but another acquisition bumped the epoch (pid-reuse stand-in)."""
    token = singleton.token
    assert token is not None
    with engine.begin() as conn:
        conn.execute(text("UPDATE worker_singleton SET epoch = epoch + 1"))
        assert jobs.enqueue(conn, "k", "x") is not None
        assert jobs.claim(conn, "w1", token) is None
    assert not singleton.check()


def test_y5_watchdog_thread_exits_on_loss(engine: Engine) -> None:
    exit_hook = ExitRecorder()
    singleton = WorkerSingleton(engine, on_lost=exit_hook, check_timeout_s=1.0)
    token = singleton.acquire()
    singleton.start_watchdog(0.05)
    try:
        assert not exit_hook.called.wait(0.3)  # healthy: no exit
        _terminate(engine, token.pid)
        assert exit_hook.called.wait(5)
        assert exit_hook.codes == [EXIT_SINGLETON_LOST]
    finally:
        singleton.release()


class _FreezableProxy:
    """TCP forwarder whose traffic can be silently swallowed (a half-open network path)."""

    def __init__(self, host: str, port: int) -> None:
        self.frozen = threading.Event()
        self._upstream = (host, port)
        self._sockets: list[socket.socket] = []
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port = self._listener.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while True:
            try:
                client, _ = self._listener.accept()
            except OSError:
                return
            server = socket.create_connection(self._upstream)
            self._sockets += [client, server]
            for src, dst in ((client, server), (server, client)):
                threading.Thread(target=self._pump, args=(src, dst), daemon=True).start()

    def _pump(self, src: socket.socket, dst: socket.socket) -> None:
        try:
            while data := src.recv(65536):
                if not self.frozen.is_set():
                    dst.sendall(data)
        except OSError:
            pass

    def close(self) -> None:
        self._listener.close()
        for s in self._sockets:
            with contextlib.suppress(OSError):
                s.shutdown(socket.SHUT_RDWR)
            s.close()


@contextmanager
def _proxied_engine(db_url: str) -> Iterator[tuple[Engine, _FreezableProxy]]:
    url = make_url(db_url)
    proxy = _FreezableProxy(url.host or "127.0.0.1", url.port or 5432)
    engine = create_engine(url.set(host="127.0.0.1", port=proxy.port))
    try:
        yield engine, proxy
    finally:
        proxy.close()
        engine.dispose()


def test_y5_hung_check_hits_deadline(engine: Engine, db_url: str) -> None:
    """E5b: the singleton path goes silent; check() must give up at its deadline, not hang."""
    with _proxied_engine(db_url) as (proxied, proxy):
        hook = ExitRecorder()
        s = WorkerSingleton(proxied, on_lost=hook, check_timeout_s=0.5)
        token = s.acquire()
        assert s.check()
        proxy.frozen.set()
        _terminate(engine, token.pid)
        started = time.monotonic()
        assert not s.check()
        assert time.monotonic() - started < 2.0
        assert hook.codes == [EXIT_SINGLETON_LOST]
        proxy.close()  # unblocks the stuck probe so the connection can be closed
        time.sleep(0.2)
        s.release()


def _worker(
    engine: Engine,
    calls: list[tuple[int, int | None]],
    worker_id: str = "w-test",
    **setting_values: float,
) -> Worker:
    def handler(job: Job, lock: ConversationLock | None) -> None:
        calls.append((job.id, None if lock is None else lock.conversation_id))

    return Worker(
        engine,
        {"process_chat": handler, "k": handler},
        worker_id=worker_id,
        singleton=WorkerSingleton(engine, on_lost=ExitRecorder()),
        settings=settings(**setting_values),
        sleep=lambda s: None,
    )


def test_run_once_refuses_without_singleton(engine: Engine) -> None:
    worker = _worker(engine, [])
    with pytest.raises(SingletonNotHeldError):
        worker.run_once()


def test_worker_start_waits_before_recovery(engine: Engine) -> None:
    slept: list[float] = []
    worker = Worker(
        engine,
        {},
        singleton=WorkerSingleton(engine, on_lost=ExitRecorder()),
        settings=settings(worker_singleton_poll_s=3.0),
        sleep=slept.append,
    )
    try:
        worker.start()  # watchdog on by default
        assert slept == [6.0]
        assert worker.singleton._thread is not None and worker.singleton._thread.is_alive()
    finally:
        worker.stop()


def test_worker_start_recovers_orphans_with_merge_rule(engine: Engine) -> None:
    with engine.begin() as conn:
        for key in ("chat:1", "chat:2"):
            conn.execute(
                text(
                    "INSERT INTO job (kind, dedup_key, status, claimed_by, attempts) "
                    "VALUES ('process_chat', :k, 'running', 'crashed-worker', 1)"
                ),
                {"k": key},
            )
        jobs.enqueue(conn, "process_chat", "chat:1")
    worker = _worker(engine, [])
    try:
        assert worker.start(watchdog=False) == {1: "superseded", 2: "queued"}
    finally:
        worker.stop()


def test_gap_old_worker_cannot_claim_after_losing_singleton(engine: Engine) -> None:
    """E5: A loses its singleton session but keeps running (watchdog not yet fired); B takes
    over. A's claims are fenced out; only B processes jobs."""
    calls_a: list[tuple[int, int | None]] = []
    calls_b: list[tuple[int, int | None]] = []
    a = _worker(engine, calls_a, worker_id="A")
    a.start(watchdog=False)
    b = _worker(engine, calls_b, worker_id="B")
    try:
        token_a = a.singleton.token
        assert token_a is not None
        _terminate(engine, token_a.pid)
        b.start(watchdog=False)
        with engine.begin() as conn:
            ids = [jobs.enqueue(conn, "k", f"SYN-{i}") for i in range(4)]
        assert a.run_once() is None  # fenced: A cannot take anything
        while b.run_once() is not None:
            pass
    finally:
        a.stop()
        b.stop()
    assert calls_a == []
    assert sorted(job_id for job_id, _ in calls_b) == ids


def test_worker_runs_job_under_conversation_lock(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
        job_id = jobs.enqueue(conn, "process_chat", f"chat:{cid}", {"conversation_id": cid})
    calls: list[tuple[int, int | None]] = []
    worker = _worker(engine, calls)
    worker.start(watchdog=False)
    try:
        result = worker.run_once()
        assert result is not None and result.outcome == "done"
        assert calls == [(job_id, cid)]
        assert worker.run_once() is None
    finally:
        worker.stop()


def test_y6_lock_busy_requeues_and_is_never_done(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
        job_id = jobs.enqueue(conn, "process_chat", f"chat:{cid}", {"conversation_id": cid})
    calls: list[tuple[int, int | None]] = []
    worker = _worker(engine, calls)
    worker.start(watchdog=False)
    try:
        with conversation_lock(engine, cid) as held:  # another task holds the conversation
            assert held is not None
            result = worker.run_once()
        assert result is not None and result.outcome == "lock_busy:queued"
        assert calls == []
        row = job_row(engine, job_id)
        # Not done, attempt given back, claim cleared, run_after pushed by the busy delay.
        assert (row.status, row.attempts, row.claimed_by) == ("queued", 0, None)
        assert row.wait_s > 20
        assert worker.run_once() is None  # not due yet
    finally:
        worker.stop()


def test_y6_lock_busy_with_queued_twin_is_superseded(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
        payload = {"conversation_id": cid}
        first = jobs.enqueue(conn, "process_chat", f"chat:{cid}", payload)
    worker = _worker(engine, [])
    worker.start(watchdog=False)
    try:
        token = worker.singleton.token
        assert token is not None
        with conversation_lock(engine, cid) as held:
            assert held is not None
            with engine.begin() as conn:
                claimed = jobs.claim(conn, worker.worker_id, token)
                assert claimed is not None and claimed.id == first
                twin = jobs.enqueue(conn, "process_chat", f"chat:{cid}", payload)
                assert (
                    jobs.requeue(
                        conn, first, delay_s=5, worker_id=worker.worker_id, refund_attempt=True
                    )
                    == "superseded"
                )
        with engine.connect() as conn:
            statuses = {r.id: r.status for r in conn.execute(text("SELECT id, status FROM job"))}
        assert statuses == {first: "superseded", twin: "queued"}
        assert job_row(engine, twin).attempts == 0  # the refunded attempt is not inherited
    finally:
        worker.stop()


def test_failing_handler_is_retried_not_lost(engine: Engine) -> None:
    def boom(job: Job, lock: ConversationLock | None) -> None:
        raise RuntimeError("synthetic failure")

    with engine.begin() as conn:
        job_id = jobs.enqueue(conn, "unregistered", "x")
        other = jobs.enqueue(conn, "explodes", "y")
    worker = Worker(
        engine,
        {"explodes": boom},
        worker_id="w-test",
        singleton=WorkerSingleton(engine, on_lost=ExitRecorder()),
        settings=settings(),
        sleep=lambda s: None,
    )
    worker.start(watchdog=False)
    try:
        results = {r.job_id: r.outcome for r in (worker.run_once(), worker.run_once()) if r}
    finally:
        worker.stop()
    assert results == {job_id: "failed:queued", other: "failed:queued"}
    assert job_row(engine, job_id).last_error_code == "KeyError"
    assert job_row(engine, other).last_error_code == "RuntimeError"


def test_runtime_role_check(engine: Engine) -> None:
    with engine.begin() as conn:
        check_runtime_role(conn, AppEnv.TEST)  # owner allowed outside production
        with pytest.raises(UnsafeDatabaseRoleError):
            check_runtime_role(conn, AppEnv.PRODUCTION)  # superuser / owner
        conn.execute(text("SET LOCAL ROLE assistant_app"))
        check_runtime_role(conn, AppEnv.PRODUCTION)  # a member of the runtime role is fine
    worker = Worker(
        engine,
        {},
        singleton=WorkerSingleton(engine, on_lost=ExitRecorder()),
        settings=settings(app_env=AppEnv.PRODUCTION),
        sleep=lambda s: None,
    )
    with pytest.raises(UnsafeDatabaseRoleError):
        worker.start()
    assert worker.singleton.token is None  # refused before taking the singleton


def test_singleton_token_params() -> None:
    assert SingletonToken(7, 3).params() == {"singleton_pid": 7, "singleton_epoch": 3}
