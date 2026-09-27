"""Persistent job queue on the ``job`` table (docs/ARCHITECTURE.md §6.1–§6.2).

Functions take a ``Connection`` and do not commit; the caller owns the transaction. Every status
change is a conditional UPDATE (CAS on ``status`` and, where it matters, ``claimed_by``).

Requeue merge rule (shared by startup recovery, lock-not-acquired and retryable failure): if a
``queued`` job with the same (kind, dedup_key) exists, this job becomes ``superseded`` (the queued
one reads the messages from the DB anyway); otherwise it goes back to ``queued``. A concurrent
enqueue can win the race for the partial UNIQUE index; the savepoint catches that and falls back to
``superseded``, so the rule never raises a unique violation and never crash-loops.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.expression import bindparam

BACKOFF_BASE_S = 10.0
BACKOFF_MAX_S = 3600.0


@dataclass(frozen=True)
class Job:
    id: int
    kind: str
    dedup_key: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    claimed_by: str


def backoff_seconds(attempts: int, rng: random.Random | None = None) -> float:
    """Exponential backoff with full jitter, 10 s → 1 h (§6.2). ``attempts`` counts failures."""
    ceiling = min(BACKOFF_MAX_S, BACKOFF_BASE_S * 2 ** max(attempts - 1, 0))
    return max(BACKOFF_BASE_S, (rng or random).uniform(ceiling / 2, ceiling))


def enqueue(
    conn: Connection,
    kind: str,
    dedup_key: str,
    payload: dict[str, Any] | None = None,
    delay_s: float = 0.0,
) -> int | None:
    """Add a queued job. Returns its id, or ``None`` if one with the same key is already queued.

    A job that is ``running`` does not block this insert (the partial UNIQUE covers ``queued``
    only), so a message that arrives during a run gets its own queued job and is not lost.
    """
    stmt = text(
        """
        INSERT INTO job (kind, dedup_key, payload, run_after)
        VALUES (:kind, :dedup_key, :payload, now() + make_interval(secs => :delay))
        ON CONFLICT (kind, dedup_key) WHERE status = 'queued' DO NOTHING
        RETURNING id
        """
    ).bindparams(bindparam("payload", type_=JSONB))
    row = conn.execute(
        stmt, {"kind": kind, "dedup_key": dedup_key, "payload": payload or {}, "delay": delay_s}
    ).first()
    return None if row is None else int(row[0])


def claim(conn: Connection, worker_id: str) -> Job | None:
    """Claim the next due job with ``FOR UPDATE SKIP LOCKED`` (§6.2), or return ``None``."""
    row = conn.execute(
        text(
            """
            UPDATE job SET status = 'running', claimed_by = :me, claimed_at = now(),
                           version = version + 1
            WHERE id = (
                SELECT id FROM job
                WHERE status = 'queued' AND run_after <= now()
                ORDER BY run_after, id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, kind, dedup_key, payload, attempts, max_attempts, claimed_by
            """
        ),
        {"me": worker_id},
    ).first()
    if row is None:
        return None
    return Job(
        id=row.id,
        kind=row.kind,
        dedup_key=row.dedup_key,
        payload=row.payload,
        attempts=row.attempts,
        max_attempts=row.max_attempts,
        claimed_by=row.claimed_by,
    )


def complete(conn: Connection, job_id: int, worker_id: str) -> bool:
    """``running`` → ``done`` for the claiming worker only."""
    result = conn.execute(
        text(
            "UPDATE job SET status = 'done', version = version + 1 "
            "WHERE id = :id AND status = 'running' AND claimed_by = :me"
        ),
        {"id": job_id, "me": worker_id},
    )
    return result.rowcount == 1


def requeue(
    conn: Connection,
    job_id: int,
    *,
    delay_s: float,
    worker_id: str | None = None,
    error_code: str | None = None,
    count_attempt: bool = False,
) -> str | None:
    """Apply the merge rule to a ``running`` job. Returns the new status or ``None`` if the job
    was not running (or not claimed by ``worker_id`` when given)."""
    params: dict[str, Any] = {
        "id": job_id,
        "me": worker_id,
        "delay": delay_s,
        "err": error_code,
        "inc": 1 if count_attempt else 0,
    }
    owner = "AND (CAST(:me AS text) IS NULL OR claimed_by = :me)"
    try:
        with conn.begin_nested():
            row = conn.execute(
                text(
                    f"""
                    UPDATE job SET status = 'queued', claimed_by = NULL, claimed_at = NULL,
                        run_after = now() + make_interval(secs => :delay),
                        attempts = attempts + :inc,
                        last_error_code = COALESCE(:err, last_error_code),
                        version = version + 1
                    WHERE id = :id AND status = 'running' {owner}
                      AND NOT EXISTS (
                        SELECT 1 FROM job q
                        WHERE q.kind = job.kind AND q.dedup_key = job.dedup_key
                          AND q.status = 'queued')
                    RETURNING status
                    """
                ),
                params,
            ).first()
    except IntegrityError:
        row = None  # a concurrent enqueue took the queued slot first
    if row is not None:
        return "queued"
    superseded = conn.execute(
        text(
            f"""
            UPDATE job SET status = 'superseded', attempts = attempts + :inc,
                last_error_code = COALESCE(:err, last_error_code), version = version + 1
            WHERE id = :id AND status = 'running' {owner}
            """
        ),
        params,
    )
    return "superseded" if superseded.rowcount == 1 else None


def fail(conn: Connection, job: Job, error_code: str) -> str | None:
    """Record a failed attempt: ``dead`` after ``max_attempts``, otherwise requeue with backoff.

    Only for side-effect-free jobs; sending never retries through this path (§6.2, §6.5).
    """
    attempts = job.attempts + 1
    if attempts >= job.max_attempts:
        dead = conn.execute(
            text(
                "UPDATE job SET status = 'dead', attempts = attempts + 1, last_error_code = :err, "
                "version = version + 1 WHERE id = :id AND status = 'running' AND claimed_by = :me"
            ),
            {"id": job.id, "me": job.claimed_by, "err": error_code},
        )
        return "dead" if dead.rowcount == 1 else None
    return requeue(
        conn,
        job.id,
        delay_s=backoff_seconds(attempts),
        worker_id=job.claimed_by,
        error_code=error_code,
        count_attempt=True,
    )


def recover_orphaned(conn: Connection, worker_id: str) -> dict[int, str]:
    """Startup takeover (Y1): apply the merge rule to every ``running`` job not claimed by this
    worker. Only call this while holding the singleton lock: that is the proof that the previous
    owner is dead (§6.1). Nothing is taken over because of a timeout. Returns {job_id: status}.
    """
    ids: list[int] = list(
        conn.execute(
            text(
                "SELECT id FROM job WHERE status = 'running' "
                "AND claimed_by IS DISTINCT FROM :me ORDER BY id FOR UPDATE"
            ),
            {"me": worker_id},
        ).scalars()
    )
    outcome: dict[int, str] = {}
    for job_id in ids:
        status = requeue(conn, job_id, delay_s=0.0, error_code="worker_lost")
        if status is not None:
            outcome[job_id] = status
    return outcome


def queued_run_after(conn: Connection, job_id: int) -> datetime | None:
    """Small read helper for callers and tests."""
    return conn.execute(
        text("SELECT run_after FROM job WHERE id = :id AND status = 'queued'"), {"id": job_id}
    ).scalar()
