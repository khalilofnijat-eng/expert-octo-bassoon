# SYNTHETIC: all rows created here are made-up test data.
"""Row factories and small helpers for tests/db."""

from __future__ import annotations

import threading
from typing import Any

from sqlalchemy import Connection, Engine, text

from app.config import AppEnv, Settings
from app.db.writes import record_message


class ExitRecorder:
    """Stands in for ``os._exit`` as a WorkerSingleton ``on_lost`` hook."""

    def __init__(self) -> None:
        self.codes: list[int] = []
        self.called = threading.Event()

    def __call__(self, code: int) -> None:
        self.codes.append(code)
        self.called.set()


def settings(**values: Any) -> Settings:
    base: dict[str, Any] = {
        "app_env": AppEnv.TEST,
        "worker_singleton_poll_s": 0.05,
        "worker_lock_busy_delay_s": 30.0,
    }
    return Settings(**{**base, **values})


def make_conversation(conn: Connection, chat: str = "SYN-chat-1", **values: Any) -> int:
    cols = {"avito_chat_id": chat, **values}
    names = ", ".join(cols)
    params = ", ".join(f":{k}" for k in cols)
    return int(
        conn.execute(
            text(f"INSERT INTO conversation ({names}) VALUES ({params}) RETURNING id"), cols
        ).scalar_one()
    )


def customer_message(engine: Engine, cid: int, mid: str) -> int | None:
    with engine.begin() as conn:
        return record_message(
            conn,
            conversation_id=cid,
            avito_message_id=mid,
            author_role="customer",
            direction="in",
            type="text",
            source="webhook",
            content_masked="SYN hello",
        )


def make_draft(conn: Connection, conversation_id: int, based_on_seq: int) -> int:
    return int(
        conn.execute(
            text(
                "INSERT INTO draft (conversation_id, based_on_seq, action, parts) "
                "VALUES (:c, :s, 'ask_info', ARRAY['SYN part']) RETURNING id"
            ),
            {"c": conversation_id, "s": based_on_seq},
        ).scalar_one()
    )


def make_outbound(conn: Connection, draft_id: int, part_no: int = 1, part_count: int = 1) -> int:
    return int(
        conn.execute(
            text(
                "INSERT INTO outbound_message (idempotency_key, draft_id, part_no, part_count, "
                "kind, body_text) VALUES (:k, :d, :p, :n, 'text', 'SYN text') RETURNING id"
            ),
            {"k": f"SYN-{draft_id}-{part_no}-1", "d": draft_id, "p": part_no, "n": part_count},
        ).scalar_one()
    )


def enable_sending(conn: Connection) -> None:
    conn.execute(
        text("UPDATE system_setting SET kill_switch = false, automation_mode = 'approve_to_send'")
    )


def job_row(engine: Engine, job_id: int) -> Any:
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT status, attempts, last_error_code, claimed_by, "
                "extract(epoch FROM run_after - now()) AS wait_s FROM job WHERE id = :i"
            ),
            {"i": job_id},
        ).one()


def audit_mark(engine: Engine) -> int:
    """Highest audit_event id so far (audit rows survive between tests; job ids do not)."""
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT coalesce(max(id), 0) FROM audit_event")).scalar_one())


def alerts(engine: Engine, job_id: int, since: int) -> list[Any]:
    with engine.connect() as conn:
        return list(
            conn.execute(
                text(
                    "SELECT action, reason_code FROM audit_event WHERE result = 'alert' "
                    "AND entity_ids ->> 'job_id' = :j AND id > :since ORDER BY id"
                ),
                {"j": str(job_id), "since": since},
            ).all()
        )
