# SYNTHETIC: child worker process for tests/db/test_db_crash.py (not a test module).
"""Start a real Worker, run one job, and optionally die with SIGKILL inside the handler.

argv: database_url mode   (mode: poison | draft | draft_then_die)
Prints one JSON line per event on stdout.
"""

from __future__ import annotations

import json
import os
import signal
import sys

from sqlalchemy import create_engine, text

from app.config import AppEnv, Settings
from app.db.writes import insert_draft_fenced
from app.queue.jobs import Job
from app.queue.locks import ConversationLock
from app.queue.worker import Worker


def emit(**values: object) -> None:
    print(json.dumps(values), flush=True)


def die() -> None:
    os.kill(os.getpid(), signal.SIGKILL)


def main() -> None:
    url, mode = sys.argv[1], sys.argv[2]
    engine = create_engine(url)

    def poison(job: Job, lock: ConversationLock | None) -> None:
        die()  # e.g. OOM kill or a crash in a native library

    def draft(job: Job, lock: ConversationLock | None) -> None:
        assert lock is not None
        with lock.connection.begin():
            seq = lock.connection.execute(
                text("SELECT last_inbound_seq FROM conversation WHERE id = :c"),
                {"c": lock.conversation_id},
            ).scalar_one()
            draft_id = insert_draft_fenced(lock, based_on_seq=seq, action="ask_info", parts=["SYN"])
        emit(event="draft", draft_id=draft_id)
        if mode == "draft_then_die":
            die()  # after the draft committed, before the job is marked done

    handler = poison if mode == "poison" else draft
    settings = Settings(app_env=AppEnv.TEST, worker_singleton_poll_s=0.2)
    worker = Worker(engine, {"poison": handler, "process_chat": handler}, settings=settings)
    emit(event="recovered", jobs={str(k): v for k, v in worker.start().items()})
    result = worker.run_once()
    emit(event="result", outcome=None if result is None else result.outcome)
    worker.stop()


if __name__ == "__main__":
    main()
