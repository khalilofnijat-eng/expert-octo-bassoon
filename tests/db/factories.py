# SYNTHETIC: all rows created here are made-up test data.
"""Row factories for tests/db."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, text


def make_conversation(conn: Connection, chat: str = "SYN-chat-1", **values: Any) -> int:
    cols = {"avito_chat_id": chat, **values}
    names = ", ".join(cols)
    params = ", ".join(f":{k}" for k in cols)
    return int(
        conn.execute(
            text(f"INSERT INTO conversation ({names}) VALUES ({params}) RETURNING id"), cols
        ).scalar_one()
    )


def make_draft(conn: Connection, conversation_id: int, based_on_seq: int) -> int:
    return int(
        conn.execute(
            text(
                "INSERT INTO draft (conversation_id, based_on_seq, action, parts) "
                "VALUES (:c, :s, 'ask_info', ARRAY['SYN part'])  RETURNING id"
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
