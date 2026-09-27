# SYNTHETIC: jobs and conversations are made up.
"""Real process crashes (SIGKILL) against real PostgreSQL: a poison job ends up dead, and a job
killed after writing its draft does not write a second one when re-run."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from typing import Any

from sqlalchemy import Engine, text

from app.config import REPO_ROOT
from app.queue import jobs
from tests.db.factories import alerts, audit_mark, customer_message, job_row, make_conversation

CHILD = os.path.join(os.path.dirname(__file__), "child_worker.py")


def _run_child(url: str, mode: str) -> tuple[int, list[dict[str, Any]]]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT), "APP_ENV": "test"}
    proc = subprocess.run(
        [sys.executable, CHILD, url, mode],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO_ROOT),
        env=env,
    )
    events = [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]
    return proc.returncode, events


def _due_now(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE job SET run_after = now() WHERE status = 'queued'"))


def test_poison_job_that_kills_the_worker_goes_dead(engine: Engine, db_url: str) -> None:
    mark = audit_mark(engine)
    with engine.begin() as conn:
        job_id = jobs.enqueue(conn, "poison", "SYN-poison")
        conn.execute(text("UPDATE job SET max_attempts = 3 WHERE id = :i"), {"i": job_id})
    # Each crash is followed by a restart whose recovery requeues the orphan with backoff (and
    # claims nothing yet); we skip the backoff and restart again.
    codes, recoveries = [], []
    for _ in range(6):
        code, events = _run_child(db_url, "poison")
        codes.append(code)
        recoveries += [e["jobs"] for e in events if e["event"] == "recovered" and e["jobs"]]
        _due_now(engine)
    assert codes == [-signal.SIGKILL, 0] * 3
    key = str(job_id)
    assert recoveries == [{key: "queued"}, {key: "queued"}, {key: "dead"}]
    row = job_row(engine, job_id)
    assert (row.status, row.last_error_code) == ("dead", "worker_lost")
    assert [tuple(a) for a in alerts(engine, job_id, mark)] == [("job_dead", "worker_lost")]


def test_crash_after_draft_does_not_duplicate_it(engine: Engine, db_url: str) -> None:
    with engine.begin() as conn:
        cid = make_conversation(conn)
    customer_message(engine, cid, "SYN-m1")
    with engine.begin() as conn:
        job_id = jobs.enqueue(conn, "process_chat", f"chat:{cid}", {"conversation_id": cid})

    code, events = _run_child(db_url, "draft_then_die")
    assert code == -signal.SIGKILL
    first = next(e["draft_id"] for e in events if e["event"] == "draft")
    assert job_row(engine, job_id).status == "running"  # killed before complete

    code, events = _run_child(db_url, "draft")  # restart: recovery requeues with backoff
    assert code == 0
    assert events == [
        {"event": "recovered", "jobs": {str(job_id): "queued"}},
        {"event": "result", "outcome": None},
    ]
    _due_now(engine)
    code, events = _run_child(db_url, "draft")  # the job runs again
    assert code == 0
    again = next(e["draft_id"] for e in events if e["event"] == "draft")
    assert again == first
    assert events[-1] == {"event": "result", "outcome": "done"}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM draft")).scalar() == 1
        assert conn.execute(text("SELECT last_processed_seq FROM conversation")).scalar() == 1
    assert job_row(engine, job_id).status == "done"
