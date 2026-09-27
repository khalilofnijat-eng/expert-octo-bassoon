# SYNTHETIC: conversations and jobs are made up.
"""Advisory locks and the single worker: Y1 (worker start), Y2, Y5, Y6 on real PostgreSQL."""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import Engine, create_engine, text

from app.db.cas import claim_send_intent
from app.queue import jobs
from app.queue.jobs import Job
from app.queue.locks import (
    EXIT_SINGLETON_LOST,
    NS_CONVERSATION,
    NS_SINGLETON,
    ConversationLock,
    SingletonBusyError,
    WorkerSingleton,
    conversation_lock,
    try_advisory_lock,
)
from app.queue.worker import Worker
from tests.db.factories import make_conversation, make_draft, make_outbound


class ExitRecorder:
    def __init__(self) -> None:
        self.codes: list[int] = []
        self.called = threading.Event()

    def __call__(self, code: int) -> None:
        self.codes.append(code)
        self.called.set()


def _backend_alive(engine: Engine, pid: int) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE pid = :p)"), {"p": pid}
            ).scalar()
        )


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


def test_singleton_is_exclusive(engine: Engine) -> None:
    first = WorkerSingleton(engine, on_lost=ExitRecorder())
    second = WorkerSingleton(engine, on_lost=ExitRecorder())
    first.acquire()
    try:
        with pytest.raises(SingletonBusyError):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()


def test_y5_singleton_loss_calls_exit_and_fences_writes(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
        outbound = make_outbound(conn, make_draft(conn, cid, 0))
    exit_hook = ExitRecorder()
    singleton = WorkerSingleton(engine, on_lost=exit_hook)
    pid = singleton.acquire()
    try:
        assert singleton.check()
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(:p)"), {"p": pid})
        # The fenced intent CAS from any other connection now affects 0 rows.
        with engine.begin() as conn:
            assert not claim_send_intent(conn, outbound, 0, pid)
        assert not singleton.check()
        assert exit_hook.codes == [EXIT_SINGLETON_LOST]
    finally:
        singleton.release()


def test_y5_watchdog_thread_exits_on_loss(engine: Engine) -> None:
    exit_hook = ExitRecorder()
    singleton = WorkerSingleton(engine, on_lost=exit_hook)
    pid = singleton.acquire()
    singleton.start_watchdog(0.05)
    try:
        assert not exit_hook.called.wait(0.3)  # healthy: no exit
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(:p)"), {"p": pid})
        assert exit_hook.called.wait(5)
        assert exit_hook.codes == [EXIT_SINGLETON_LOST]
    finally:
        singleton.release()


def _worker(engine: Engine, calls: list[tuple[int, int | None]]) -> Worker:
    def handler(job: Job, lock: ConversationLock | None) -> None:
        calls.append((job.id, None if lock is None else lock.conversation_id))

    return Worker(
        engine,
        {"process_chat": handler},
        worker_id="w-test",
        singleton=WorkerSingleton(engine, on_lost=ExitRecorder()),
        lock_busy_delay_s=30,
    )


def test_worker_start_recovers_orphans_with_merge_rule(engine: Engine) -> None:
    with engine.begin() as conn:
        for key in ("chat:1", "chat:2"):
            conn.execute(
                text(
                    "INSERT INTO job (kind, dedup_key, status, claimed_by) "
                    "VALUES ('process_chat', :k, 'running', 'crashed-worker')"
                ),
                {"k": key},
            )
        jobs.enqueue(conn, "process_chat", "chat:1")
    worker = _worker(engine, [])
    try:
        assert worker.start() == {1: "superseded", 2: "queued"}
    finally:
        worker.stop()


def test_worker_runs_job_under_conversation_lock(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
        job_id = jobs.enqueue(conn, "process_chat", f"chat:{cid}", {"conversation_id": cid})
    calls: list[tuple[int, int | None]] = []
    worker = _worker(engine, calls)
    worker.start()
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
    worker.start()
    try:
        with conversation_lock(engine, cid) as held:  # another task holds the conversation
            assert held is not None
            result = worker.run_once()
        assert result is not None and result.outcome == "lock_busy:queued"
        assert calls == []
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT status, attempts, claimed_by, run_after - now() AS wait "
                    "FROM job WHERE id = :i"
                ),
                {"i": job_id},
            ).one()
        assert row.status == "queued" and row.attempts == 0 and row.claimed_by is None
        assert row.wait.total_seconds() > 20  # run_after pushed by lock_busy_delay_s
        assert worker.run_once() is None  # not due yet
    finally:
        worker.stop()


def test_y6_lock_busy_with_queued_twin_is_superseded(engine: Engine) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
        payload = {"conversation_id": cid}
        first = jobs.enqueue(conn, "process_chat", f"chat:{cid}", payload)
    worker = _worker(engine, [])
    worker.start()
    try:
        with conversation_lock(engine, cid) as held:
            assert held is not None
            with engine.begin() as conn:
                claimed = jobs.claim(conn, worker.worker_id)
                assert claimed is not None and claimed.id == first
                twin = jobs.enqueue(conn, "process_chat", f"chat:{cid}", payload)
                assert jobs.requeue(conn, first, delay_s=5, worker_id=worker.worker_id) == (
                    "superseded"
                )
        with engine.connect() as conn:
            statuses = {r.id: r.status for r in conn.execute(text("SELECT id, status FROM job"))}
        assert statuses == {first: "superseded", twin: "queued"}
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
    )
    worker.start()
    try:
        results = {r.job_id: r.outcome for r in (worker.run_once(), worker.run_once()) if r}
    finally:
        worker.stop()
    assert results == {job_id: "failed:queued", other: "failed:queued"}
    with engine.connect() as conn:
        codes = dict(conn.execute(text("SELECT id, last_error_code FROM job")).all())
    assert codes == {job_id: "KeyError", other: "RuntimeError"}
