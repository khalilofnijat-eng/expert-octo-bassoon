# SYNTHETIC: job keys and payloads are made up.
"""Job queue on real PostgreSQL: uniqueness, LEAST merge, fenced SKIP LOCKED claims, attempts at
claim, merge rule, backoff, dead + alert, defer, requeue_dead."""

from __future__ import annotations

import random
import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.queue import jobs
from app.queue.locks import SingletonToken
from tests.db.factories import alerts, audit_mark, job_row


def _insert_running(engine: Engine, key: str, claimed_by: str, attempts: int = 1) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    "INSERT INTO job (kind, dedup_key, status, claimed_by, claimed_at, attempts) "
                    "VALUES ('process_chat', :k, 'running', :w, now(), :a) RETURNING id"
                ),
                {"k": key, "w": claimed_by, "a": attempts},
            ).scalar_one()
        )


def _due_now(engine: Engine, job_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE job SET run_after = now() WHERE id = :i"), {"i": job_id})


def test_queued_uniqueness_and_running_does_not_block(
    engine: Engine, token: SingletonToken
) -> None:
    with engine.begin() as conn:
        first = jobs.enqueue(conn, "process_chat", "chat:1")
        assert first is not None
        assert jobs.enqueue(conn, "process_chat", "chat:1") == first  # merged, same job
        assert jobs.enqueue(conn, "process_chat", "chat:2") not in (None, first)
    with engine.begin() as conn, pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO job (kind, dedup_key) VALUES ('process_chat', 'chat:1')"))

    # A message arriving while the job runs gets a new queued job: nothing is lost.
    with engine.begin() as conn:
        claimed = jobs.claim(conn, "w1", token)
    assert claimed is not None and claimed.id == first
    with engine.begin() as conn:
        second = jobs.enqueue(conn, "process_chat", "chat:1")
        assert second is not None and second != first
        assert jobs.enqueue(conn, "process_chat", "chat:1") == second
        assert jobs.complete(conn, first, "w1")
    assert job_row(engine, second).status == "queued"


def test_enqueue_pulls_run_after_forward_unless_in_error_backoff(
    engine: Engine, token: SingletonToken
) -> None:
    with engine.begin() as conn:
        job_id = jobs.enqueue(conn, "process_chat", "chat:1", delay_s=600)
    assert job_row(engine, job_id).wait_s > 500
    with engine.begin() as conn:
        assert jobs.enqueue(conn, "process_chat", "chat:1") == job_id
    assert job_row(engine, job_id).wait_s <= 1  # LEAST(old, new)
    with engine.begin() as conn:
        assert jobs.enqueue(conn, "process_chat", "chat:1", delay_s=600) == job_id
    assert job_row(engine, job_id).wait_s <= 1  # never pushed back

    # In failure backoff (last_error_code set) a new message does not erase the backoff.
    with engine.begin() as conn:
        job = jobs.claim(conn, "w1", token)
        assert job is not None and jobs.fail(conn, job, "LLMTimeout") == "queued"
    waiting = job_row(engine, job_id).wait_s
    assert waiting >= jobs.BACKOFF_BASE_S - 1
    with engine.begin() as conn:
        assert jobs.enqueue(conn, "process_chat", "chat:1") is None
    assert job_row(engine, job_id).wait_s == pytest.approx(waiting, abs=1)


def test_enqueue_while_claim_in_flight_is_not_lost(engine: Engine, token: SingletonToken) -> None:
    """The LEAST upsert waits for a claim that holds the queued row, then inserts a new row."""
    with engine.begin() as conn:
        first = jobs.enqueue(conn, "process_chat", "chat:1")
    with engine.connect() as claimer:
        claimer.begin()
        assert jobs.claim(claimer, "w1", token) is not None
        result: list[int | None] = []

        def upsert() -> None:
            with engine.begin() as conn:
                result.append(jobs.enqueue(conn, "process_chat", "chat:1"))

        t = threading.Thread(target=upsert)
        t.start()
        t.join(0.5)
        assert t.is_alive()  # blocked on the row the claim holds
        claimer.commit()
        t.join(5)
    assert result and result[0] not in (None, first)
    assert job_row(engine, result[0]).status == "queued"


def test_claim_respects_run_after(engine: Engine, token: SingletonToken) -> None:
    with engine.begin() as conn:
        jobs.enqueue(conn, "k", "later", delay_s=60)
        assert jobs.claim(conn, "w1", token) is None
        now_id = jobs.enqueue(conn, "k", "now")
        got = jobs.claim(conn, "w1", token)
    assert got is not None and got.id == now_id and got.attempts == 1  # counted at claim


def test_claim_is_fenced_on_the_singleton(engine: Engine, token: SingletonToken) -> None:
    with engine.begin() as conn:
        job_id = jobs.enqueue(conn, "k", "x")
        assert jobs.claim(conn, "w1", SingletonToken(token.pid + 1, token.epoch)) is None
        assert jobs.claim(conn, "w1", SingletonToken(token.pid, token.epoch + 1)) is None
    assert job_row(engine, job_id).status == "queued"


def test_skip_locked_claim_does_not_block_or_double_claim(
    engine: Engine, token: SingletonToken
) -> None:
    with engine.begin() as conn:
        a = jobs.enqueue(conn, "k", "a")
        b = jobs.enqueue(conn, "k", "b")
    with engine.connect() as c1, engine.connect() as c2:
        c1.begin()
        first = jobs.claim(c1, "w1", token)  # row lock held, not committed
        c2.begin()
        c2.execute(text("SET LOCAL lock_timeout = '1s'"))
        second = jobs.claim(c2, "w2", token)  # must skip, not wait
        assert first is not None and second is not None
        assert {first.id, second.id} == {a, b}
        assert jobs.claim(c2, "w2", token) is None
        c1.commit()
        c2.commit()


def test_concurrent_claim_two_workers_no_double_processing(
    engine: Engine, token: SingletonToken
) -> None:
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
                job = jobs.claim(conn, name, token)
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


def test_complete_only_by_claiming_worker(engine: Engine, token: SingletonToken) -> None:
    with engine.begin() as conn:
        jobs.enqueue(conn, "k", "x")
        job = jobs.claim(conn, "w1", token)
        assert job is not None
        assert not jobs.complete(conn, job.id, "someone-else")
        assert jobs.complete(conn, job.id, "w1")
        assert not jobs.complete(conn, job.id, "w1")  # already done: CAS fails


def test_fail_backs_off_then_dead_with_alert(engine: Engine, token: SingletonToken) -> None:
    mark = audit_mark(engine)
    with engine.begin() as conn:
        job_id = jobs.enqueue(conn, "k", "flaky")
        conn.execute(text("UPDATE job SET max_attempts = 2 WHERE id = :i"), {"i": job_id})
        job = jobs.claim(conn, "w1", token)
        assert job is not None and job.attempts == 1
        assert jobs.fail(conn, job, "boom") == "queued"
    row = job_row(engine, job_id)
    assert (row.attempts, row.last_error_code) == (1, "boom")  # fail does not count again
    assert row.wait_s >= jobs.BACKOFF_BASE_S - 1
    assert alerts(engine, job_id, mark) == []
    _due_now(engine, job_id)
    with engine.begin() as conn:
        job = jobs.claim(conn, "w1", token)
        assert job is not None and job.attempts == 2
        assert jobs.fail(conn, job, "boom") == "dead"
    assert job_row(engine, job_id).status == "dead"
    assert [tuple(a) for a in alerts(engine, job_id, mark)] == [("job_dead", "boom")]


def test_backoff_reaches_cap_within_max_attempts() -> None:
    rng = random.Random(1)
    for attempts in range(1, 20):
        value = jobs.backoff_seconds(attempts, rng)
        assert jobs.BACKOFF_BASE_S <= value <= jobs.BACKOFF_MAX_S
    # With the default max_attempts (12) the last backoffs run at the 1 h cap.
    ceilings = [min(jobs.BACKOFF_MAX_S, jobs.BACKOFF_BASE_S * 2 ** (a - 1)) for a in range(1, 12)]
    assert ceilings[-1] == jobs.BACKOFF_MAX_S
    total = sum(ceilings)  # 1.7-3.4 h from first failure to dead
    assert total / 2 > 1.5 * 3600
    assert total < 3.5 * 3600


def test_defer_does_not_count_and_keeps_its_time(engine: Engine, token: SingletonToken) -> None:
    until = datetime.now(UTC) + timedelta(hours=1)
    with engine.begin() as conn:
        job_id = jobs.enqueue(conn, "process_chat", "chat:1")
        job = jobs.claim(conn, "w1", token)
        assert job is not None
        assert jobs.defer(conn, job, until, "llm_outage") == "queued"
    row = job_row(engine, job_id)
    assert (row.status, row.attempts, row.last_error_code) == ("queued", 0, "llm_outage")
    assert row.wait_s == pytest.approx(3600, abs=5)
    with engine.begin() as conn:
        assert jobs.enqueue(conn, "process_chat", "chat:1") is None  # not pulled forward


def test_requeue_dead(engine: Engine, token: SingletonToken) -> None:
    with engine.begin() as conn:
        job_id = jobs.enqueue(conn, "process_chat", "chat:1")
        conn.execute(text("UPDATE job SET max_attempts = 1 WHERE id = :i"), {"i": job_id})
        job = jobs.claim(conn, "w1", token)
        assert job is not None and jobs.fail(conn, job, "boom") == "dead"
        assert jobs.requeue_dead(conn, job_id, actor="owner") == "queued"
        assert jobs.requeue_dead(conn, job_id, actor="owner") is None  # no longer dead
    row = job_row(engine, job_id)
    assert (row.status, row.attempts, row.last_error_code) == ("queued", 0, None)

    # With a queued twin the dead job is superseded; the twin does the work.
    with engine.begin() as conn:
        job = jobs.claim(conn, "w1", token)
        assert job is not None and jobs.fail(conn, job, "boom") == "dead"
        twin = jobs.enqueue(conn, "process_chat", "chat:1")
        assert jobs.requeue_dead(conn, job_id, actor="owner") == "superseded"
    assert job_row(engine, twin).status == "queued"


def test_y1_crash_restart_merge_rule(engine: Engine) -> None:
    """Y1: a dead worker's running job becomes superseded if the same key is queued (handing on
    its attempt count), else queued with backoff; an orphan that used up max_attempts goes dead
    with an alert. Running recovery again raises nothing and changes nothing."""
    mark = audit_mark(engine)
    with_queued = _insert_running(engine, "chat:1", "dead-worker", attempts=3)
    alone = _insert_running(engine, "chat:2", "dead-worker")
    # Two orphans for one key: one queued, one superseded.
    twin_a = _insert_running(engine, "chat:3", "dead-worker")
    twin_b = _insert_running(engine, "chat:3", "dead-worker")
    poison = _insert_running(engine, "chat:5", "dead-worker", attempts=12)
    mine = _insert_running(engine, "chat:4", "new-worker")
    with engine.begin() as conn:
        queued = jobs.enqueue(conn, "process_chat", "chat:1")
    assert queued is not None

    with engine.begin() as conn:
        outcome = jobs.recover_orphaned(conn, "new-worker")
    assert outcome == {
        with_queued: "superseded",
        alone: "queued",
        twin_a: "queued",
        twin_b: "superseded",
        poison: "dead",
    }
    assert job_row(engine, queued).attempts == 3  # inherited from the superseded orphan
    assert job_row(engine, alone).wait_s >= jobs.BACKOFF_BASE_S - 1
    assert job_row(engine, alone).last_error_code == "worker_lost"
    assert job_row(engine, mine).status == "running"  # this instance's own job is not taken over
    assert [tuple(a) for a in alerts(engine, poison, mark)] == [("job_dead", "worker_lost")]

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
