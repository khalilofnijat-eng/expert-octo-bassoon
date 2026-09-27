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
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from sqlalchemy import Engine

from app.config import Settings, get_settings
from app.db.roles import check_runtime_role
from app.queue import jobs
from app.queue.jobs import Job
from app.queue.locks import (
    ConversationLock,
    SingletonNotHeldError,
    WorkerSingleton,
    conversation_lock,
)

log = logging.getLogger(__name__)

Handler = Callable[[Job, ConversationLock | None], None]


@dataclass(frozen=True)
class RunResult:
    job_id: int
    outcome: str  # done | lock_busy:<queued|superseded> | failed:<queued|superseded|dead>


def new_worker_id() -> str:
    """Unique per process start, so recovery never mistakes an old run's jobs for its own."""
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


class Worker:
    """Timing comes from ``Settings``: the watchdog polls every ``worker_singleton_poll_s`` (each
    probe has the same deadline), a new worker waits ``2 x worker_singleton_poll_s`` after taking
    the singleton before recovery (so a previous worker that lost the lock has detected it and
    exited), and a busy conversation lock delays a job by ``worker_lock_busy_delay_s``."""

    def __init__(
        self,
        engine: Engine,
        handlers: Mapping[str, Handler],
        worker_id: str | None = None,
        singleton: WorkerSingleton | None = None,
        settings: Settings | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self.engine = engine
        self.worker_id = worker_id or new_worker_id()
        self.handlers = handlers
        poll_s = self.settings.worker_singleton_poll_s
        self.singleton = singleton or WorkerSingleton(engine, check_timeout_s=poll_s)
        self._sleep = sleep

    def start(self, watchdog: bool = True) -> dict[int, str]:
        """Check the DB role, take the singleton (raises ``SingletonBusyError`` if held), start
        the watchdog, wait for the takeover delay, then recover orphaned jobs (Y1)."""
        poll_s = self.settings.worker_singleton_poll_s
        with self.engine.connect() as conn:
            check_runtime_role(conn, self.settings.app_env)
        self.singleton.acquire()
        if watchdog:
            self.singleton.start_watchdog(poll_s)
        self._sleep(2 * poll_s)
        # TODO(T-025): before recovery, move outbox rows in 'sending' to 'unknown' and reconcile
        # them; sending stays off until that is done (§6.8).
        with self.engine.begin() as conn:
            recovered = jobs.recover_orphaned(conn, self.worker_id)
        if recovered:
            log.info("recovered orphaned jobs: %s", recovered)
        return recovered

    def run_once(self) -> RunResult | None:
        """Claim and run one due job. Returns ``None`` when nothing is due (or claimable)."""
        token = self.singleton.token
        if token is None:
            raise SingletonNotHeldError("run_once needs the worker singleton")
        with self.engine.begin() as conn:
            job = jobs.claim(conn, self.worker_id, token)
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
                        # Y6: never mark done without the lock; requeue with the merge rule and
                        # give the attempt back (a busy lock is not the job's failure).
                        with self.engine.begin() as conn:
                            status = jobs.requeue(
                                conn,
                                job.id,
                                delay_s=self.settings.worker_lock_busy_delay_s,
                                worker_id=self.worker_id,
                                refund_attempt=True,
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
