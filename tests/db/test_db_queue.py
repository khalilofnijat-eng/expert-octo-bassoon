# SYNTHETIC: job keys and payloads are made up.
"""Job queue on real PostgreSQL: uniqueness, SKIP LOCKED claims, merge rule, backoff, dead."""

from __future__ import annotations

import random
import threading

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.queue import jobs


def _status(engine: Engine, job_id: int) -> str:
    with engine.connect() as conn:
        return str(
            conn.execute(text("SELECT status FROM job WHERE id = :i"), {"i": job_id}).one()[0]
        )


def _insert_running(engine: Engine, key: str, claimed_by: str) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    "INSERT INTO job (kind, dedup_key, status, claimed_by, claimed_at) "
                    "VALUES ('process_chat', :k, 'running', :w, now()) RETURNING id"
                ),
                {"k": key, "w": claimed_by},
            ).scalar_one()
        )


def test_queued_uniqueness_and_running_does_not_block(engine: Engine) -> None:
    with engine.begin() as conn:
        first = jobs.enqueue(conn, "process_chat", "chat:1")
        assert first is not None
        assert jobs.enqueue(conn, "process_chat", "chat:1") is None  # ON CONFLICT DO NOTHING
        assert jobs.enqueue(conn, "process_chat", "chat:2") is not None
    with engine.begin() as conn, pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO job (kind, dedup_key) VALUES ('process_chat', 'chat:1')"))

    # A message arriving while the job runs gets a new queued job: nothing is lost.
    with engine.begin() as conn:
        claimed = jobs.claim(conn, "w1")
    assert claimed is not None and claimed.id == first
    with engine.begin() as conn:
        second = jobs.enqueue(conn, "process_chat", "chat:1")
        assert second is not None and second != first
        assert jobs.enqueue(conn, "process_chat", "chat:1") is None
        assert jobs.complete(conn, first, "w1")
    assert _status(engine, second) == "queued"


def test_claim_respects_run_after(engine: Engine) -> None:
    with engine.begin() as conn:
        jobs.enqueue(conn, "k", "later", delay_s=60)
        assert jobs.claim(conn, "w1") is None
        now_id = jobs.enqueue(conn, "k", "now")
        got = jobs.claim(conn, "w1")
    assert got is not None and got.id == now_id


def test_skip_locked_claim_does_not_block_or_double_claim(engine: Engine) -> None:
    with engine.begin() as conn:
        a = jobs.enqueue(conn, "k", "a")
        b = jobs.enqueue(conn, "k", "b")
    with engine.connect() as c1, engine.connect() as c2:
        c1.begin()
        first = jobs.claim(c1, "w1")  # row lock held, not committed
        c2.begin()
        c2.execute(text("SET LOCAL lock_timeout = '1s'"))
        second = jobs.claim(c2, "w2")  # must skip, not wait
        assert first is not None and second is not None
        assert {first.id, second.id} == {a, b}
        assert jobs.claim(c2, "w2") is None
        c1.commit()
        c2.commit()


def test_concurrent_claim_two_workers_no_double_processing(engine: Engine) -> None:
    total = 200
    with engine.begin() as conn:
        for i in range(total):
            jobs.enqueue(conn, "k", f"job-{i}")
    seen: dict[str, list[int]] = {"w1": [], "w2": []}
    start = threading.Barrier(2)

    def work(name: str) -> None:
        start.wait()
        while True:
            with engine.begin() as conn:
                job = jobs.claim(conn, name)
                if job is None:
                    return
                seen[name].append(job.id)
                assert jobs.complete(conn, job.id, name)

    threads = [threading.Thread(target=work, args=(n,)) for n in seen]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    all_ids = seen["w1"] + seen["w2"]
    assert len(all_ids) == total
    assert len(set(all_ids)) == total
    assert seen["w1"] and seen["w2"]  # both workers took part
    with engine.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM job WHERE status = 'done'")).scalar() == total
        )


