"""The single worker (docs/ARCHITECTURE.md §6.1): singleton lock, startup recovery, and running one
job at a time under its conversation lock.

A handler gets the job and, for conversation jobs (``payload["conversation_id"]``), the held
``ConversationLock``; every write it protects must go through ``lock.connection`` (Y2). Handlers
of other jobs get ``None``. A handler that raises is recorded with ``fail`` (retry or ``dead``).
"""

from __future__ import annotations

import logging
import os
import socket
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from sqlalchemy import Engine

from app.queue import jobs
from app.queue.jobs import Job
from app.queue.locks import ConversationLock, WorkerSingleton, conversation_lock

log = logging.getLogger(__name__)

Handler = Callable[[Job, ConversationLock | None], None]

# Delay before a job whose conversation lock was busy runs again (Y6).
LOCK_BUSY_DELAY_S = 5.0


@dataclass(frozen=True)
class RunResult:
    job_id: int
    outcome: str  # done | lock_busy:<queued|superseded> | failed:<queued|superseded|dead>


def new_worker_id() -> str:
    """Unique per process start, so recovery never mistakes an old run's jobs for its own."""
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


class Worker:
    def __init__(
        self,
        engine: Engine,
        handlers: Mapping[str, Handler],
        worker_id: str | None = None,
        singleton: WorkerSingleton | None = None,
        lock_busy_delay_s: float = LOCK_BUSY_DELAY_S,
    ) -> None:
        self.engine = engine
        self.worker_id = worker_id or new_worker_id()
        self.handlers = handlers
        self.singleton = singleton or WorkerSingleton(engine)
        self.lock_busy_delay_s = lock_busy_delay_s

    def start(self, watchdog_interval_s: float | None = None) -> dict[int, str]:
        """Take the singleton lock (raises ``SingletonBusyError`` if held), then recover jobs
        left ``running`` by a dead worker with the merge rule (Y1)."""
        self.singleton.acquire()
        if watchdog_interval_s is not None:
            self.singleton.start_watchdog(watchdog_interval_s)
        with self.engine.begin() as conn:
            recovered = jobs.recover_orphaned(conn, self.worker_id)
        if recovered:
            log.info("recovered orphaned jobs: %s", recovered)
        return recovered

    def run_once(self) -> RunResult | None:
        """Claim and run one due job. Returns ``None`` when the queue has nothing due."""
        with self.engine.begin() as conn:
            job = jobs.claim(conn, self.worker_id)
        if job is None:
            return None
        conversation_id = job.payload.get("conversation_id")
        try:
            handler = self.handlers[job.kind]  # unknown kind -> fail -> eventually dead
            if conversation_id is None:
                handler(job, None)
            else:
                with conversation_lock(self.engine, int(conversation_id)) as lock:
                    if lock is None:
                        # Y6: never mark done without the lock; requeue with the merge rule.
                        with self.engine.begin() as conn:
                            status = jobs.requeue(
                                conn,
                                job.id,
                                delay_s=self.lock_busy_delay_s,
                                worker_id=self.worker_id,
                            )
                        return RunResult(job.id, f"lock_busy:{status}")
                    handler(job, lock)
        except Exception as exc:
            log.exception("job %s failed", job.id)
            with self.engine.begin() as conn:
                status = jobs.fail(conn, job, type(exc).__name__)
            return RunResult(job.id, f"failed:{status}")
        with self.engine.begin() as conn:
            jobs.complete(conn, job.id, self.worker_id)
        return RunResult(job.id, "done")

    def stop(self) -> None:
        self.singleton.release()
