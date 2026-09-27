"""Persistent job queue on the ``job`` table (docs/ARCHITECTURE.md §6.1–§6.2).

Functions take a ``Connection`` and do not commit; the caller owns the transaction. Every status
change is a conditional UPDATE (CAS on ``status`` and, where it matters, ``claimed_by``).

Attempts: ``claim`` increments ``attempts``, so a job that kills its worker (a "poison" job) is
counted even though ``fail`` never runs. Paths that are not the job's fault give the attempt back
(``refund_attempt``): a busy conversation lock (Y6) and ``defer`` (LLM outage, circuit breaker).
With ``max_attempts = 12`` there are 11 backoffs (10, 20, ... 2560, 3600, 3600 s ceilings, full
jitter over the upper half), about 1.7–3.4 h from the first failure to ``dead``. A job that goes
``dead`` writes an alert row (``app.db.audit.record_alert``); ``requeue_dead`` brings it back.

Requeue merge rule (startup recovery, lock busy, retryable failure, ``defer``): if a ``queued``
job with the same (kind, dedup_key) exists, this job becomes ``superseded`` (the queued one reads
the messages from the DB anyway) and hands its attempt count to it; otherwise it goes back to
``queued``. A concurrent enqueue can win the race for the partial UNIQUE index; a savepoint
catches that and falls back to ``superseded``, so the rule never raises a unique violation.
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

from app.db.audit import append_audit, new_op_id, record_alert
from app.queue.locks import SingletonToken, singleton_fence_sql

BACKOFF_BASE_S = 10.0
BACKOFF_MAX_S = 3600.0


@dataclass(frozen=True)
class Job:
    id: int
    kind: str
    dedup_key: str
    payload: dict[str, Any]
    attempts: int  # including the current claim
    max_attempts: int
    claimed_by: str


def backoff_seconds(attempts: int, rng: random.Random | None = None) -> float:
    """Delay after the ``attempts``-th failed attempt: exponential, 10 s → 1 h, full jitter over
    the upper half of the ceiling (§6.2)."""
    ceiling = min(BACKOFF_MAX_S, BACKOFF_BASE_S * 2 ** max(attempts - 1, 0))
    return max(BACKOFF_BASE_S, (rng or random).uniform(ceiling / 2, ceiling))


def enqueue(
    conn: Connection,
    kind: str,
    dedup_key: str,
    payload: dict[str, Any] | None = None,
    delay_s: float = 0.0,
) -> int | None:
    """Make sure a queued job exists for (kind, dedup_key).

    Returns the id of the queued job that will do the work: a new row, or the existing queued row,
    whose ``run_after`` is pulled forward to ``LEAST(old, new)``. Returns ``None`` when the
    existing queued row is waiting after an error (``last_error_code`` set: failure backoff or
    ``defer``); it is left untouched so a new message cannot erase a backoff, and it still reads
    the new message when it runs. A ``running`` job never blocks the insert (the partial UNIQUE
    covers ``queued`` only), so a message that arrives during a run is not lost.
    """
    stmt = text(
        """
        INSERT INTO job (kind, dedup_key, payload, run_after)
        VALUES (:kind, :dedup_key, :payload, now() + make_interval(secs => :delay))
        ON CONFLICT (kind, dedup_key) WHERE status = 'queued'
        DO UPDATE SET run_after = LEAST(job.run_after, EXCLUDED.run_after)
            WHERE job.last_error_code IS NULL
        RETURNING id
        """
    ).bindparams(bindparam("payload", type_=JSONB))
    row = conn.execute(
        stmt, {"kind": kind, "dedup_key": dedup_key, "payload": payload or {}, "delay": delay_s}
    ).first()
    return None if row is None else int(row[0])


def claim(conn: Connection, worker_id: str, token: SingletonToken) -> Job | None:
    """Claim the next due job with ``FOR UPDATE SKIP LOCKED`` (§6.2), or return ``None``.

    Fenced: nothing is claimed unless ``token`` is still the live singleton (a worker that lost
    the singleton cannot keep taking jobs while a new worker runs).
    """
    row = conn.execute(
        text(
            f"""
            UPDATE job SET status = 'running', claimed_by = :me, claimed_at = now(),
                           attempts = attempts + 1, version = version + 1
            WHERE id = (
                SELECT id FROM job
                WHERE status = 'queued' AND run_after <= now()
                ORDER BY run_after, id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
              AND {singleton_fence_sql()}
            RETURNING id, kind, dedup_key, payload, attempts, max_attempts, claimed_by
            """
        ),
        {"me": worker_id, **token.params()},
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


_OWNER = "AND (CAST(:me AS text) IS NULL OR claimed_by = :me)"


def requeue(
    conn: Connection,
    job_id: int,
    *,
    delay_s: float = 0.0,
    until: datetime | None = None,
    worker_id: str | None = None,
    error_code: str | None = None,
    refund_attempt: bool = False,
) -> str | None:
    """Apply the merge rule to a ``running`` job. ``run_after`` is ``until`` if given, else now +
    ``delay_s``. Returns the new status, or ``None`` if the job was not running (or not claimed by
    ``worker_id`` when given)."""
    params: dict[str, Any] = {
        "id": job_id,
        "me": worker_id,
        "delay": delay_s,
        "until": until,
        "err": error_code,
        "refund": 1 if refund_attempt else 0,
    }
    try:
        with conn.begin_nested():
            row = conn.execute(
                text(
                    f"""
                    UPDATE job SET status = 'queued', claimed_by = NULL, claimed_at = NULL,
                        run_after = COALESCE(CAST(:until AS timestamptz),
                                             now() + make_interval(secs => :delay)),
                        attempts = GREATEST(attempts - :refund, 0),
                        last_error_code = COALESCE(:err, last_error_code),
                        version = version + 1
                    WHERE id = :id AND status = 'running' {_OWNER}
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
            UPDATE job SET status = 'superseded', attempts = GREATEST(attempts - :refund, 0),
                last_error_code = COALESCE(:err, last_error_code), version = version + 1
            WHERE id = :id AND status = 'running' {_OWNER}
            RETURNING kind, dedup_key, attempts
            """
        ),
        params,
    ).first()
    if superseded is None:
        return None
    # The queued twin inherits the failure count, so a poison conversation still ends up dead.
    conn.execute(
        text(
            "UPDATE job SET attempts = GREATEST(attempts, :n) "
            "WHERE kind = :kind AND dedup_key = :key AND status = 'queued'"
        ),
        {"n": superseded.attempts, "kind": superseded.kind, "key": superseded.dedup_key},
    )
    return "superseded"


def _mark_dead(conn: Connection, job_id: int, error_code: str, worker_id: str | None) -> bool:
    row = conn.execute(
        text(
            f"""
            UPDATE job SET status = 'dead', last_error_code = :err, version = version + 1
            WHERE id = :id AND status = 'running' {_OWNER}
            RETURNING kind, attempts
            """
        ),
        {"id": job_id, "me": worker_id, "err": error_code},
    ).first()
    if row is None:
        return False
    record_alert(
        conn,
        action="job_dead",
        entity_ids={"job_id": job_id, "kind": row.kind, "attempts": row.attempts},
        reason_code=error_code,
    )
    return True


def fail(conn: Connection, job: Job, error_code: str) -> str | None:
    """Record a failed attempt (already counted at claim): ``dead`` (+ alert) once
    ``max_attempts`` is used up, otherwise requeue with backoff.

    Only for side-effect-free jobs; sending never retries through this path (§6.2, §6.5). Outages
    of a dependency (LLM circuit open) use ``defer`` instead and do not count.
    """
    if job.attempts >= job.max_attempts:
        return "dead" if _mark_dead(conn, job.id, error_code, job.claimed_by) else None
    return requeue(
        conn,
        job.id,
        delay_s=backoff_seconds(job.attempts),
        worker_id=job.claimed_by,
        error_code=error_code,
    )


def defer(conn: Connection, job: Job, until: datetime, reason: str) -> str | None:
    """Put a running job back until ``until`` without counting an attempt (circuit breaker).

    ``reason`` is stored as ``last_error_code``, so a new message does not pull the job forward
    (see ``enqueue``).
    """
    return requeue(
        conn,
        job.id,
        until=until,
        worker_id=job.claimed_by,
        error_code=reason,
        refund_attempt=True,
    )


def recover_orphaned(conn: Connection, worker_id: str) -> dict[int, str]:
    """Startup takeover (Y1): every ``running`` job not claimed by this worker is an orphan.

    Only call this while holding the singleton lock, after the takeover wait (``Worker.start``):
    that is the proof that the previous owner is dead (§6.1). Nothing is taken over because of a
    timeout. The crash counts as the attempt made at claim time: an orphan that has used up
    ``max_attempts`` goes ``dead`` (+ alert), the others get the merge rule with backoff.
    Returns {job_id: new status}.
    """
    rows = conn.execute(
        text(
            "SELECT id, attempts, max_attempts FROM job WHERE status = 'running' "
            "AND claimed_by IS DISTINCT FROM :me ORDER BY id FOR UPDATE"
        ),
        {"me": worker_id},
    ).all()
    outcome: dict[int, str] = {}
    for row in rows:
        status: str | None
        if row.attempts >= row.max_attempts:
            status = "dead" if _mark_dead(conn, row.id, "worker_lost", None) else None
        else:
            status = requeue(
                conn, row.id, delay_s=backoff_seconds(row.attempts), error_code="worker_lost"
            )
        if status is not None:
            outcome[row.id] = status
    return outcome


def requeue_dead(conn: Connection, job_id: int, actor: str) -> str | None:
    """Admin action: give a ``dead`` job a fresh start (attempts 0, due now), with the merge rule.

    Returns ``queued``, ``superseded`` (a queued job for the same key exists and will do the
    work), or ``None`` if the job is not dead. Writes an audit row.
    """
    params = {"id": job_id}
    try:
        with conn.begin_nested():
            row = conn.execute(
                text(
                    """
                    UPDATE job SET status = 'queued', attempts = 0, last_error_code = NULL,
                        run_after = now(), claimed_by = NULL, claimed_at = NULL,
                        version = version + 1
                    WHERE id = :id AND status = 'dead'
                      AND NOT EXISTS (
                        SELECT 1 FROM job q
                        WHERE q.kind = job.kind AND q.dedup_key = job.dedup_key
                          AND q.status = 'queued')
                    RETURNING id
                    """
                ),
                params,
            ).first()
    except IntegrityError:
        row = None
    status: str | None = "queued" if row is not None else None
    if status is None:
        superseded = conn.execute(
            text(
                "UPDATE job SET status = 'superseded', version = version + 1 "
                "WHERE id = :id AND status = 'dead'"
            ),
            params,
        )
        status = "superseded" if superseded.rowcount == 1 else None
    if status is not None:
        append_audit(
            conn,
            op_id=new_op_id("job_requeue_dead"),
            actor=actor,
            action="job_requeue_dead",
            entity_ids={"job_id": job_id},
            result=status,
        )
    return status