def test_complete_only_by_claiming_worker(engine: Engine) -> None:
    with engine.begin() as conn:
        jobs.enqueue(conn, "k", "x")
        job = jobs.claim(conn, "w1")
        assert job is not None
        assert not jobs.complete(conn, job.id, "someone-else")
        assert jobs.complete(conn, job.id, "w1")
        assert not jobs.complete(conn, job.id, "w1")  # already done: CAS fails


def test_fail_backs_off_then_dead(engine: Engine) -> None:
    with engine.begin() as conn:
        job_id = jobs.enqueue(conn, "k", "flaky")
        conn.execute(text("UPDATE job SET max_attempts = 2 WHERE id = :i"), {"i": job_id})
        job = jobs.claim(conn, "w1")
        assert job is not None
        assert jobs.fail(conn, job, "boom") == "queued"
        row = conn.execute(
            text(
                "SELECT attempts, run_after - now() AS wait, last_error_code FROM job WHERE id = :i"
            ),
            {"i": job_id},
        ).one()
        assert row.attempts == 1 and row.last_error_code == "boom"
        assert row.wait.total_seconds() >= jobs.BACKOFF_BASE_S - 1
        conn.execute(text("UPDATE job SET run_after = now() WHERE id = :i"), {"i": job_id})
        job = jobs.claim(conn, "w1")
        assert job is not None and job.attempts == 1
        assert jobs.fail(conn, job, "boom") == "dead"
    assert _status(engine, job_id) == "dead"


def test_backoff_bounds() -> None:
    rng = random.Random(1)
    for attempts in range(1, 20):
        value = jobs.backoff_seconds(attempts, rng)
        assert jobs.BACKOFF_BASE_S <= value <= jobs.BACKOFF_MAX_S
    assert jobs.backoff_seconds(30, rng) >= jobs.BACKOFF_MAX_S / 2


def test_y1_crash_restart_merge_rule(engine: Engine) -> None:
    """Y1: a dead worker's running job becomes superseded if the same key is queued, else
    queued. Running recovery again (another crash-restart) raises nothing and changes nothing."""
    with_queued = _insert_running(engine, "chat:1", "dead-worker")
    alone = _insert_running(engine, "chat:2", "dead-worker")
    # Two orphans for one key (e.g. crash during a lock-busy requeue): one queued, one superseded.
    twin_a = _insert_running(engine, "chat:3", "dead-worker")
    twin_b = _insert_running(engine, "chat:3", "dead-worker")
    mine = _insert_running(engine, "chat:4", "new-worker")
    with engine.begin() as conn:
        queued = jobs.enqueue(conn, "process_chat", "chat:1")

    with engine.begin() as conn:
        outcome = jobs.recover_orphaned(conn, "new-worker")
    assert outcome == {
        with_queued: "superseded",
        alone: "queued",
        twin_a: "queued",
        twin_b: "superseded",
    }
    assert _status(engine, queued) == "queued"
    assert _status(engine, mine) == "running"  # this instance's own job is not taken over

    with engine.begin() as conn:
        assert jobs.recover_orphaned(conn, "new-worker") == {}


def test_requeue_falls_back_to_superseded_when_enqueue_wins_race(engine: Engine) -> None:
    running = _insert_running(engine, "chat:9", "w1")
    with engine.connect() as racer, engine.connect() as conn:
        racer.begin()
        jobs.enqueue(racer, "process_chat", "chat:9")  # uncommitted queued row
        conn.begin()

        result: list[str | None] = []

        def do_requeue() -> None:
            result.append(jobs.requeue(conn, running, delay_s=0, worker_id="w1"))

        t = threading.Thread(target=do_requeue)
        t.start()
        t.join(0.5)  # blocks on the racer's index entry
        racer.commit()
        t.join()
        conn.commit()
    assert result == ["superseded"]
